'use client';

import { useState, type CSSProperties } from 'react';
import Image from 'next/image';
import { cn } from '@/lib/utils';
import type { Asset } from '@/lib/types';

/** A fanned stack of recent outputs. Clicking a side card brings it to the front. */
export function Hero({ assets, title }: { assets: Asset[]; title: string }) {
  const [front, setFront] = useState(0);
  const count = assets.length;

  return (
    <section aria-label="Highlights" className="flex flex-col items-center gap-10 lg:gap-[52px]">
      <div className="relative h-[calc(var(--card-w)*9/16)] w-full [--card-w:200px] [--shift:110px] lg:[--card-w:345px] lg:[--shift:228px]">
        {assets.map((asset, index) => {
          // -1 and 1 sit either side of the front card; the rest wait out of sight behind it
          const offset = ((index - front + count + 1) % count) - 1;
          const side = Math.abs(offset) === 1;
          const style: CSSProperties = {
            width: 'var(--card-w)',
            transform: `translate(calc(-50% + var(--shift) * ${side ? offset : 0}), -50%) scale(${offset === 0 ? 1 : side ? 0.7 : 0.5})`,
            zIndex: offset === 0 ? 2 : side ? 1 : 0,
            opacity: offset === 0 || side ? 1 : 0
          };
          return (
            <button
              key={asset.id}
              type="button"
              tabIndex={side ? 0 : -1}
              aria-hidden={!side && offset !== 0}
              aria-label={offset === 0 ? 'Current highlight' : 'Show this highlight'}
              onClick={() => setFront(index)}
              style={style}
              className={cn(
                'absolute top-1/2 left-1/2 aspect-video overflow-hidden rounded-[11px] bg-muted transition-[transform,opacity] duration-500 ease-out',
                offset === 0
                  ? 'cursor-default shadow-[0_18px_40px_rgb(0_0_0/0.55)] ring-2 ring-white/25'
                  : 'shadow-[0_8px_24px_rgb(0_0_0/0.4)] ring-1 ring-white/15'
              )}
            >
              <Image src={asset.thumbnail_url} alt="" fill sizes="345px" className="object-cover" priority={offset === 0} />
            </button>
          );
        })}
      </div>

      <h1 className="bg-linear-to-b from-white to-[#8d8d8e] bg-clip-text px-4 text-center font-display text-[32px] leading-none font-bold tracking-[-0.01em] text-transparent uppercase font-stretch-[86%] lg:text-[47px]">
        {title}
      </h1>
    </section>
  );
}
