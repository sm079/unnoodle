import type { Page, Route } from '@playwright/test';
import { generations, projects, uploads, workflows } from '../src/lib/fixtures';
import type { Asset, Generation, GenerationRequest, Project } from '../src/lib/types';

/**
 * Answers the browser's API calls with the fixtures, so the tests need no API and always see the same data. A
 * generation sent from the composer is queued, then runs and finishes over the next few times the list is fetched.
 */
export async function mockApi(page: Page, { signedIn = true } = {}) {
  const created: Generation[] = [];
  const createdProjects: Project[] = [];
  let reads = 0;

  // Signed in as an admin: the cookie gets past the sign-in redirect (src/proxy.ts), and the mocks never check it
  if (signedIn) await signIn(page);
  await page.route('**/api/auth/me', route => route.fulfill({ json: { id: 'usr_e2e', email: 'me@example.com', is_admin: true } }));

  await page.route('**/api/workflows', route => route.fulfill({ json: workflows }));

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
    const workflow = workflows.find(w => w.default_for.includes(capability))!;
    const generation: Generation = {
      id: `gen_new_${created.length}`,
      status: 'queued',
      capability,
      workflow_id: workflow.id,
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
