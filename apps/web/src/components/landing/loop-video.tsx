'use client';

import { useEffect, useRef, useState } from 'react';
import { PlayIcon, Volume2Icon, VolumeXIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * A muted looping video that plays only while it's on screen, so a page of them doesn't decode all at once. With
 * reduced motion it waits for a tap. `sound` adds a button that unmutes it.
 */
export function LoopVideo({
  src,
  poster,
  label,
  sound = false,
  className
}: {
  src: string;
  poster: string;
  label: string;
  sound?: boolean;
  className?: string;
}) {
  const ref = useRef<HTMLVideoElement>(null);
  const [muted, setMuted] = useState(true);
  const [paused, setPaused] = useState(true);
  const [still, setStill] = useState(false);

  useEffect(() => {
    const video = ref.current;
    if (!video) return;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    setStill(reduced);
    if (reduced) return;
    const observer = new IntersectionObserver(([entry]) => {
      // Browsers can refuse to play (low power mode, data saver); the poster stays and a tap starts it
      if (entry.isIntersecting) video.play().catch(() => setStill(true));
      else video.pause();
    });
    observer.observe(video);
    return () => observer.disconnect();
  }, []);

  function toggleSound() {
    const video = ref.current;
    if (!video) return;
    video.muted = !video.muted;
    setMuted(video.muted);
    if (video.paused) video.play().catch(() => {});
  }

  return (
    <div className={cn('relative overflow-hidden bg-panel', className)}>
      <video
        ref={ref}
        src={src}
        poster={poster}
        aria-label={label}
        muted
        loop
        playsInline
        preload="metadata"
        onPlay={() => setPaused(false)}
        onPause={() => setPaused(true)}
        className="size-full object-cover"
      />
      {still && paused && (
        <button
          type="button"
          onClick={() => ref.current?.play().catch(() => {})}
          aria-label={`Play ${label}`}
          className="absolute inset-0 flex items-center justify-center bg-black/20"
        >
          <span className="flex size-12 items-center justify-center rounded-full bg-black/55 backdrop-blur-md">
            <PlayIcon className="size-5 fill-white text-white" />
          </span>
        </button>
      )}
      {sound && (
        <button
          type="button"
          onClick={toggleSound}
          aria-pressed={!muted}
          aria-label={muted ? 'Turn sound on' : 'Turn sound off'}
          className="absolute right-2.5 bottom-2.5 flex h-8 items-center gap-1.5 rounded-full bg-black/55 px-3 text-xs font-semibold text-white backdrop-blur-md transition-[scale,background-color] duration-200 ease-spring hover:bg-black/70 active:scale-90"
        >
          {muted ? <VolumeXIcon className="size-4" /> : <Volume2Icon className="size-4" />}
          {muted ? 'Sound' : 'On'}
        </button>
      )}
    </div>
  );
}
