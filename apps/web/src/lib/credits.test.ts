import { expect, test } from 'vitest';
import { costOf } from './credits';
import type { MediaType, Prices, Quality } from './types';

// The same table and cases as the API's tests/test_credits.py
const prices: Prices = {
  image: { low: 1, medium: 1, high: 2 },
  video_per_5s: { low: 10, medium: 20, high: 40 },
  per_clip: 10
};

test.each<[MediaType, Quality, number | null, number, number]>([
  ['image', 'low', null, 0, 1],
  ['image', 'medium', null, 0, 1],
  ['image', 'high', null, 0, 2],
  ['video', 'low', 5, 0, 10],
  ['video', 'medium', 10, 0, 40],
  ['video', 'high', 15, 0, 120],
  ['video', 'low', 5, 2, 30]
])('%s at %s quality, %s s, %i clips costs %i', (mediaType, quality, durationS, clips, cost) => {
  expect(costOf(prices, mediaType, quality, durationS, clips)).toBe(cost);
});
