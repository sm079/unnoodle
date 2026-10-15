// Geometry of the hero's fanned card stack.

export interface Rest {
  /** Across from the centre, in units of the gap between the front card and a side card. */
  x: number;
  scale: number;
  opacity: number;
}

/** Where a card rests at a given offset from the front card. */
export function restAt(offset: number): Rest {
  const distance = Math.abs(offset);
  if (distance === 0) return { x: 0, scale: 1, opacity: 1 };
  if (distance === 1) return { x: offset, scale: 0.7, opacity: 1 };
  // The rest wait just beyond the side cards, out of sight, so the next one slides in from the edge
  return { x: Math.sign(offset) * 1.35, scale: 0.55, opacity: 0 };
}

/** The card's offset from the front card, with as many cards waiting on the left as on the right. */
export function offsetOf(index: number, front: number, count: number) {
  const behind = Math.floor((count - 1) / 2);
  return ((index - front + count + behind) % count) - behind;
}

/**
 * Which way a released swipe moves the fan: 1 to the next card, -1 to the previous one, 0 to stay. Progress is how far
 * the fan was dragged, in card gaps (negative toward the next card); velocity is in pixels per millisecond.
 */
export function swipeStep(progress: number, velocity: number) {
  // A flick counts even when short; a slow drag has to pass about a third of the way
  if (Math.abs(velocity) > 0.4) return velocity < 0 ? 1 : -1;
  if (Math.abs(progress) > 0.3) return progress < 0 ? 1 : -1;
  return 0;
}
