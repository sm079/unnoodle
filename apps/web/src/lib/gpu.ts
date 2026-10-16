// The rented GPU in words, for people waiting on it (the API's /gpu).

import type { Gpu } from './types';

/** Why a queued generation of this pipeline waits on the GPU, in words, or null when it only waits its turn. */
export function gpuWait(gpu: Gpu | undefined | null, pipeline: string): { words: string; resting: boolean } | null {
  if (!gpu || gpu.state === 'off' || gpu.ready.includes(pipeline)) return null;
  if (gpu.state === 'resting') return { words: 'The GPU is resting until tomorrow', resting: true };
  if (gpu.phase === 'waiting-for-gpu') return { words: 'Waiting for a free GPU', resting: false };
  const eta = gpu.eta_s[pipeline];
  if (gpu.state === 'asleep' || eta === undefined) return { words: 'Starting the GPU', resting: false };
  const minutes = Math.max(1, Math.round(eta / 60));
  return { words: `Starting the GPU · about ${minutes} min`, resting: false };
}
