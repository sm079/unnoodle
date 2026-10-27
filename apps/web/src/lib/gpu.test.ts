import { describe, expect, it } from 'vitest';
import { gpuWait } from './gpu';
import type { Gpu } from './types';

const gpu = (fields: Partial<Gpu>): Gpu => ({ state: 'starting', phase: null, ready: [], eta_s: {}, ...fields });

describe('gpuWait', () => {
  it('says nothing when the GPU can already run it, or none is rented here', () => {
    expect(gpuWait(undefined, 'krea2-turbo')).toBeNull();
    expect(gpuWait(gpu({ state: 'off' }), 'krea2-turbo')).toBeNull();
    expect(gpuWait(gpu({ state: 'starting', ready: ['krea2-turbo'] }), 'krea2-turbo')).toBeNull();
  });

  it('gives the minutes left for this pipeline while the GPU starts', () => {
    expect(gpuWait(gpu({ eta_s: { 'krea2-turbo': 20 } }), 'krea2-turbo')?.words).toBe('Starting the GPU · about 1 min');
  });

  it('says what it gets ready once the GPU is up and running something else', () => {
    const up = gpu({ phase: 'models:flux2-klein-edit', ready: ['krea2-turbo'], eta_s: { 'minimax-h3': 170 } });
    expect(gpuWait(up, 'minimax-h3')).toEqual({ words: 'Getting ready for videos · about 3 min', resting: false });
    expect(gpuWait(up, 'flux2-klein-edit')?.words).toBe('Getting ready for edits');
  });

  it('says when it waits for a free GPU, or for tomorrow', () => {
    expect(gpuWait(gpu({ phase: 'waiting-for-gpu' }), 'krea2-turbo')?.words).toBe('Waiting for a free GPU');
    expect(gpuWait(gpu({ state: 'asleep' }), 'krea2-turbo')?.words).toBe('Starting the GPU');
    expect(gpuWait(gpu({ state: 'resting' }), 'krea2-turbo')).toEqual({ words: 'The GPU is resting until tomorrow', resting: true });
  });
});
