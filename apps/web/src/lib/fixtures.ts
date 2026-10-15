// Mock data for building the UI before the API exists, in the same shapes the API will return (see types.ts).
// There are no mock video files yet, so video assets point at their poster image.

import type {
  Asset,
  ComposerDraft,
  Generation,
  GenerationParams,
  MediaType,
  Project,
  Tag,
  User,
  Workflow,
  WorkflowControl,
  WorkflowOptions
} from './types';

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

// Look settings are placeholders until the workflows define real ones
const characterControl: WorkflowControl = { id: 'character', label: 'Character', options: ['None', 'Mara', 'Theo', 'Kit'] };
const lens: WorkflowControl = { id: 'lens', label: 'Lens', options: ['Auto', '24mm', '35mm', '50mm', '85mm'] };
const filmSetup: WorkflowControl = {
  id: 'film_setup',
  label: 'Film setup',
  options: ['Auto', 'Digital', '35mm film', '16mm film', 'Anamorphic']
};
const camera: WorkflowControl = { id: 'camera', label: 'Camera', options: ['Auto', 'Static', 'Dolly in', 'Orbit', 'Handheld', 'Crane up'] };
const colorPalette: WorkflowControl = {
  id: 'color_palette',
  label: 'Color palette',
  options: ['Auto', 'Warm', 'Cool', 'Teal and orange', 'Monochrome', 'Pastel']
};
const lighting: WorkflowControl = {
  id: 'lighting',
  label: 'Lighting',
  options: ['Auto', 'Golden hour', 'Low key', 'High key', 'Neon', 'Overcast']
};

const imageOptions: WorkflowOptions = {
  aspect_ratios: ['1:1', '3:4', '4:3', '9:16', '16:9'],
  resolutions: ['1K', '2K'],
  durations_s: [],
  audio: false,
  max_count: 4,
  max_inputs: 0,
  controls: [characterControl, lens]
};

const videoOptions: WorkflowOptions = {
  aspect_ratios: ['16:9', '9:16', '3:4', '1:1'],
  resolutions: ['540p', '720p', '1080p'],
  durations_s: [5, 8, 10],
  audio: true,
  max_count: 4,
  max_inputs: 0,
  controls: [filmSetup, camera, colorPalette, lighting]
};

export const workflows: Workflow[] = [
  {
    id: 'illustrious-t2i',
    name: 'Illustrious',
    capability: 'image.generate',
    description: 'Anime and illustration styles',
    credits: 2,
    options: imageOptions
  },
  {
    id: 'anima-t2i',
    name: 'Anima',
    capability: 'image.generate',
    description: 'Stylised characters with clean line art',
    credits: 2,
    options: imageOptions
  },
  {
    id: 'flux-klein-9b-t2i',
    name: 'Flux Klein 9B',
    capability: 'image.generate',
    description: 'Photoreal images from a prompt',
    credits: 3,
    options: { ...imageOptions, resolutions: ['1K', '2K', '4K'] }
  },
  {
    id: 'flux-klein-9b-edit',
    name: 'Flux Klein 9B',
    capability: 'image.edit',
    description: 'Change part of an image and keep the rest',
    credits: 3,
    options: { ...imageOptions, max_inputs: 1, controls: [lens, lighting] }
  },
  {
    id: 'ltx-2.5-t2v',
    name: 'LTX 2.5',
    capability: 'video.generate',
    description: 'Fast video from a prompt',
    credits: 20,
    options: videoOptions
  },
  {
    id: 'ltx-2.5-i2v',
    name: 'LTX 2.5',
    capability: 'video.from_frame',
    description: 'Animate a start frame',
    credits: 20,
    options: { ...videoOptions, resolutions: ['720p', '1080p'], max_inputs: 1 }
  },
  {
    id: 'ltx-2.5-keyframes',
    name: 'LTX 2.5',
    capability: 'video.keyframes',
    description: 'Move between keyframes placed on a timeline',
    credits: 30,
    options: { ...videoOptions, resolutions: ['720p'], max_inputs: 8, controls: [camera, lighting] }
  },
  {
    id: 'minimax-h3-first-last',
    name: 'MiniMax H3',
    capability: 'video.first_last',
    description: 'Fill in the motion between two frames',
    credits: 40,
    options: {
      ...videoOptions,
      resolutions: ['768p', '1080p'],
      durations_s: [6, 10],
      audio: false,
      max_count: 2,
      max_inputs: 2,
      controls: [camera]
    }
  },
  {
    id: 'scail-swap',
    name: 'SCAIL',
    capability: 'video.character_swap',
    description: 'Replace the person in a clip with a character',
    credits: 50,
    options: {
      ...videoOptions,
      aspect_ratios: ['9:16', '16:9', '1:1'],
      resolutions: ['720p'],
      durations_s: [6],
      audio: false,
      max_count: 1,
      max_inputs: 2,
      controls: []
    }
  }
];

export const me: User = { id: 'usr_me', name: 'Robin', avatar_url: null };

export const projects: Project[] = [
  { id: 'prj_film', name: 'Short film', created_at: '2026-10-08T10:00:00Z' },
  { id: 'prj_mood', name: 'Moodboard', created_at: '2026-10-09T10:00:00Z' }
];

export const tags: Tag[] = [
  { id: 'tag_portrait', name: 'portrait' },
  { id: 'tag_keep', name: 'keep' }
];

const room = image('ast_room', 'room-photo', 'upload', '2026-10-10T08:00:00Z');
const character = image('ast_character', 'character-ref', 'upload', '2026-10-10T08:01:00Z');
const danceClip = video('ast_dance', 'city-vertical', 6, 'upload', '2026-10-10T08:02:00Z');

export const uploads: Asset[] = [danceClip, character, room];

const portrait = image('ast_portrait', 'portrait-warm', 'generation', '2026-10-11T09:01:00Z');
const roadClip = video('ast_road', 'road-dusk', 5, 'generation', '2026-10-12T09:03:00Z');

const imageParams: GenerationParams = { aspect_ratio: '3:4', resolution: '1K', duration_s: null, count: 1, seed: null };
const videoParams: GenerationParams = { aspect_ratio: '16:9', resolution: '720p', duration_s: 5, count: 1, seed: null };

/** Newest first, the order the API will return them in. Covers every status, for both images and videos. */
export const generations: Generation[] = [
  {
    id: 'gen_queued',
    status: 'queued',
    capability: 'image.generate',
    workflow_id: 'anima-t2i',
    prompt: 'girl with silver hair on a rain-soaked neon street, looking back over her shoulder',
    params: imageParams,
    inputs: [],
    outputs: [],
    progress: null,
    error: null,
    project_id: null,
    tag_ids: [],
    created_at: '2026-10-15T09:20:00Z',
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
    project_id: 'prj_film',
    tag_ids: [],
    created_at: '2026-10-15T09:18:00Z',
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
      { role: 'end_frame', asset: image('ast_greenhouse_end', 'garden-square', 'generation', '2026-10-13T09:00:00Z'), position_s: null }
    ],
    outputs: [],
    progress: null,
    error: 'The worker ran out of GPU memory.',
    project_id: null,
    tag_ids: [],
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
    progress: null,
    error: null,
    project_id: null,
    tag_ids: [],
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
    outputs: [video('ast_morph', 'portrait-warm', 8, 'generation', '2026-10-13T16:05:00Z')],
    progress: null,
    error: null,
    project_id: 'prj_film',
    tag_ids: ['tag_keep'],
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
    outputs: [image('ast_room_edit', 'room-photo', 'generation', '2026-10-13T11:00:30Z')],
    progress: null,
    error: null,
    project_id: 'prj_mood',
    tag_ids: [],
    created_at: '2026-10-13T11:00:00Z',
    finished_at: '2026-10-13T11:00:30Z'
  },
  {
    id: 'gen_road',
    status: 'done',
    capability: 'video.generate',
    workflow_id: 'ltx-2.5-t2v',
    prompt: 'an old jeep on an empty road at dusk, low angle, film grain',
    params: { ...videoParams, seed: 901 },
    inputs: [],
    outputs: [roadClip],
    progress: null,
    error: null,
    project_id: 'prj_film',
    tag_ids: ['tag_keep'],
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
    outputs: [
      image('ast_greenhouse_1', 'garden-square', 'generation', '2026-10-11T15:00:20Z'),
      image('ast_greenhouse_2', 'garden-square', 'generation', '2026-10-11T15:00:20Z')
    ],
    progress: null,
    error: null,
    project_id: 'prj_mood',
    tag_ids: [],
    created_at: '2026-10-11T15:00:00Z',
    finished_at: '2026-10-11T15:00:20Z'
  },
  {
    id: 'gen_portrait',
    status: 'done',
    capability: 'image.generate',
    workflow_id: 'illustrious-t2i',
    prompt: 'portrait of a woman in a red coat, warm backlight',
    params: { ...imageParams, seed: 12 },
    inputs: [],
    outputs: [portrait],
    progress: null,
    error: null,
    project_id: 'prj_film',
    tag_ids: ['tag_portrait'],
    created_at: '2026-10-11T09:00:00Z',
    finished_at: '2026-10-11T09:01:00Z'
  }
];

/** One draft per output type, so both composer modes show realistic attachments and a route. */
export const composerDrafts: Record<MediaType, ComposerDraft> = {
  image: {
    prompt: '',
    inputs: [{ role: 'edit_target', asset: room, position_s: null }],
    params: { ...imageParams, aspect_ratio: '4:3' },
    workflow_id: 'flux-klein-9b-edit'
  },
  video: {
    prompt: 'she smiles as the wind catches her hair',
    inputs: [{ role: 'start_frame', asset: portrait, position_s: null }],
    params: { ...videoParams, aspect_ratio: '3:4' },
    workflow_id: 'ltx-2.5-i2v'
  }
};
