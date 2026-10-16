'use client';

import { m, type Variants } from 'motion/react';
import { cn } from '@/lib/utils';

// Both paths use the same commands so one can morph into the other
const tangled = 'M3 15.5c1.6 -5 4.4 -5 5.2 -1.8c0.7 2.9 3.3 3 4.3 -0.7c0.6 -2.1 1.6 -3 3 -3H21';
const straight = 'M3 12c1.6 0 4.4 0 5.2 0c0.7 0 3.3 0 4.3 0c0.6 0 1.6 0 3 0H21';

const lineVariants: Variants = {
  tangled: { d: tangled },
  straight: { d: straight, transition: { type: 'spring', bounce: 0.45, visualDuration: 0.4 } }
};

/**
 * A tangled line that straightens out. Drawn in currentColor so it works on a tile or on its own. It straightens when
 * a Motion ancestor switches to the "straight" variant, e.g. with whileHover="straight".
 */
export function NoodleGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden className={cn('size-4', className)}>
      <m.path d={tangled} variants={lineVariants} stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        'flex size-8 shrink-0 items-center justify-center rounded-[9px] bg-linear-to-b from-[#ff8763] to-brand text-white shadow-[inset_0_1px_0_rgb(255_255_255/0.5)]',
        className
      )}
    >
      <NoodleGlyph className="size-5" />
    </span>
  );
}
