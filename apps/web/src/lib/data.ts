'use client';

// The API data the app reads, cached in the browser with SWR, so the composer, the gallery and the hero share one copy.

import useSWR, { useSWRConfig } from 'swr';
import { api, generationsIn, paths, request } from './api';
import type { Asset, Credits, Generation, Gpu, Preferences, Project, User, Pipeline } from './types';

export function usePipelines() {
  // They only change when the API restarts
  return useSWR(paths.pipelines, path => request<Pipeline[]>(path), { revalidateOnFocus: false });
}

export function useUploads() {
  return useSWR(paths.uploads, path => request<Asset[]>(path));
}

export const isActive = (g: Generation) => g.status === 'queued' || g.status === 'running';

export function useProjects() {
  return useSWR(paths.projects, path => request<Project[]>(path));
}

/** One project's generations, or all of them (My generations) for null. */
export function useGenerations(projectId: string | null = null) {
  return useSWR(generationsIn(projectId), path => request<Generation[]>(path), {
    // Every second while something is queued or running, so progress moves; otherwise only when the tab regains focus
    refreshInterval: generations => (generations?.some(isActive) ? 1000 : 0)
  });
}

/** The signed-in account. */
export function useMe() {
  return useSWR(paths.me, path => request<User>(path), { revalidateOnFocus: false });
}

/** The balance and the prices. Checked again while something is waiting, since a failed one gives its credits back. */
export function useCredits() {
  const { data: generations } = useGenerations();
  return useSWR(paths.credits, path => request<Credits>(path), {
    refreshInterval: generations?.some(isActive) ? 3000 : 0
  });
}

/** Where the rented GPU is, for anyone waiting on it. Checked every few seconds while something of theirs waits and
 * the GPU isn't fully up; otherwise only when asked. */
export function useGpu() {
  const { data: generations } = useGenerations();
  const waiting = generations?.some(isActive) ?? false;
  return useSWR(paths.gpu, path => request<Gpu>(path), {
    refreshInterval: gpu => (waiting && gpu?.state !== 'ready' && gpu?.state !== 'off' ? 3000 : 0)
  });
}

export function usePreferences() {
  const swr = useSWR(paths.preferences, path => request<Preferences>(path));
  return {
    ...swr,
    /** Shows the change at once and puts it back if the API refuses it. */
    update: (changes: Partial<Preferences>) =>
      swr.mutate(api.updatePreferences(changes), {
        optimisticData: current => ({ smart_queue: false, ...current, ...changes }),
        rollbackOnError: true,
        revalidate: false
      })
  };
}

/** Adds what was just created to the cached lists right away, then checks them against the API. */
export function useAddToCache() {
  const { mutate } = useSWRConfig();
  const prepend = (path: string, generation: Generation) =>
    mutate<Generation[]>(path, current => [generation, ...(current ?? [])], { revalidate: true });
  return {
    generation: (generation: Generation) => {
      // It was paid for
      void mutate(paths.credits);
      // It is in My generations, and in its project if it has one, whose count has changed
      void prepend(paths.generations, generation);
      if (generation.project_id !== null) {
        void prepend(generationsIn(generation.project_id), generation);
        void mutate(paths.projects);
      }
    },
    project: (project: Project) => mutate<Project[]>(paths.projects, current => [project, ...(current ?? [])], { revalidate: false }),
    upload: () => mutate(paths.uploads)
  };
}
