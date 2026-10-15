'use client';

import type { ReactNode } from 'react';
import { LazyMotion, MotionConfig, type Transition } from 'motion/react';

const loadFeatures = () => import('@/lib/motion-features').then(module => module.default);

/** Settles quickly with a hint of overshoot; matches --ease-spring in globals.css. */
export const spring: Transition = { type: 'spring', bounce: 0.2, visualDuration: 0.35 };

export function MotionProvider({ children }: { children: ReactNode }) {
  return (
    // With reduced motion, Motion skips movement and keeps fades
    <MotionConfig reducedMotion="user" transition={spring}>
      <LazyMotion features={loadFeatures} strict>
        {children}
      </LazyMotion>
    </MotionConfig>
  );
}
