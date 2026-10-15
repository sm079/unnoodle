import { describe, expect, test } from 'vitest';
import { outputType } from './capabilities';
import { composerDrafts, generations, projects, tags, workflows } from './fixtures';
import type { GenerationStatus, MediaType } from './types';

// The UI is tuned against these fixtures, so they have to keep the rules the API will enforce.

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

  test.each(generations)('$id runs a workflow for its capability and outputs its media type', g => {
    expect(workflowById.get(g.workflow_id)?.capability).toBe(g.capability);
    for (const output of g.outputs) {
      expect(output.media_type).toBe(outputType(g.capability));
      expect(output.source).toBe('generation');
    }
  });

  test.each(generations)('$id gives a position to keyframes only', g => {
    for (const input of g.inputs) {
      expect(input.position_s !== null).toBe(input.role === 'keyframe');
    }
  });

  test('reference projects and tags that exist', () => {
    const projectIds = new Set(projects.map(p => p.id));
    const tagIds = new Set(tags.map(t => t.id));
    for (const g of generations) {
      if (g.project_id !== null) expect(projectIds).toContain(g.project_id);
      for (const id of g.tag_ids) expect(tagIds).toContain(id);
    }
  });

  test('are newest first', () => {
    const times = generations.map(g => g.created_at);
    expect(times).toEqual([...times].sort().reverse());
  });
});

test.each(Object.entries(composerDrafts))('the %s draft routes to a workflow for that output type', (mode, draft) => {
  const workflow = workflowById.get(draft.workflow_id);
  expect(workflow).toBeDefined();
  expect(outputType(workflow!.capability)).toBe(mode);
});

test.each([...generations, ...Object.values(composerDrafts)].map(g => ({ id: 'id' in g ? g.id : `${g.workflow_id} draft`, g })))(
  '$id only uses settings its workflow offers',
  ({ g }) => {
    const { options } = workflowById.get(g.workflow_id)!;
    expect(options.aspect_ratios).toContain(g.params.aspect_ratio);
    expect(options.resolutions).toContain(g.params.resolution);
    if (g.params.duration_s === null) expect(options.durations_s).toEqual([]);
    else expect(options.durations_s).toContain(g.params.duration_s);
    expect(g.params.count).toBeLessThanOrEqual(options.max_count);
    expect(g.inputs.length).toBeLessThanOrEqual(options.max_inputs);
  }
);

test.each(workflows)('$id offers settings for its output type', ({ capability, options }) => {
  const video = outputType(capability) === 'video';
  expect(options.durations_s.length > 0).toBe(video);
  if (!video) expect(options.audio).toBe(false);
});
