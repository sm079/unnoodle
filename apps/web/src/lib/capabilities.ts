import type { Asset, Capability, InputRole, MediaType } from './types';

export const capabilityLabels: Record<Capability, string> = {
  'image.generate': 'Text to image',
  'image.edit': 'Edit image',
  'image.restyle': 'Restyle image',
  'image.multi_ref': 'Image from references',
  'video.generate': 'Text to video',
  'video.from_frame': 'Video from frame',
  'video.first_last': 'Video from first and last frame',
  'video.keyframes': 'Video from keyframes',
  'video.reference': 'Video from reference',
  'video.character_swap': 'Character swap'
};

export const roleLabels: Record<InputRole, string> = {
  start_frame: 'Start frame',
  end_frame: 'End frame',
  keyframe: 'Keyframe',
  reference: 'Reference',
  edit_target: 'Edit',
  restyle: 'Restyle',
  source_video: 'Source video'
};

export function outputType(capability: Capability): MediaType {
  return capability.startsWith('video.') ? 'video' : 'image';
}

/**
 * The role a newly attached input starts with, given the roles already taken. It covers the common case, a start
 * then an end frame for video, or an image to edit then references, and the role chip changes it.
 */
export function defaultRole(mode: MediaType, taken: InputRole[], asset: Asset): InputRole {
  if (mode === 'image') return taken.includes('edit_target') ? 'reference' : 'edit_target';
  if (asset.media_type === 'video') return 'source_video';
  if (taken.includes('source_video')) return 'reference';
  if (!taken.includes('start_frame')) return 'start_frame';
  if (!taken.includes('end_frame')) return 'end_frame';
  return 'reference';
}
