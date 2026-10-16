// Which pipeline a request runs on, worked out in the composer so it can show the route before anything is sent. The
// API decides for real (apps/api/app/routing.py); this follows the same rules with the same messages, and
// routing.test.ts runs the same cases as the API's tests.

import type { Capability, InputRole, MediaType, Pipeline } from './types';

/** An attachment, as routing sees it: its role and whether it is a photo or a clip. */
export type Attached = [role: InputRole, mediaType: MediaType];

/** Either where a request goes, or why it can't go anywhere, in words for the person sending it. */
export type Routed<T> = { ok: true; value: T } | { ok: false; error: string };

const doing: Record<Capability, string> = {
  'image.generate': 'Creating an image',
  'image.edit': 'Editing an image',
  'video.generate': 'Making a video',
  'video.reference': 'Making a video'
};

export function route(pipelines: Pipeline[], mediaType: MediaType, inputs: Attached[], model: string | null): Routed<Pipeline> {
  const capability = capabilityFor(mediaType, inputs);
  if (!capability.ok) return capability;
  const chosen = choosePipeline(pipelines, capability.value, model);
  if (!chosen.ok) return chosen;
  for (const [[role, kind], count] of counted(inputs)) {
    const most = chosen.value.accepts.find(a => a.role === role && a.media_type === kind)?.most ?? 0;
    if (count > most) {
      const what = kind === 'image' ? 'photo' : 'clip';
      const doingIt = doing[capability.value];
      return failed(most === 0 ? `${doingIt} can't use ${plural(what)}` : `${doingIt} takes at most ${countOf(most, what)}`);
    }
  }
  return chosen;
}

export function capabilityFor(mediaType: MediaType, inputs: Attached[]): Routed<Capability> {
  const attached = inputs.length > 0;
  if (mediaType === 'image') return { ok: true, value: attached ? 'image.edit' : 'image.generate' };
  return { ok: true, value: attached ? 'video.reference' : 'video.generate' };
}

export function choosePipeline(pipelines: Pipeline[], capability: Capability, model: string | null): Routed<Pipeline> {
  const offering = pipelines.filter(w => w.capabilities.includes(capability));
  if (offering.length === 0) return failed(`${doing[capability]} isn't available yet`);
  const pipeline =
    model === null ? (offering.find(w => w.default_for.includes(capability)) ?? offering[0]) : offering.find(w => w.model === model);
  return pipeline ? { ok: true, value: pipeline } : failed(`${doing[capability]} isn't available with that model`);
}

/** Counts each kind of attachment, in the order they first appear, as the API's messages list them. */
function counted(inputs: Attached[]): [Attached, number][] {
  const counts = new Map<string, [Attached, number]>();
  for (const input of inputs) {
    const key = input.join('/');
    counts.set(key, [input, (counts.get(key)?.[1] ?? 0) + 1]);
  }
  return [...counts.values()];
}

const failed = (error: string): { ok: false; error: string } => ({ ok: false, error });

const plural = (noun: string) => `${noun}s`;

const countOf = (count: number, noun: string) => `${count} ${count === 1 ? noun : plural(noun)}`;
