import { describe, expect, test } from 'vitest';
import { outputType } from './capabilities';
import { generations, pipelines } from './fixtures';
import { capabilityFor, route, type Attached } from './routing';
import type { Capability, GenerationStatus, MediaType } from './types';

// The UI is tuned against these fixtures and the end-to-end tests serve them, so they keep the rules the API enforces

const pipelineById = new Map(pipelines.map(w => [w.id, w]));

describe('generations', () => {
  test('cover every status, and finished outputs of both types', () => {
    const statuses: GenerationStatus[] = ['queued', 'running', 'failed', 'done'];
    expect(new Set(generations.map(g => g.status))).toEqual(new Set(statuses));

    const doneTypes = generations.filter(g => g.status === 'done').map(g => outputType(g.capability));
    expect(new Set(doneTypes)).toEqual(new Set<MediaType>(['image', 'video']));
  });

  test.each(generations)('$id has fields that match its status', g => {
    expect(g.outputs.length > 0).toBe(g.status === 'done');
    expect(g.progress !== null).toBe(g.status === 'running');
    expect(g.error !== null).toBe(g.status === 'failed');
    expect(g.finished_at !== null).toBe(g.status === 'done' || g.status === 'failed');
  });

  test.each(generations)('$id routes to its pipeline and outputs its media type', g => {
    const pipeline = pipelineById.get(g.pipeline_id)!;
    expect(pipeline.capabilities).toContain(g.capability);
    const attached = g.inputs.map((i): Attached => [i.role, i.asset.media_type]);
    expect(capabilityFor(outputType(g.capability), attached)).toEqual({ ok: true, value: g.capability });
    expect(route(pipelines, outputType(g.capability), attached, pipeline.model)).toEqual({ ok: true, value: pipeline });
    for (const output of g.outputs) {
      expect(output.media_type).toBe(outputType(g.capability));
      expect(output.source).toBe('generation');
    }
  });

  test.each(generations)('$id only uses settings its pipeline offers', g => {
    const pipeline = pipelineById.get(g.pipeline_id)!;
    // No shape means the first attachment's
    if (g.params.aspect_ratio === null) expect(g.inputs.length).toBeGreaterThan(0);
    else expect(pipeline.aspect_ratios).toContain(g.params.aspect_ratio);
    if (g.params.duration_s === null) expect(pipeline.durations_s).toEqual([]);
    else expect(pipeline.durations_s).toContain(g.params.duration_s);
  });

  test('are newest first', () => {
    const times = generations.map(g => g.created_at);
    expect(times).toEqual([...times].sort().reverse());
  });
});

describe('pipelines', () => {
  test.each(pipelines)('$id offers settings for its output type', ({ capabilities, durations_s, sound }) => {
    const video = outputType(capabilities[0]) === 'video';
    expect(durations_s.length > 0).toBe(video);
    if (!video) expect(sound).toBe(false);
  });

  test('each capability has one default', () => {
    const capabilities = new Set<Capability>(pipelines.flatMap(w => w.capabilities));
    for (const capability of capabilities) {
      expect(pipelines.filter(w => w.default_for.includes(capability))).toHaveLength(1);
    }
  });
});
