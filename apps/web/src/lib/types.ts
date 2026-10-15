// The shapes the API returns. The mock fixtures use them today; once the API serves real data they will be
// generated from its OpenAPI schema instead. Field names are snake_case to match the JSON on the wire.

export type MediaType = 'image' | 'video';

export type Capability =
  | 'image.generate'
  | 'image.edit'
  | 'image.restyle'
  | 'image.multi_ref'
  | 'video.generate'
  | 'video.from_frame'
  | 'video.first_last'
  | 'video.keyframes'
  | 'video.reference'
  | 'video.character_swap';

/** What an attached asset is for. The output type plus the roles of the inputs decide the capability. */
export type InputRole = 'start_frame' | 'end_frame' | 'keyframe' | 'reference' | 'edit_target' | 'restyle' | 'source_video';

export type GenerationStatus = 'queued' | 'running' | 'failed' | 'done';

export type AspectRatio = '1:1' | '4:3' | '3:4' | '16:9' | '9:16';

export interface Asset {
  id: string;
  media_type: MediaType;
  source: 'upload' | 'generation';
  url: string;
  /** A still for grids. The same as url for images. */
  thumbnail_url: string;
  width: number;
  height: number;
  /** Videos only. */
  duration_s: number | null;
  created_at: string;
}

export interface GenerationInput {
  role: InputRole;
  asset: Asset;
  /** Seconds into the clip. Keyframe inputs only. */
  position_s: number | null;
}

export interface GenerationParams {
  aspect_ratio: AspectRatio;
  /** Output size as shown on the chip, e.g. '1K' for images or '720p' for video. */
  resolution: string;
  /** Videos only. */
  duration_s: number | null;
  /** Outputs per run. */
  count: number;
  /** null asks for a random seed; finished generations record the one used. */
  seed: number | null;
}

/** A ComfyUI workflow that implements one capability. */
export interface Workflow {
  id: string;
  /** Shown in the route line, e.g. 'LTX 2.5'. */
  name: string;
  capability: Capability;
}

export interface Generation {
  id: string;
  status: GenerationStatus;
  capability: Capability;
  workflow_id: string;
  prompt: string;
  params: GenerationParams;
  inputs: GenerationInput[];
  /** Filled once status is 'done'. */
  outputs: Asset[];
  /** 0 to 1 while running. */
  progress: number | null;
  /** Set when status is 'failed'. */
  error: string | null;
  project_id: string | null;
  tag_ids: string[];
  created_at: string;
  finished_at: string | null;
}

export interface Project {
  id: string;
  name: string;
  created_at: string;
}

export interface Tag {
  id: string;
  name: string;
}

/** What the composer holds before submitting; it becomes the body of a generate request. */
export interface ComposerDraft {
  prompt: string;
  inputs: GenerationInput[];
  params: GenerationParams;
  /** The route the request resolves to. The API will decide this; the fixtures fake it. */
  workflow_id: string;
}
