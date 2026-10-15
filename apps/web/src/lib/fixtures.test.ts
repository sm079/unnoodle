import { describe, expect, test } from 'vitest';
import { outputType } from './capabilities';
import { generations, workflows } from './fixtures';
import { capabilityFor, route, type Attached } from './routing';
import type { Capability, GenerationStatus, MediaType } from './types';

// The UI is tuned against these fixtures and the end-to-end tests serve them, so they keep the rules the API enforces

const workflowById = new Map(workflows.map(w => [w.id, w]));

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

  test.each(generations)('$id routes to its workflow and outputs its media type', g => {
    const workflow = workflowById.get(g.workflow_id)!;
    expect(workflow.capabilities).toContain(g.capability);
    const attached = g.inputs.map((i): Attached => [i.role, i.asset.media_type]);
    expect(capabilityFor(outputType(g.capability), attached)).toEqual({ ok: true, value: g.capability });
    expect(route(workflows, outputType(g.capability), attached, workflow.model)).toEqual({ ok: true, value: workflow });
    for (const output of g.outputs) {
      expect(output.media_type).toBe(outputType(g.capability));
      expect(output.source).toBe('generation');
    }
  });

  test.each(generations)('$id only uses settings its workflow offers', g => {
    const workflow = workflowById.get(g.workflow_id)!;
    if (g.params.aspect_ratio === null) expect(workflow.aspect_ratios).toEqual([]);
    else expect(workflow.aspect_ratios).toContain(g.params.aspect_ratio);
    if (g.params.duration_s === null) expect(workflow.durations_s).toEqual([]);
    else expect(workflow.durations_s).toContain(g.params.duration_s);
    expect(g.params.count).toBeLessThanOrEqual(workflow.max_count);
  });

  test('are newest first', () => {
    const times = generations.map(g => g.created_at);
    expect(times).toEqual([...times].sort().reverse());
  });
});

describe('workflows', () => {
  test.each(workflows)('$id offers settings for its output type', ({ capabilities, durations_s, sound }) => {
    const video = outputType(capabilities[0]) === 'video';
    expect(durations_s.length > 0).toBe(video);
    if (!video) expect(sound).toBe(false);
  });

  test('each capability has one default', () => {
    const capabilities = new Set<Capability>(workflows.flatMap(w => w.capabilities));
    for (const capability of capabilities) {
      expect(workflows.filter(w => w.default_for.includes(capability))).toHaveLength(1);
    }
  });
});
