// Mock data in the API's shapes (see types.ts): what the end-to-end tests serve in place of the API, and what the UI
// shows where the API has nothing yet, such as projects. There are no mock video files, so video assets point at
// their poster image.

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

const allRatios: AspectRatio[] = ['1:1', '3:4', '4:3', '9:16', '16:9'];
const videoRatios: AspectRatio[] = ['16:9', '9:16', '3:4', '1:1'];

const imageWorkflow = {
  resolutions: { '1K': allRatios, '2K': allRatios },
  max_count: 4,
  durations_s: [],
  audio: false,
  roles: {},
  default: false
} satisfies Partial<Workflow>;

const videoWorkflow = {
  resolutions: { '540p': videoRatios, '720p': videoRatios, '1080p': videoRatios },
  max_count: 4,
  durations_s: [5, 8, 10],
  audio: true,
  roles: {},
  default: true
} satisfies Partial<Workflow>;

export const workflows: Workflow[] = [
  {
    ...imageWorkflow,
    id: 'illustrious-t2i',
    capability: 'image.generate',
    model: 'illustrious',
    model_name: 'Illustrious',
    description: 'Anime and illustration styles'
  },
  {
    ...imageWorkflow,
    id: 'anima-t2i',
    capability: 'image.generate',
    model: 'anima',
    model_name: 'Anima',
    description: 'Stylised characters with clean line art'
  },
  {
    ...imageWorkflow,
    id: 'flux-klein-9b-t2i',
    capability: 'image.generate',
    model: 'flux-klein-9b',
    model_name: 'Flux Klein 9B',
    description: 'Photoreal images from a prompt',
    default: true,
    resolutions: { '1K': allRatios, '2K': allRatios, '4K': allRatios }
  },
  {
    ...imageWorkflow,
    id: 'flux-klein-9b-edit',
    capability: 'image.edit',
    model: 'flux-klein-9b',
    model_name: 'Flux Klein 9B',
    description: 'Change part of an image and keep the rest',
    default: true,
    roles: { edit_target: 1, reference: 2 }
  },
  {
    ...videoWorkflow,
    id: 'ltx-2.5-t2v',
    capability: 'video.generate',
    model: 'ltx-2.5',
    model_name: 'LTX 2.5',
    description: 'Fast video from a prompt'
  },
  {
    ...videoWorkflow,
    id: 'ltx-2.5-i2v',
    capability: 'video.from_frame',
    model: 'ltx-2.5',
    model_name: 'LTX 2.5',
    description: 'Animate a start frame',
    resolutions: { '720p': videoRatios, '1080p': videoRatios },
    roles: { start_frame: 1 }
  },
  {
    ...videoWorkflow,
    id: 'ltx-2.5-keyframes',
    capability: 'video.keyframes',
    model: 'ltx-2.5',
    model_name: 'LTX 2.5',
    description: 'Move between keyframes placed on a timeline',
    resolutions: { '720p': videoRatios },
    roles: { keyframe: 8 }
  },
  {
    ...videoWorkflow,
    id: 'minimax-h3-first-last',
    capability: 'video.first_last',
    model: 'minimax-h3',
    model_name: 'MiniMax H3',
    description: 'Fill in the motion between two frames',
    resolutions: { '768p': videoRatios, '1080p': videoRatios },
    durations_s: [6, 10],
    audio: false,
    max_count: 2,
    roles: { start_frame: 1, end_frame: 1 }
  },
  {
    ...videoWorkflow,
    id: 'scail-swap',
    capability: 'video.character_swap',
    model: 'scail',
    model_name: 'SCAIL',
    description: 'Replace the person in a clip with a character',
    resolutions: { '720p': ['9:16', '16:9', '1:1'] },
    durations_s: [6],
    audio: false,
    max_count: 1,
    roles: { source_video: 1, reference: 1 }
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

const imageParams = { aspect_ratio: '3:4', resolution: '1K', duration_s: null, count: 1, seed: 12, audio: false } as const;
const videoParams = { aspect_ratio: '16:9', resolution: '720p', duration_s: 5, count: 1, seed: 901, audio: false } as const;

const ended = { progress: null, started_at: null };

/** Newest first, the order the API returns them in. Covers every status, for both images and videos. */
export const generations: Generation[] = [
  {
    id: 'gen_queued',
    status: 'queued',
    capability: 'image.generate',
    workflow_id: 'anima-t2i',
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
    capability: 'video.from_frame',
    workflow_id: 'ltx-2.5-i2v',
    prompt: 'she turns towards the camera as the light fades',
    params: { ...videoParams, aspect_ratio: '3:4' },
    inputs: [{ role: 'start_frame', asset: portrait, position_s: null }],
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
    capability: 'video.first_last',
    workflow_id: 'minimax-h3-first-last',
    prompt: 'the empty room fills with plants over a year, timelapse',
    params: { ...videoParams, resolution: '1080p', duration_s: 6 },
    inputs: [
      { role: 'start_frame', asset: room, position_s: null },
      { role: 'end_frame', asset: greenhouse[0], position_s: null }
    ],
    outputs: [],
    ...ended,
    error: 'The GPU ran out of memory. Try a smaller size or fewer outputs.',
    created_at: '2026-10-14T18:30:00Z',
    finished_at: '2026-10-14T18:31:10Z'
  },
  {
    id: 'gen_swap',
    status: 'done',
    capability: 'video.character_swap',
    workflow_id: 'scail-swap',
    prompt: 'replace the dancer with the character',
    params: { ...videoParams, aspect_ratio: '9:16', duration_s: 6, seed: 5521 },
    inputs: [
      { role: 'source_video', asset: danceClip, position_s: null },
      { role: 'reference', asset: character, position_s: null }
    ],
    outputs: [video('ast_swap', 'city-vertical', 6, 'generation', '2026-10-14T12:04:00Z')],
    ...ended,
    error: null,
    created_at: '2026-10-14T12:00:00Z',
    finished_at: '2026-10-14T12:04:00Z'
  },
  {
    id: 'gen_keyframes',
    status: 'done',
    capability: 'video.keyframes',
    workflow_id: 'ltx-2.5-keyframes',
    prompt: 'slow morph between the two portraits',
    params: { ...videoParams, aspect_ratio: '3:4', duration_s: 8, seed: 77 },
    inputs: [
      { role: 'keyframe', asset: portrait, position_s: 0 },
      { role: 'keyframe', asset: character, position_s: 6 }
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
    workflow_id: 'flux-klein-9b-edit',
    prompt: 'replace the sofa with a green velvet armchair',
    params: { ...imageParams, aspect_ratio: '4:3', seed: 3130 },
    inputs: [{ role: 'edit_target', asset: room, position_s: null }],
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
    workflow_id: 'ltx-2.5-t2v',
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
    workflow_id: 'flux-klein-9b-t2i',
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
    workflow_id: 'illustrious-t2i',
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

export const projects: Project[] = [
  { id: 'prj_film', name: 'Short film', created_at: '2026-10-08T10:00:00Z', covers: [roadClip, morph, portrait] },
  { id: 'prj_mood', name: 'Moodboard', created_at: '2026-10-09T10:00:00Z', covers: [roomEdit, ...greenhouse] }
];
