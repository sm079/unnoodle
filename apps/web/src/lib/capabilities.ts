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

// The roles attached inputs take, in the order they are added; the last one repeats
const inputRoles: Record<Capability, InputRole[]> = {
  'image.generate': ['reference'],
  'image.edit': ['edit_target', 'reference'],
  'image.restyle': ['restyle', 'reference'],
  'image.multi_ref': ['reference'],
  'video.generate': ['reference'],
  'video.from_frame': ['start_frame', 'reference'],
  'video.first_last': ['start_frame', 'end_frame'],
  'video.keyframes': ['keyframe'],
  'video.reference': ['reference'],
  'video.character_swap': ['source_video', 'reference']
};

export function roleFor(capability: Capability, index: number): InputRole {
  const roles = inputRoles[capability];
  return roles[Math.min(index, roles.length - 1)];
}
