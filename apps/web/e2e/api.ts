import type { Page, Route } from '@playwright/test';
import { generations, projects, uploads, pipelines } from '../src/lib/fixtures';
import type { Asset, Generation, GenerationRequest, Gpu, Project } from '../src/lib/types';

/**
 * Answers the browser's API calls with the fixtures, so the tests need no API and always see the same data. A
 * generation sent from the composer is queued, then runs and finishes over the next few times the list is fetched.
 */
// By default no GPU is rented, as on a machine that runs its own renderer
const noGpu: Gpu = { state: 'off', phase: null, ready: [], eta_s: {} };

export async function mockApi(page: Page, { signedIn = true, credits = 1000, gpu = noGpu } = {}) {
  const created: Generation[] = [];
  const createdProjects: Project[] = [];
  let reads = 0;

  // Signed in as an admin: the cookie gets past the sign-in redirect (src/proxy.ts), and the mocks never check it
  if (signedIn) await signIn(page);
  await page.route('**/api/auth/me', route => route.fulfill({ json: { id: 'usr_e2e', email: 'me@example.com', is_admin: true } }));

  // The API's price table; WELCOME is an invite code worth 50
  let balance = credits;
  const prices = { image: { low: 1, medium: 1, high: 2 }, video_per_5s: { low: 10, medium: 20, high: 40 }, per_clip: 10 };
  await page.route('**/api/credits', route => route.fulfill({ json: { balance, prices } }));
  await page.route('**/api/credits/redeem', async route => {
    const { code } = route.request().postDataJSON() as { code: string };
    if (code.toUpperCase() !== 'WELCOME') return route.fulfill({ status: 404, json: { detail: "That code doesn't work" } });
    balance += 50;
    return route.fulfill({ json: { balance, prices } });
  });

  await page.route('**/api/health', route => route.fulfill({ json: { status: 'ok', db: 'ok' } }));
  await page.route('**/api/pipelines', route => route.fulfill({ json: pipelines }));
  await page.route('**/api/gpu', route => route.fulfill({ json: gpu }));

  await page.route('**/api/assets', async route => {
    if (route.request().method() === 'GET') return route.fulfill({ json: uploads });
    const asset: Asset = { ...uploads[1], id: `ast_upload_${Date.now()}`, created_at: new Date().toISOString() };
    return route.fulfill({ status: 201, json: asset });
  });

  // With or without ?project_id=
  await page.route(/\/api\/generations(\?.*)?$/, async route => {
    if (route.request().method() === 'POST') return route.fulfill({ status: 201, json: [queue(route)] });
    reads += 1;
    for (const g of created) advance(g);
    const project = new URL(route.request().url()).searchParams.get('project_id');
    const all = [...created, ...generations];
    return route.fulfill({ json: project === null ? all : all.filter(g => g.project_id === project) });
  });

  let preferences = { smart_queue: false };
  await page.route('**/api/preferences', async route => {
    if (route.request().method() === 'PATCH') preferences = { ...preferences, ...route.request().postDataJSON() };
    return route.fulfill({ json: preferences });
  });

  await page.route('**/api/projects', async route => {
    if (route.request().method() === 'GET') return route.fulfill({ json: [...createdProjects, ...projects] });
    const { name } = route.request().postDataJSON() as { name: string };
    const project: Project = {
      id: `prj_new_${createdProjects.length}`,
      name,
      demo: false,
      mine: true,
      created_at: new Date().toISOString(),
      generation_count: 0,
      covers: []
    };
    createdProjects.unshift(project);
    return route.fulfill({ status: 201, json: project });
  });

  function queue(route: Route): Generation {
    const body = route.request().postDataJSON() as GenerationRequest;
    const capability = body.media_type === 'image' ? 'image.generate' : 'video.generate';
    const pipeline = pipelines.find(w => w.default_for.includes(capability))!;
    const generation: Generation = {
      id: `gen_new_${created.length}`,
      status: 'queued',
      capability,
      pipeline_id: pipeline.id,
      prompt: body.prompt,
      project_id: body.project_id ?? null,
      params: {
        quality: body.params.quality ?? 'medium',
        aspect_ratio: body.params.aspect_ratio ?? null,
        duration_s: body.params.duration_s ?? null,
        seed: body.params.seed ?? 42
      },
      inputs: [],
      outputs: [],
      progress: null,
      error: null,
      created_at: new Date().toISOString(),
      started_at: null,
      finished_at: null
    };
    created.unshift(generation);
    return generation;
  }

  function advance(g: Generation) {
    if (g.status === 'queued') Object.assign(g, { status: 'running', progress: 0.5, started_at: new Date().toISOString() });
    else if (g.status === 'running' && reads > 3)
      Object.assign(g, {
        status: 'done',
        progress: null,
        finished_at: new Date().toISOString(),
        outputs: [{ ...uploads[2], id: `${g.id}_out`, source: 'generation' }]
      });
  }
}

/** What signing in leaves behind: the session cookie, which gets past the sign-in redirect (src/proxy.ts). */
export function signIn(page: Page) {
  return page.context().addCookies([{ name: 'unnoodle_session', value: 'e2e', domain: 'localhost', path: '/' }]);
}
