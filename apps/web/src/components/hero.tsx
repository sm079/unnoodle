'use client';

import { Fragment, useEffect, useRef, useState, type CSSProperties, type KeyboardEvent, type PointerEvent } from 'react';
import Image from 'next/image';
import { offsetOf, restAt, swipeStep } from '@/lib/fan';
import { cn } from '@/lib/utils';
import type { Asset } from '@/lib/types';

interface Swipe {
  pointerId: number;
  startX: number;
  startY: number;
  /** Pixels between the front card and a side card. */
  shift: number;
  dragging: boolean;
  /** Recent pointer positions, for the release velocity. */
  samples: { x: number; t: number }[];
}

/**
 * A fanned stack of recent outputs, or with none yet, a word on how to start. Tap or click a side card to bring it to the front, swipe or drag the fan, or use the
 * arrow keys. With a mouse, the front card leans toward the pointer.
 */
export function Hero({ assets, title }: { assets: Asset[]; title: string }) {
  const [front, setFront] = useState(0);
  const [dragging, setDragging] = useState(false);
  const stageRef = useRef<HTMLDivElement>(null);
  const cardRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const swipe = useRef<Swipe | null>(null);
  const swallowClick = useRef(false);
  const focusFront = useRef(false);
  const tiltFrame = useRef(0);
  const count = assets.length;

  useEffect(() => {
    if (!focusFront.current) return;
    focusFront.current = false;
    cardRefs.current[front]?.focus();
  }, [front]);

  useEffect(() => () => cancelAnimationFrame(tiltFrame.current), []);

  function step(by: number) {
    setFront(current => (current + by + count) % count);
  }

  function setProgress(progress: number) {
    stageRef.current?.style.setProperty('--p', String(progress));
  }

  function onPointerDown(event: PointerEvent<HTMLDivElement>) {
    swallowClick.current = false;
    if (!event.isPrimary || event.button !== 0) return;
    const shift = parseFloat(getComputedStyle(event.currentTarget).getPropertyValue('--shift')) || 1;
    swipe.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      shift,
      dragging: false,
      samples: [{ x: event.clientX, t: event.timeStamp }]
    };
  }

  function onPointerMove(event: PointerEvent<HTMLDivElement>) {
    if (event.pointerType === 'mouse') tiltToward(event.clientX, event.clientY);

    const current = swipe.current;
    if (!current || current.pointerId !== event.pointerId) return;
    const dx = event.clientX - current.startX;
    if (!current.dragging) {
      const dy = event.clientY - current.startY;
      if (Math.hypot(dx, dy) < 8) return;
      // Mostly vertical: leave it to the page to scroll
      if (Math.abs(dy) > Math.abs(dx)) {
        swipe.current = null;
        return;
      }
      current.dragging = true;
      event.currentTarget.setPointerCapture(event.pointerId);
      setDragging(true);
      untilt();
    }
    current.samples = [...current.samples.filter(sample => event.timeStamp - sample.t < 100), { x: event.clientX, t: event.timeStamp }];
    setProgress(Math.max(-1, Math.min(1, dx / current.shift)));
  }

  function onPointerUp(event: PointerEvent<HTMLDivElement>) {
    const current = swipe.current;
    swipe.current = null;
    if (!current?.dragging) return;
    // The pointer was captured, so the click that follows lands on the stage and must not pick a card
    swallowClick.current = true;
    const [oldest] = current.samples;
    const velocity = (event.clientX - oldest.x) / Math.max(1, event.timeStamp - oldest.t);
    const by = swipeStep((event.clientX - current.startX) / current.shift, velocity);
    // Settle from where the finger let go: the cards spring from the dragged layout to the new one
    setProgress(0);
    setDragging(false);
    if (by !== 0) step(by);
  }

  function onPointerCancel() {
    swipe.current = null;
    setProgress(0);
    setDragging(false);
  }

  function tiltToward(clientX: number, clientY: number) {
    cancelAnimationFrame(tiltFrame.current);
    tiltFrame.current = requestAnimationFrame(() => {
      const card = cardRefs.current[front];
      const stage = stageRef.current;
      if (!card || !stage || swipe.current?.dragging) return;
      const box = card.getBoundingClientRect();
      const x = Math.max(-1, Math.min(1, ((clientX - box.left) / box.width) * 2 - 1));
      const y = Math.max(-1, Math.min(1, ((clientY - box.top) / box.height) * 2 - 1));
      stage.style.setProperty('--rx', `${(-y * 5).toFixed(2)}deg`);
      stage.style.setProperty('--ry', `${(x * 7).toFixed(2)}deg`);
      stage.style.setProperty('--mx', `${((x + 1) * 50).toFixed(1)}%`);
      stage.style.setProperty('--my', `${((y + 1) * 50).toFixed(1)}%`);
    });
  }

  function untilt() {
    cancelAnimationFrame(tiltFrame.current);
    stageRef.current?.style.setProperty('--rx', '0deg');
    stageRef.current?.style.setProperty('--ry', '0deg');
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();
    focusFront.current = true;
    step(event.key === 'ArrowRight' ? 1 : -1);
  }

  return (
    <section className="flex flex-col items-center gap-7 lg:gap-12">
      {count > 0 && (
        <div
          ref={stageRef}
          role="region"
          aria-roledescription="carousel"
          aria-label="Highlights"
          data-dragging={dragging || undefined}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerCancel}
          onPointerLeave={untilt}
          onClickCapture={event => {
            if (!swallowClick.current) return;
            swallowClick.current = false;
            event.preventDefault();
            event.stopPropagation();
          }}
          onKeyDown={onKeyDown}
          className="group/stage hero-stage relative isolate h-[calc(var(--card-w)*9/16)] w-full touch-pan-y select-none [--card-w:200px] [--shift:110px] lg:[--card-w:345px] lg:[--shift:228px]"
        >
          {/* The front card's colours, blurred into a glow behind the fan */}
          <div
            aria-hidden
            className="pointer-events-none absolute top-1/2 left-1/2 -z-10 h-[150%] w-[calc(var(--card-w)*2)] -translate-1/2 animate-[fade-in_1400ms_ease-out_500ms_backwards] opacity-45 blur-3xl saturate-150"
          >
            {assets.map((asset, index) => (
              <Image
                key={asset.id}
                src={asset.thumbnail_url}
                alt=""
                fill
                sizes="64px"
                className={cn('object-cover transition-opacity duration-700 ease-out', index === front ? 'opacity-100' : 'opacity-0')}
              />
            ))}
          </div>

          {assets.map((asset, index) => {
            const offset = offsetOf(index, front, count);
            const here = restAt(offset);
            const next = restAt(offset - 1);
            const previous = restAt(offset + 1);
            const isFront = offset === 0;
            const side = Math.abs(offset) === 1;
            const style = {
              width: 'var(--card-w)',
              '--x': here.x,
              '--s': here.scale,
              '--a': here.opacity,
              '--x-next': next.x,
              '--s-next': next.scale,
              '--a-next': next.opacity,
              '--x-prev': previous.x,
              '--s-prev': previous.scale,
              '--a-prev': previous.opacity,
              '--deal': Math.abs(offset)
            } as CSSProperties;
            return (
              <button
                key={asset.id}
                ref={element => {
                  cardRefs.current[index] = element;
                }}
                type="button"
                data-front={isFront || undefined}
                data-side={side ? (offset < 0 ? 'previous' : 'next') : undefined}
                tabIndex={isFront || side ? 0 : -1}
                aria-hidden={!isFront && !side}
                inert={!isFront && !side}
                aria-label={isFront ? `Highlight ${index + 1} of ${count}` : offset < 0 ? 'Previous highlight' : 'Next highlight'}
                onClick={() => side && step(offset)}
                style={style}
                className={cn(
                  'hero-card absolute top-1/2 left-1/2 aspect-video overflow-hidden rounded-[11px] bg-muted outline-none focus-visible:ring-4 focus-visible:ring-brand/60',
                  isFront
                    ? 'cursor-grab shadow-[0_18px_40px_rgb(0_0_0/0.55)] ring-2 ring-white/25 group-data-[dragging]/stage:cursor-grabbing'
                    : 'shadow-[0_8px_24px_rgb(0_0_0/0.4)] ring-1 ring-white/15 hover:brightness-110',
                  // A side card peeks toward the centre under the pointer, inviting the click
                  'motion-safe:data-[side=next]:hover:[transform:translateX(-14px)] motion-safe:data-[side=previous]:hover:[transform:translateX(14px)]'
                )}
              >
                <Image
                  src={asset.thumbnail_url}
                  alt=""
                  fill
                  sizes="345px"
                  draggable={false}
                  // The first front card is the largest thing on screen at load
                  preload={index === 0}
                  loading={Math.abs(offsetOf(index, 0, count)) === 1 ? 'eager' : undefined}
                  className="object-cover"
                />
                {isFront && (
                  <span
                    aria-hidden
                    className="hero-glare pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300"
                    style={{
                      background: 'radial-gradient(circle at var(--mx, 50%) var(--my, 50%), rgb(255 255 255 / 0.2), transparent 55%)'
                    }}
                  />
                )}
              </button>
            );
          })}

          <p aria-live="polite" className="sr-only">
            {`Highlight ${front + 1} of ${count}`}
          </p>
        </div>
      )}

      <h1 className="px-4 text-center font-display text-[clamp(1.625rem,1.1rem+2.4vw,2.95rem)] leading-none font-bold tracking-[-0.01em] text-balance uppercase font-stretch-[86%]">
        {title.split(' ').map((word, index) => (
          <Fragment key={index}>
            {index > 0 && ' '}
            <span className="hero-word -mb-[0.1em] pb-[0.1em]" style={{ '--i': index } as CSSProperties}>
              {word}
            </span>
          </Fragment>
        ))}
      </h1>
      {count === 0 && (
        <p className="max-w-md px-4 text-center text-balance text-[#8a8b8c]">
          Describe a picture or a video below. Attach photos or clips to change them or to show what you mean.
        </p>
      )}
    </section>
  );
}
