'use client';

// The API data the app reads, cached in the browser with SWR, so the composer, the gallery and the hero share one copy.

import useSWR, { useSWRConfig } from 'swr';
import { generationsIn, paths, request } from './api';
import type { Asset, Generation, Project, Workflow } from './types';

export function useWorkflows() {
  // They only change when the API restarts
  return useSWR(paths.workflows, path => request<Workflow[]>(path), { revalidateOnFocus: false });
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

/** Adds what was just created to the cached lists right away, then checks them against the API. */
export function useAddToCache() {
  const { mutate } = useSWRConfig();
  const prepend = (path: string, generation: Generation) =>
    mutate<Generation[]>(path, current => [generation, ...(current ?? [])], { revalidate: true });
  return {
    generation: (generation: Generation) => {
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
