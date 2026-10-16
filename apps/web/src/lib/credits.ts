// What a request costs, so Generate can say before it's pressed. The API charges for real (apps/api/app/credits.py,
// cost_of); this follows the same table, which the API sends with the balance. Change both together.

import type { MediaType, Prices, Quality } from './types';

/** The credits one generation takes; "how many" queues that many, each charged this. */
export function costOf(prices: Prices, mediaType: MediaType, quality: Quality, durationS: number | null, clips: number): number {
  if (mediaType === 'image') return prices.image[quality] ?? 0;
  return (prices.video_per_5s[quality] ?? 0) * Math.ceil((durationS ?? 5) / 5) + prices.per_clip * clips;
}
