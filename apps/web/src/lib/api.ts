// Calls to the API, which the web app passes through under /api (see next.config.ts).

import type { AdminUser, Asset, Credits, Generation, GenerationRequest, Invite, InviteRequest, Preferences, Project, User } from './types';

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
  if (response.status === 401 && !path.startsWith('/auth/')) signIn();
  if (!response.ok) throw new ApiError(await reason(response), response.status);
  // Sign out answers with no body
  return (response.status === 204 ? undefined : await response.json()) as T;
}

/** Sends someone whose session has ended to sign in, and back here afterwards. */
function signIn() {
  const here = window.location.pathname + window.location.search;
  // A full load: this runs outside React, with no router to hand, and the cached data belongs to the ended session
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.assign(`/sign-in?next=${encodeURIComponent(here)}`);
}

function json(method: string, body: unknown): RequestInit {
  return { method, headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) };
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

/** What to tell the user when a call failed. */
export function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : 'Something went wrong. Try again.';
}

export const api = {
  upload(file: File): Promise<Asset> {
    const body = new FormData();
    body.append('file', file);
    return request('/assets', { method: 'POST', body });
  },

  /** Queues params.count generations and returns them, oldest first. */
  createGeneration(body: GenerationRequest): Promise<Generation[]> {
    return request('/generations', json('POST', body));
  },

  /** Changes the settings given and returns them all. Admins only. */
  updatePreferences(changes: Partial<Preferences>): Promise<Preferences> {
    return request('/preferences', json('PATCH', changes));
  },

  createProject(name: string): Promise<Project> {
    return request('/projects', json('POST', { name }));
  },

  /** Makes an account and signs in to it. */
  signUp(email: string, password: string): Promise<User> {
    return request('/auth/sign-up', json('POST', { email, password }));
  },

  signIn(email: string, password: string): Promise<User> {
    return request('/auth/sign-in', json('POST', { email, password }));
  },

  signOut(): Promise<void> {
    return request('/auth/sign-out', { method: 'POST' });
  },

  /** Adds an invite code's credits, and returns the new balance. */
  redeem(code: string): Promise<Credits> {
    return request('/credits/redeem', json('POST', { code }));
  },

  // Admins only

  deleteGeneration(id: string): Promise<void> {
    return request(`/admin/generations/${encodeURIComponent(id)}`, { method: 'DELETE' });
  },

  /** Gives credits, or takes them back with a negative amount. */
  grant(userId: string, amount: number, note: string | null): Promise<AdminUser> {
    return request(`/admin/users/${encodeURIComponent(userId)}/credits`, json('POST', { amount, note }));
  },

  createInvite(invite: InviteRequest): Promise<Invite> {
    return request('/admin/invite-codes', json('POST', invite));
  },

  /** Each returns the whole list after the change. */
  addBannedWord(word: string): Promise<string[]> {
    return request('/admin/banned-words', json('POST', { word }));
  },

  removeBannedWord(word: string): Promise<string[]> {
    return request(`/admin/banned-words/${encodeURIComponent(word)}`, { method: 'DELETE' });
  }
};

// Paths the data hooks read, which also name their cache entries
export const paths = {
  pipelines: '/pipelines',
  uploads: '/assets',
  generations: '/generations',
  projects: '/projects',
  preferences: '/preferences',
  me: '/auth/me',
  credits: '/credits',
  admin: {
    generations: '/admin/generations',
    users: '/admin/users',
    invites: '/admin/invite-codes',
    words: '/admin/banned-words'
  }
} as const;

/** The generations in one project, or every generation (My generations) for null. */
export const generationsIn = (projectId: string | null) =>
  projectId === null ? paths.generations : `${paths.generations}?project_id=${encodeURIComponent(projectId)}`;
