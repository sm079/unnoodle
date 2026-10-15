import { describe, expect, test } from 'vitest';
import { capabilityFor, chooseWorkflow, route } from './routing';
import type { Capability, InputRole, MediaType, Workflow } from './types';

// The same cases as the API's tests/test_routing.py, which decides for real

describe('capabilityFor', () => {
  test.each<[MediaType, InputRole[], Capability]>([
    ['image', [], 'image.generate'],
    ['image', ['edit_target'], 'image.edit'],
    ['image', ['edit_target', 'reference', 'reference'], 'image.edit'],
    ['image', ['reference', 'edit_target'], 'image.edit'],
    ['image', ['restyle'], 'image.restyle'],
    ['image', ['reference'], 'image.multi_ref'],
    ['image', ['reference', 'reference', 'reference'], 'image.multi_ref'],
    ['video', [], 'video.generate'],
    ['video', ['start_frame'], 'video.from_frame'],
    ['video', ['start_frame', 'end_frame'], 'video.first_last'],
    ['video', ['end_frame', 'start_frame'], 'video.first_last'],
    ['video', ['keyframe', 'keyframe', 'keyframe'], 'video.keyframes'],
    ['video', ['reference', 'reference'], 'video.reference'],
    ['video', ['source_video', 'reference'], 'video.character_swap']
  ])('%s from %j is %s', (mediaType, roles, capability) => {
    expect(capabilityFor(mediaType, roles)).toEqual({ ok: true, value: capability });
  });

  test.each<[MediaType, InputRole[], string]>([
    ['image', ['start_frame'], "A start frame can't be used to make an image"],
    ['video', ['edit_target'], "An edit target can't be used to make a video"],
    ['image', ['edit_target', 'edit_target'], 'Nothing makes an image from 2 edit targets'],
    ['image', ['restyle', 'reference'], 'Nothing makes an image from 1 restyle and 1 reference'],
    ['video', ['end_frame'], 'Nothing makes a video from 1 end frame'],
    ['video', ['start_frame', 'start_frame'], 'Nothing makes a video from 2 start frames'],
    ['video', ['start_frame', 'keyframe'], 'Nothing makes a video from 1 start frame and 1 keyframe'],
    ['video', ['source_video'], 'Nothing makes a video from 1 source video']
  ])('%s from %j is refused', (mediaType, roles, message) => {
    expect(capabilityFor(mediaType, roles)).toEqual({ ok: false, error: message });
  });
});

function workflow(id: string, capability: Capability, model: string, isDefault = false, roles: Workflow['roles'] = {}): Workflow {
  const modelName = model.charAt(0).toUpperCase() + model.slice(1);
  return {
    id,
    capability,
    model,
    model_name: modelName,
    description: '',
    default: isDefault,
    resolutions: { '1K': ['1:1'] },
    max_count: 1,
    durations_s: [],
    audio: false,
    roles
  };
}

const catalogue = [
  workflow('anima', 'image.generate', 'anima'),
  workflow('flux-t2i', 'image.generate', 'flux', true),
  workflow('flux-edit', 'image.edit', 'flux', true, { edit_target: 1, reference: 2 })
];

describe('chooseWorkflow', () => {
  test('a request without a model gets the default', () => {
    expect(chooseWorkflow(catalogue, 'image.generate', null)).toMatchObject({ value: { id: 'flux-t2i' } });
    expect(chooseWorkflow(catalogue, 'image.edit', null)).toMatchObject({ value: { id: 'flux-edit' } });
  });

  test('a named model picks its workflow', () => {
    expect(chooseWorkflow(catalogue, 'image.generate', 'anima')).toMatchObject({ value: { id: 'anima' } });
  });

  test('a model that cannot do the capability is refused', () => {
    expect(chooseWorkflow(catalogue, 'image.edit', 'anima')).toEqual({
      ok: false,
      error: "anima doesn't do image.edit; these do: flux"
    });
  });

  test('a capability without workflows is refused', () => {
    expect(chooseWorkflow(catalogue, 'video.generate', null)).toEqual({ ok: false, error: 'No workflow does video.generate yet' });
  });
});

test('route checks the inputs fit the workflow', () => {
  expect(route(catalogue, 'image', ['edit_target', 'reference', 'reference'], null)).toMatchObject({ value: { id: 'flux-edit' } });
  expect(route(catalogue, 'image', ['edit_target', 'reference', 'reference', 'reference'], null)).toEqual({
    ok: false,
    error: 'Flux takes at most 2 references'
  });
});
