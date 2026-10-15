import type { Capability, InputRole, MediaType } from './types';

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
