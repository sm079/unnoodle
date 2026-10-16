'use client';

import { useState, type CSSProperties } from 'react';
import Image from 'next/image';
import { cn } from '@/lib/utils';

/** Two pictures of the same size, one over the other, with a handle that wipes between them. */
export function BeforeAfter({
  before,
  after,
  width,
  height,
  className
}: {
  before: { src: string; alt: string };
  after: { src: string; alt: string };
  width: number;
  height: number;
  className?: string;
}) {
  const [split, setSplit] = useState(50);
  const sizes = '(min-width: 1024px) 25vw, 80vw';

  return (
    <div className={cn('relative overflow-hidden bg-panel select-none', className)} style={{ '--split': `${split}%` } as CSSProperties}>
      <Image src={after.src} alt={after.alt} width={width} height={height} sizes={sizes} className="size-full object-cover" />
      <Image
        src={before.src}
        alt={before.alt}
        width={width}
        height={height}
        sizes={sizes}
        className="absolute inset-0 size-full object-cover [clip-path:inset(0_calc(100%-var(--split))_0_0)]"
      />
      <span className="pointer-events-none absolute top-2.5 left-2.5 rounded-full bg-black/55 px-2.5 py-1 text-[0.6875rem] font-semibold text-white backdrop-blur-md">
        Before
      </span>
      <span className="pointer-events-none absolute top-2.5 right-2.5 rounded-full bg-black/55 px-2.5 py-1 text-[0.6875rem] font-semibold text-white backdrop-blur-md">
        After
      </span>
      <span
        aria-hidden
        className="pointer-events-none absolute inset-y-0 left-(--split) w-0.5 -translate-x-1/2 bg-white shadow-[0_0_12px_rgb(0_0_0/0.5)]"
      >
        <span className="absolute top-1/2 left-1/2 flex size-9 -translate-1/2 items-center justify-center rounded-full bg-white text-black shadow-lg">
          <svg
            viewBox="0 0 24 24"
            className="size-4"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="m9 6-6 6 6 6M15 6l6 6-6 6" />
          </svg>
        </span>
      </span>
      <input
        type="range"
        min={0}
        max={100}
        value={split}
        onChange={event => setSplit(Number(event.target.value))}
        aria-label="Compare before and after"
        className="absolute inset-0 size-full cursor-ew-resize opacity-0"
      />
    </div>
  );
}
