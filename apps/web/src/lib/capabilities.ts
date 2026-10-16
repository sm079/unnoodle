import type { AspectRatio, Capability, MediaType, Quality } from './types';

/** What a route does, in the words the route chip shows. */
export const capabilityLabels: Record<Capability, string> = {
  'image.generate': 'Create an image',
  'image.edit': 'Edit an image',
  'video.generate': 'Make a video',
  'video.reference': 'Make a video from references'
};

export const qualityLabels: Record<Quality, string> = { low: 'Low', medium: 'Medium', high: 'High' };

/** The shapes in words. */
export const shapeLabels: Record<AspectRatio, string> = {
  '1:1': 'Square',
  '2:3': 'Portrait photo',
  '3:2': 'Photo',
  '3:4': 'Portrait standard',
  '4:3': 'Standard',
  '9:16': 'Portrait widescreen',
  '16:9': 'Widescreen',
  '21:9': 'Ultrawide'
};

export function outputType(capability: Capability): MediaType {
  return capability.startsWith('video.') ? 'video' : 'image';
}
