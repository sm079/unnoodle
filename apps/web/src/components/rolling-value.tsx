'use client';

import { useState } from 'react';
import { AnimatePresence, m, type Variants } from 'motion/react';
import { rollDirection } from '@/lib/motion';
import { cn } from '@/lib/utils';

const variants: Variants = {
  enter: (direction: number) => ({ y: `${direction * 75}%`, opacity: 0, filter: 'blur(2px)' }),
  center: { y: '0%', opacity: 1, filter: 'blur(0px)' },
  exit: (direction: number) => ({ y: `${direction * -75}%`, opacity: 0, filter: 'blur(2px)' })
};

/** Shows a value that rolls to its next one like an odometer. Screen readers get the plain value. */
export function RollingValue({ value, className }: { value: string | number; className?: string }) {
  const [shown, setShown] = useState(value);
  const [direction, setDirection] = useState(1);
  if (value !== shown) {
    setDirection(rollDirection(shown, value));
    setShown(value);
  }

  return (
    <span className={cn('relative inline-grid overflow-hidden', className)}>
      <span className="sr-only">{value}</span>
      <AnimatePresence initial={false} custom={direction}>
        <m.span
          key={value}
          aria-hidden
          custom={direction}
          variants={variants}
          initial="enter"
          animate="center"
          exit="exit"
          transition={{ type: 'spring', bounce: 0.15, visualDuration: 0.3 }}
          className="col-start-1 row-start-1 truncate"
        >
          {value}
        </m.span>
      </AnimatePresence>
    </span>
  );
}
