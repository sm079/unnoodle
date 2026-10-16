'use client';

import { useLayoutEffect, useRef, useState } from 'react';
import { AnimatePresence, m, type Transition, type Variants } from 'motion/react';
import { rollDirection } from '@/lib/motion';
import { cn } from '@/lib/utils';

const variants: Variants = {
  enter: (direction: number) => ({ y: `${direction * 75}%`, opacity: 0, filter: 'blur(2px)' }),
  center: { y: '0%', opacity: 1, filter: 'blur(0px)' },
  exit: (direction: number) => ({ y: `${direction * -75}%`, opacity: 0, filter: 'blur(2px)' })
};

const transition: Transition = { type: 'spring', bounce: 0.15, visualDuration: 0.3 };

/**
 * Shows a value that rolls to its next one like an odometer, while its width eases to the new one's, so whatever sits
 * beside it slides rather than jumps. Screen readers get the plain value.
 */
export function RollingValue({ value, className }: { value: string | number; className?: string }) {
  const [shown, setShown] = useState(value);
  const [direction, setDirection] = useState(1);
  if (value !== shown) {
    setDirection(rollDirection(shown, value));
    setShown(value);
  }

  // The new value's width, measured from a hidden copy; also follows late font loads
  const measure = useRef<HTMLSpanElement>(null);
  const [width, setWidth] = useState<number | null>(null);
  useLayoutEffect(() => {
    const element = measure.current;
    if (!element) return;
    const read = () => setWidth(element.getBoundingClientRect().width);
    read();
    const observer = new ResizeObserver(read);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return (
    <m.span
      initial={false}
      animate={width === null ? undefined : { width }}
      transition={transition}
      className={cn('relative inline-grid overflow-hidden', className)}
    >
      <span className="sr-only">{value}</span>
      <span ref={measure} aria-hidden className="invisible absolute top-0 left-0 whitespace-nowrap">
        {value}
      </span>
      <AnimatePresence initial={false} custom={direction}>
        <m.span
          key={value}
          aria-hidden
          custom={direction}
          variants={variants}
          initial="enter"
          animate="center"
          exit="exit"
          transition={transition}
          // Clipped by the box rather than cut with an ellipsis, which would flash on the old value as the box narrows
          className="col-start-1 row-start-1 whitespace-nowrap"
        >
          {value}
        </m.span>
      </AnimatePresence>
    </m.span>
  );
}
