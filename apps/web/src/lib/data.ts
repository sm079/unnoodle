'use client';

// The API data the app reads, cached in the browser with SWR, so the composer, the gallery and the hero share one copy.

import useSWR, { useSWRConfig } from 'swr';
import { paths, request } from './api';
import type { Asset, Generation, Workflow } from './types';

export function useWorkflows() {
  // They only change when the API restarts
  return useSWR(paths.workflows, path => request<Workflow[]>(path), { revalidateOnFocus: false });
}

export function useUploads() {
  return useSWR(paths.uploads, path => request<Asset[]>(path));
}

export const isActive = (g: Generation) => g.status === 'queued' || g.status === 'running';

export function useGenerations() {
  return useSWR(paths.generations, path => request<Generation[]>(path), {
    // Every second while something is queued or running, so progress moves; otherwise only when the tab regains focus
    refreshInterval: generations => (generations?.some(isActive) ? 1000 : 0)
  });
}

/** Adds what was just created to the cached lists right away, then checks them against the API. */
export function useAddToCache() {
  const { mutate } = useSWRConfig();
  return {
    generation: (generation: Generation) =>
      mutate<Generation[]>(paths.generations, current => [generation, ...(current ?? [])], { revalidate: true }),
    upload: () => mutate(paths.uploads)
  };
}
