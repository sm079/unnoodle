import type { CSSProperties } from 'react';

// Menu items follow their menu in, a beat apart. Menus open often, so this stays short.
export const menuItemClass = 'motion-safe:animate-rise [--rise-blur:0px] [--rise-distance:6px] [animation-duration:240ms]';

export const menuItemDelay = (index: number): CSSProperties => ({ animationDelay: `${Math.min(index, 6) * 15}ms` });

/** Which way a value rolls when it changes: up (1) when it grows, down (-1) when it shrinks. Text that isn't a number rolls up. */
export function rollDirection(previous: string | number, next: string | number) {
  const [a, b] = [parseFloat(String(previous)), parseFloat(String(next))];
  return Number.isNaN(a) || Number.isNaN(b) || b >= a ? 1 : -1;
}
