// Which workflow a request runs on, worked out in the composer so it can show the route before anything is sent. The
// API decides for real (apps/api/app/routing.py); this follows the same rules with the same messages, and
// routing.test.ts runs the same cases as the API's tests.

import type { Capability, InputRole, MediaType, Workflow } from './types';

// The order a role picker lists them in
const roleOrder: InputRole[] = ['edit_target', 'reference'];

/** The roles a photo or clip can take for an output type: those some workflow making that type accepts it in. */
export function rolesFor(workflows: Workflow[], outputType: MediaType, mediaType: MediaType): InputRole[] {
  const accepted = workflows
    .filter(w => w.capabilities.some(c => c.startsWith(`${outputType}.`)))
    .flatMap(w => w.accepts.filter(a => a.media_type === mediaType).map(a => a.role));
  return roleOrder.filter(role => accepted.includes(role));
}

/** An attachment, as routing sees it: its role and whether it is a photo or a clip. */
export type Attached = [role: InputRole, mediaType: MediaType];

/** Either where a request goes, or why it can't go anywhere, in words for the person sending it. */
export type Routed<T> = { ok: true; value: T } | { ok: false; error: string };

const doing: Record<Capability, string> = {
  'image.generate': 'Making a picture',
  'image.edit': 'Editing a photo',
  'video.generate': 'Making a video',
  'video.reference': 'Making a video'
};

export function route(workflows: Workflow[], mediaType: MediaType, inputs: Attached[], model: string | null): Routed<Workflow> {
  const capability = capabilityFor(mediaType, inputs);
  if (!capability.ok) return capability;
  const chosen = chooseWorkflow(workflows, capability.value, model);
  if (!chosen.ok) return chosen;
  for (const [[role, kind], count] of counted(inputs)) {
    const most = chosen.value.accepts.find(a => a.role === role && a.media_type === kind)?.most ?? 0;
    if (count > most) {
      const what = noun(role, kind);
      const doingIt = doing[capability.value];
      return failed(most === 0 ? `${doingIt} can't use ${plural(what)}` : `${doingIt} takes at most ${countOf(most, what)}`);
    }
  }
  return chosen;
}

export function capabilityFor(mediaType: MediaType, inputs: Attached[]): Routed<Capability> {
  const targets = inputs.filter(([role]) => role === 'edit_target');
  const found = (capability: Capability): Routed<Capability> => ({ ok: true, value: capability });
  if (targets.some(([, kind]) => kind === 'video')) return failed('Only a photo can be edited');
  if (mediaType === 'image') {
    if (inputs.length === 0) return found('image.generate');
    if (targets.length > 1) return failed('Only one photo can be the one to edit');
    if (targets.length === 0) return failed('Pick the photo to edit');
    return found('image.edit');
  }
  if (targets.length > 0) return failed("A video can't edit a photo, but it can use one as a reference");
  return found(inputs.length > 0 ? 'video.reference' : 'video.generate');
}

export function chooseWorkflow(workflows: Workflow[], capability: Capability, model: string | null): Routed<Workflow> {
  const offering = workflows.filter(w => w.capabilities.includes(capability));
  if (offering.length === 0) return failed(`${doing[capability]} isn't available yet`);
  const workflow =
    model === null ? (offering.find(w => w.default_for.includes(capability)) ?? offering[0]) : offering.find(w => w.model === model);
  return workflow ? { ok: true, value: workflow } : failed(`${doing[capability]} isn't available with that model`);
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

function noun(role: InputRole, mediaType: MediaType): string {
  if (role === 'edit_target') return 'photo to edit';
  return mediaType === 'image' ? 'reference photo' : 'reference clip';
}

/** "photo to edit" becomes "photos to edit". */
function plural(noun: string): string {
  const [first, rest] = noun.split(' to ');
  return rest ? `${first}s to ${rest}` : `${noun}s`;
}

const countOf = (count: number, noun: string) => `${count} ${count === 1 ? noun : plural(noun)}`;
