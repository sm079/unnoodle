import { describe, expect, test } from 'vitest';
import { offsetOf, restAt, swipeStep } from './fan';

describe('offsetOf', () => {
  test.each([2, 3, 5, 6, 7])('gives %i cards one offset each, with the front card at 0', count => {
    for (let front = 0; front < count; front++) {
      const offsets = Array.from({ length: count }, (_, index) => offsetOf(index, front, count));
      expect(new Set(offsets).size).toBe(count);
      expect(offsets[front]).toBe(0);
    }
  });

  test('puts the neighbours either side of the front card', () => {
    expect(offsetOf(4, 0, 5)).toBe(-1);
    expect(offsetOf(1, 0, 5)).toBe(1);
    expect(offsetOf(0, 4, 5)).toBe(1);
  });

  test('keeps as many cards waiting on the left as on the right', () => {
    const offsets = Array.from({ length: 5 }, (_, index) => offsetOf(index, 2, 5));
    expect(offsets.filter(offset => offset < 0)).toHaveLength(2);
    expect(offsets.filter(offset => offset > 0)).toHaveLength(2);
  });
});

describe('restAt', () => {
  test('shows the front card and its two neighbours, smaller toward the sides', () => {
    expect(restAt(0)).toEqual({ x: 0, scale: 1, opacity: 1 });
    expect(restAt(-1)).toEqual({ x: -1, scale: 0.7, opacity: 1 });
    expect(restAt(1)).toEqual({ x: 1, scale: 0.7, opacity: 1 });
  });

  test('hides the rest just past the neighbour on their side', () => {
    for (const offset of [-3, -2, 2, 3]) {
      const rest = restAt(offset);
      expect(rest.opacity).toBe(0);
      expect(Math.sign(rest.x)).toBe(Math.sign(offset));
      expect(Math.abs(rest.x)).toBeGreaterThan(1);
    }
  });
});

describe('swipeStep', () => {
  test('stays put for a short, slow drag', () => {
    expect(swipeStep(-0.2, -0.1)).toBe(0);
    expect(swipeStep(0.2, 0.1)).toBe(0);
  });

  test('moves on once the drag passes about a third of the way', () => {
    expect(swipeStep(-0.5, 0)).toBe(1);
    expect(swipeStep(0.5, 0)).toBe(-1);
  });

  test('follows a flick even when the drag was short', () => {
    expect(swipeStep(-0.1, -0.8)).toBe(1);
    expect(swipeStep(0.1, 0.8)).toBe(-1);
  });

  test('lets a flick back win over the distance dragged', () => {
    expect(swipeStep(-0.6, 0.8)).toBe(-1);
  });
});
