// Calls to the API, which the web app passes through under /api (see next.config.ts).

import type { Asset, Generation, GenerationRequest } from './types';

/** A failed call. The message is fit to show: the API's own reason when it gave one. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number
  ) {
    super(message);
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, init);
  } catch {
    throw new ApiError("Can't reach the server. Check your connection.", 0);
  }
  if (!response.ok) throw new ApiError(await reason(response), response.status);
  return (await response.json()) as T;
}

/** The API explains refusals in a "detail": a sentence for its own checks, a list for malformed requests. */
async function reason(response: Response): Promise<string> {
  const body: unknown = await response.json().catch(() => null);
  const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : null;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map(item => String(item?.msg ?? item)).join('; ');
  // A proxy error rather than an answer from the API
  return response.status >= 500 ? "The server isn't answering. Try again in a moment." : `Request failed (${response.status})`;
}

export const api = {
  upload(file: File): Promise<Asset> {
    const body = new FormData();
    body.append('file', file);
    return request('/assets', { method: 'POST', body });
  },

  createGeneration(body: GenerationRequest): Promise<Generation> {
    return request('/generations', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body)
    });
  }
};

// Paths the data hooks read, which also name their cache entries
export const paths = { workflows: '/workflows', uploads: '/assets', generations: '/generations' } as const;
