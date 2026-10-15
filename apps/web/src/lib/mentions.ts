import type { MediaType } from './types';

/**
 * "@photo2" or "@clip1": what the prompt calls the attachment at index, given the kinds of all of them in order.
 * Photos and clips are numbered separately, in the order they were attached, as the API reads them.
 */
export function handleOf(kinds: MediaType[], index: number): string {
  const kind = kinds[index];
  const number = kinds.slice(0, index + 1).filter(k => k === kind).length;
  return `@${kind === 'image' ? 'photo' : 'clip'}${number}`;
}

/** Splits a prompt around its handles; with the capture group, every odd part is a handle. */
export const mentionPattern = /(@(?:photo|clip)\d+)/;
