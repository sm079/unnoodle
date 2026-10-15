// Mock data in the API's shapes (see types.ts), which the end-to-end tests serve in place of the API. There are no mock
// video files, so video assets point at their poster image.

import type { AspectRatio, Asset, Generation, Project, Workflow } from './types';

const mockFiles = {
  'road-dusk': [1280, 720],
  'portrait-warm': [768, 1024],
  'garden-square': [1024, 1024],
  'city-vertical': [720, 1280],
  'room-photo': [1024, 768],
  'character-ref': [768, 1024]
} as const;

type MockFile = keyof typeof mockFiles;

function image(id: string, file: MockFile, source: Asset['source'], created_at: string): Asset {
  const url = `/mock/${file}.svg`;
  const [width, height] = mockFiles[file];
  return { id, media_type: 'image', source, url, thumbnail_url: url, width, height, duration_s: null, created_at };
}

function video(id: string, poster: MockFile, duration_s: number, source: Asset['source'], created_at: string): Asset {
  return { ...image(id, poster, source, created_at), media_type: 'video', duration_s };
}

const allShapes: AspectRatio[] = ['1:1', '2:3', '3:2', '3:4', '4:3', '9:16', '16:9', '21:9'];

/** The real catalogue, as the API lists it. */
export const workflows: Workflow[] = [
  {
    id: 'krea2-turbo',
    capabilities: ['image.generate'],
    model: 'krea-2',
    model_name: 'Krea 2',
    description: 'Pictures from a description',
    default_for: ['image.generate'],
    aspect_ratios: allShapes,
    max_count: 4,
    durations_s: [],
    sound: false,
    accepts: []
  },
  {
    id: 'flux2-klein-edit',
    capabilities: ['image.edit'],
    model: 'flux-2-klein',
    model_name: 'FLUX.2 Klein',
    description: 'Changes or combines up to three photos',
    default_for: ['image.edit'],
    aspect_ratios: allShapes,
    max_count: 1,
    durations_s: [],
    sound: false,
    accepts: [{ role: 'reference', media_type: 'image', most: 3 }]
  },
  {
    id: 'minimax-h3',
    capabilities: ['video.generate', 'video.reference'],
    model: 'minimax-h3',
    model_name: 'MiniMax H3',
    description: 'Video with sound, from a description and any photos or clips to follow',
    default_for: ['video.generate', 'video.reference'],
    aspect_ratios: allShapes,
    max_count: 1,
    durations_s: [5, 10, 15],
    sound: true,
    accepts: [
      { role: 'reference', media_type: 'image', most: 9 },
      { role: 'reference', media_type: 'video', most: 3 }
    ]
  }
];

const room = image('ast_room', 'room-photo', 'upload', '2026-10-10T08:00:00Z');
const character = image('ast_character', 'character-ref', 'upload', '2026-10-10T08:01:00Z');
const danceClip = video('ast_dance', 'city-vertical', 6, 'upload', '2026-10-10T08:02:00Z');

export const uploads: Asset[] = [danceClip, character, room];

const portrait = image('ast_portrait', 'portrait-warm', 'generation', '2026-10-11T09:01:00Z');
const roadClip = video('ast_road', 'road-dusk', 5, 'generation', '2026-10-12T09:03:00Z');
const morph = video('ast_morph', 'portrait-warm', 8, 'generation', '2026-10-13T16:05:00Z');
const roomEdit = image('ast_room_edit', 'room-photo', 'generation', '2026-10-13T11:00:30Z');
const greenhouse = [
  image('ast_greenhouse_1', 'garden-square', 'generation', '2026-10-11T15:00:20Z'),
  image('ast_greenhouse_2', 'garden-square', 'generation', '2026-10-11T15:00:20Z')
];

const imageParams = { quality: 'medium', aspect_ratio: '3:4', duration_s: null, count: 1, seed: 12 } as const;
const editParams = { ...imageParams, aspect_ratio: null } as const;
const videoParams = { quality: 'medium', aspect_ratio: '16:9', duration_s: 5, count: 1, seed: 901 } as const;

const ended = { progress: null, started_at: null };

/** Newest first, the order the API returns them in. Covers every status, for both images and videos. */
export const generations: Generation[] = [
  {
    id: 'gen_queued',
    status: 'queued',
    capability: 'image.generate',
    workflow_id: 'krea2-turbo',
    project_id: null,
    prompt: 'girl with silver hair on a rain-soaked neon street, looking back over her shoulder',
    params: { ...imageParams, seed: 7 },
    inputs: [],
    outputs: [],
    progress: null,
    error: null,
    created_at: '2026-10-15T09:20:00Z',
    started_at: null,
    finished_at: null
  },
  {
    id: 'gen_running',
    status: 'running',
    capability: 'video.reference',
    workflow_id: 'minimax-h3',
    project_id: 'prj_film',
    prompt: '@photo1 turns towards the camera as the light fades',
    params: { ...videoParams, aspect_ratio: '3:4' },
    inputs: [{ role: 'reference', asset: portrait }],
    outputs: [],
    progress: 0.42,
    error: null,
    created_at: '2026-10-15T09:18:00Z',
    started_at: '2026-10-15T09:18:05Z',
    finished_at: null
  },
  {
    id: 'gen_failed',
    status: 'failed',
    capability: 'video.reference',
    workflow_id: 'minimax-h3',
    project_id: null,
    prompt: 'the room in @photo1 fills with the plants from @photo2 over a year',
    params: { ...videoParams, quality: 'high', duration_s: 15 },
    inputs: [
      { role: 'reference', asset: room },
      { role: 'reference', asset: greenhouse[0] }
    ],
    outputs: [],
    ...ended,
    error: 'This was too big to make. Try a lower quality, a shorter length or fewer at a time.',
    created_at: '2026-10-14T18:30:00Z',
    finished_at: '2026-10-14T18:31:10Z'
  },
  {
    id: 'gen_dance',
    status: 'done',
    capability: 'video.reference',
    workflow_id: 'minimax-h3',
    project_id: null,
    prompt: 'the character in @photo1 dances like the dancer in @clip1',
    params: { ...videoParams, aspect_ratio: '9:16', seed: 5521 },
    inputs: [
      { role: 'reference', asset: danceClip },
      { role: 'reference', asset: character }
    ],
    outputs: [video('ast_dance_out', 'city-vertical', 5, 'generation', '2026-10-14T12:04:00Z')],
    ...ended,
    error: null,
    created_at: '2026-10-14T12:00:00Z',
    finished_at: '2026-10-14T12:04:00Z'
  },
  {
    id: 'gen_morph',
    status: 'done',
    capability: 'video.reference',
    workflow_id: 'minimax-h3',
    project_id: 'prj_film',
    prompt: 'slow morph from the woman in @photo1 to the character in @photo2',
    params: { ...videoParams, aspect_ratio: '3:4', duration_s: 10, seed: 77 },
    inputs: [
      { role: 'reference', asset: portrait },
      { role: 'reference', asset: character }
    ],
    outputs: [morph],
    ...ended,
    error: null,
    created_at: '2026-10-13T16:00:00Z',
    finished_at: '2026-10-13T16:05:00Z'
  },
  {
    id: 'gen_edit',
    status: 'done',
    capability: 'image.edit',
    workflow_id: 'flux2-klein-edit',
    project_id: 'prj_mood',
    prompt: 'replace the sofa with a green velvet armchair',
    params: { ...editParams, seed: 3130 },
    inputs: [{ role: 'reference', asset: room }],
    outputs: [roomEdit],
    ...ended,
    error: null,
    created_at: '2026-10-13T11:00:00Z',
    finished_at: '2026-10-13T11:00:30Z'
  },
  {
    id: 'gen_road',
    status: 'done',
    capability: 'video.generate',
    workflow_id: 'minimax-h3',
    project_id: 'prj_film',
    prompt: 'an old jeep on an empty road at dusk, low angle, film grain',
    params: videoParams,
    inputs: [],
    outputs: [roadClip],
    ...ended,
    error: null,
    created_at: '2026-10-12T09:00:00Z',
    finished_at: '2026-10-12T09:03:00Z'
  },
  {
    id: 'gen_greenhouse',
    status: 'done',
    capability: 'image.generate',
    workflow_id: 'krea2-turbo',
    project_id: 'prj_mood',
    prompt: 'overgrown greenhouse, morning light, film photo',
    params: { ...imageParams, aspect_ratio: '1:1', count: 2, seed: 4410 },
    inputs: [],
    outputs: greenhouse,
    ...ended,
    error: null,
    created_at: '2026-10-11T15:00:00Z',
    finished_at: '2026-10-11T15:00:20Z'
  },
  {
    id: 'gen_portrait',
    status: 'done',
    capability: 'image.generate',
    workflow_id: 'krea2-turbo',
    project_id: null,
    prompt: 'portrait of a woman in a red coat, warm backlight',
    params: imageParams,
    inputs: [],
    outputs: [portrait],
    ...ended,
    error: null,
    created_at: '2026-10-11T09:00:00Z',
    finished_at: '2026-10-11T09:01:00Z'
  }
];

/** A project as the API describes it, from the generations filed in it. */
function project(id: string, name: string, created_at: string): Project {
  const filed = generations.filter(g => g.project_id === id);
  return { id, name, created_at, generation_count: filed.length, covers: filed.flatMap(g => g.outputs).slice(0, 3) };
}

/** Newest first, the order the API returns them in. */
export const projects: Project[] = [
  project('prj_mood', 'Moodboard', '2026-10-09T10:00:00Z'),
  project('prj_film', 'Short film', '2026-10-08T10:00:00Z')
];
