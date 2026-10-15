import { describe, expect, test } from 'vitest';
import { capabilityFor, chooseWorkflow, route, type Attached } from './routing';
import type { Capability, MediaType, Workflow } from './types';

// The same cases as the API's tests/test_routing.py, which decides for real

const refPhoto: Attached = ['reference', 'image'];
const refClip: Attached = ['reference', 'video'];

describe('capabilityFor', () => {
  test.each<[MediaType, Attached[], Capability]>([
    ['image', [], 'image.generate'],
    ['image', [refPhoto], 'image.edit'],
    ['image', [refPhoto, refPhoto, refPhoto], 'image.edit'],
    ['image', [refClip], 'image.edit'],
    ['video', [], 'video.generate'],
    ['video', [refPhoto], 'video.reference'],
    ['video', [refClip, refPhoto], 'video.reference']
  ])('%s from %j is %s', (mediaType, inputs, capability) => {
    expect(capabilityFor(mediaType, inputs)).toEqual({ ok: true, value: capability });
  });
});

function workflow(id: string, capabilities: Capability[], fields: Partial<Workflow> = {}): Workflow {
  return {
    id,
    capabilities,
    model: 'test',
    model_name: 'Test',
    description: '',
    default_for: capabilities,
    aspect_ratios: ['1:1'],
    max_count: 1,
    durations_s: [],
    sound: false,
    accepts: [],
    ...fields
  };
}

const catalogue = [
  workflow('t2i', ['image.generate']),
  workflow('other', ['image.generate'], { model: 'other', default_for: [] }),
  workflow('edit', ['image.edit'], { accepts: [{ role: 'reference', media_type: 'image', most: 3 }] }),
  workflow('video', ['video.generate', 'video.reference'], {
    durations_s: [5, 10],
    accepts: [
      { role: 'reference', media_type: 'image', most: 2 },
      { role: 'reference', media_type: 'video', most: 1 }
    ]
  })
];

describe('chooseWorkflow', () => {
  test('a request without a model gets the default', () => {
    expect(chooseWorkflow(catalogue, 'image.generate', null)).toMatchObject({ value: { id: 't2i' } });
    expect(chooseWorkflow(catalogue, 'video.reference', null)).toMatchObject({ value: { id: 'video' } });
  });

  test('a named model picks its workflow', () => {
    expect(chooseWorkflow(catalogue, 'image.generate', 'other')).toMatchObject({ value: { id: 'other' } });
  });

  test('a model that cannot do the capability is refused', () => {
    expect(chooseWorkflow(catalogue, 'image.edit', 'other')).toEqual({
      ok: false,
      error: "Making a picture from photos isn't available with that model"
    });
  });

  test('a capability without workflows is refused', () => {
    expect(chooseWorkflow(catalogue.slice(0, 1), 'video.generate', null)).toEqual({
      ok: false,
      error: "Making a video isn't available yet"
    });
  });
});

test('route checks the inputs fit the workflow', () => {
  expect(route(catalogue, 'image', [refPhoto, refPhoto, refPhoto], null)).toMatchObject({ value: { id: 'edit' } });
  expect(route(catalogue, 'image', [refPhoto, refPhoto, refPhoto, refPhoto], null)).toEqual({
    ok: false,
    error: 'Making a picture from photos takes at most 3 photos'
  });
  expect(route(catalogue, 'image', [refPhoto, refClip], null)).toEqual({
    ok: false,
    error: "Making a picture from photos can't use clips"
  });
  expect(route(catalogue, 'video', [refClip, refClip], null)).toEqual({ ok: false, error: 'Making a video takes at most 1 clip' });
});
