import { describe, expect, test } from 'vitest';
import { rollDirection } from './motion';

describe('rollDirection', () => {
  test.each([
    [1, 2, 1],
    [4, 3, -1],
    ['720p', '1080p', 1],
    ['10s', '5s', -1],
    ['2K', '2K', 1]
  ])('rolls %s to %s in direction %i', (previous, next, direction) => {
    expect(rollDirection(previous, next)).toBe(direction);
  });

  test('rolls text that is not a number up', () => {
    expect(rollDirection('Auto', 'Golden hour')).toBe(1);
    expect(rollDirection('Golden hour', 'Auto')).toBe(1);
    expect(rollDirection('Off', 'On')).toBe(1);
  });
});
