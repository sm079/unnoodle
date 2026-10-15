// Which workflow a request runs on, worked out in the composer so it can show the route before anything is sent. The
// API decides for real (apps/api/app/routing.py); this follows the same rules, and routing.test.ts runs the same cases
// as the API's tests.

import type { Capability, InputRole, MediaType, Workflow } from './types';

/** The roles an input can take for each output type, in the order a role picker lists them. */
export const rolesFor: Record<MediaType, InputRole[]> = {
  image: ['edit_target', 'restyle', 'reference'],
  video: ['start_frame', 'end_frame', 'keyframe', 'reference', 'source_video']
};

/** Either where a request goes, or why it can't go anywhere, in words for the person sending it. */
export type Routed<T> = { ok: true; value: T } | { ok: false; error: string };

const aMedia: Record<MediaType, string> = { image: 'an image', video: 'a video' };

export function route(workflows: Workflow[], mediaType: MediaType, roles: InputRole[], model: string | null): Routed<Workflow> {
  const capability = capabilityFor(mediaType, roles);
  if (!capability.ok) return capability;
  const chosen = chooseWorkflow(workflows, capability.value, model);
  if (!chosen.ok) return chosen;
  for (const [role, count] of counted(roles)) {
    const most = chosen.value.roles[role] ?? 0;
    if (count > most) return failed(`${chosen.value.model_name} takes at most ${inputsPhrase(role, most)}`);
  }
  return chosen;
}

export function capabilityFor(mediaType: MediaType, roles: InputRole[]): Routed<Capability> {
  const counts = counted(roles);
  const present = [...counts.keys()];
  const only = (...allowed: InputRole[]) => present.every(role => allowed.includes(role));
  const exactly = (expected: Partial<Record<InputRole, number>>) =>
    counts.size === Object.keys(expected).length &&
    Object.entries(expected).every(([role, count]) => counts.get(role as InputRole) === count);
  const found = (capability: Capability): Routed<Capability> => ({ ok: true, value: capability });

  const misplaced = present.find(role => !rolesFor[mediaType].includes(role));
  if (misplaced) return failed(`${capitalize(article(words(misplaced)))} can't be used to make ${aMedia[mediaType]}`);

  if (mediaType === 'image') {
    if (present.length === 0) return found('image.generate');
    if (counts.get('edit_target') === 1 && only('edit_target', 'reference')) return found('image.edit');
    if (exactly({ restyle: 1 })) return found('image.restyle');
    if (only('reference')) return found('image.multi_ref');
  } else {
    if (present.length === 0) return found('video.generate');
    if (exactly({ start_frame: 1 })) return found('video.from_frame');
    if (exactly({ start_frame: 1, end_frame: 1 })) return found('video.first_last');
    if (only('keyframe')) return found('video.keyframes');
    if (only('reference')) return found('video.reference');
    if (exactly({ source_video: 1, reference: 1 })) return found('video.character_swap');
  }
  const inputs = [...counts].map(([role, count]) => inputsPhrase(role, count)).join(' and ');
  return failed(`Nothing makes ${aMedia[mediaType]} from ${inputs}`);
}

export function chooseWorkflow(workflows: Workflow[], capability: Capability, model: string | null): Routed<Workflow> {
  const offering = workflows.filter(w => w.capability === capability);
  if (offering.length === 0) return failed(`No workflow does ${capability} yet`);
  const workflow = model === null ? (offering.find(w => w.default) ?? offering[0]) : offering.find(w => w.model === model);
  if (workflow) return { ok: true, value: workflow };
  const available = offering
    .map(w => w.model)
    .sort()
    .join(', ');
  return failed(`${model} doesn't do ${capability}; these do: ${available}`);
}

/** Counts each role, in the order the roles first appear, as the API's messages list them. */
function counted(roles: InputRole[]): Map<InputRole, number> {
  const counts = new Map<InputRole, number>();
  for (const role of roles) counts.set(role, (counts.get(role) ?? 0) + 1);
  return counts;
}

const failed = (error: string): { ok: false; error: string } => ({ ok: false, error });

const words = (role: InputRole) => role.replaceAll('_', ' ');

const inputsPhrase = (role: InputRole, count: number) => `${count} ${words(role)}${count === 1 ? '' : 's'}`;

const article = (noun: string) => `${/^[aeiou]/.test(noun) ? 'an' : 'a'} ${noun}`;

const capitalize = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);
