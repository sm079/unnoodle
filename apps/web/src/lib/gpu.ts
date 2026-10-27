// The rented GPU in words, for people waiting on it (the API's /gpu).

import type { Gpu } from './types';

// What each pipeline makes, for when the GPU is up but still getting this one ready
const KIND: Record<string, string> = { 'krea2-turbo': 'pictures', 'flux2-klein-edit': 'edits', 'minimax-h3': 'videos' };

/** Why a queued generation of this pipeline waits on the GPU, in words, or null when it only waits its turn. */
export function gpuWait(gpu: Gpu | undefined | null, pipeline: string): { words: string; resting: boolean } | null {
  if (!gpu || gpu.state === 'off' || gpu.ready.includes(pipeline)) return null;
  if (gpu.state === 'resting') return { words: 'The GPU is resting until tomorrow', resting: true };
  if (gpu.phase === 'waiting-for-gpu') return { words: 'Waiting for a free GPU', resting: false };
  const eta = gpu.eta_s[pipeline];
  // Once something runs on it, the GPU itself is up: what's left is getting this kind ready
  const doing = gpu.ready.length > 0 && KIND[pipeline] ? `Getting ready for ${KIND[pipeline]}` : 'Starting the GPU';
  if (gpu.state === 'asleep' || eta === undefined) return { words: doing, resting: false };
  const minutes = Math.max(1, Math.round(eta / 60));
  return { words: `${doing} · about ${minutes} min`, resting: false };
}
