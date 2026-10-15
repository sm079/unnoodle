'use client';

import { useRef, useState } from 'react';
import { AnimatePresence, m } from 'motion/react';
import { AppShell, type View } from '@/components/app-shell';
import { Composer } from '@/components/composer';
import { Gallery } from '@/components/gallery';
import { Hero } from '@/components/hero';
import { useGenerations } from '@/lib/data';
import { cn } from '@/lib/utils';
import type { Asset, Project } from '@/lib/types';

interface StudioProps {
  /** The outputs the hero shows. */
  highlights: Asset[];
  projects: Project[];
}

/**
 * The one screen the app is: the home screen (hero and composer) until something is generating, then the gallery. On
 * phones the composer is docked at the bottom in both; on wide screens it sits under the hero, then slides down to
 * dock under the gallery.
 */
export function Studio({ highlights, projects }: StudioProps) {
  const [view, setView] = useState<View>('home');
  const top = useRef<HTMLDivElement>(null);

  function show(next: View) {
    setView(next);
    // The newest generation is at the top of the gallery
    top.current?.scrollIntoView({ block: 'start' });
  }

  return (
    <AppShell projects={projects} view={view} onView={show}>
      <div
        ref={top}
        // Clear of the sticky phone header when scrolled to
        className={cn(
          'flex flex-1 scroll-mt-12 flex-col px-4 lg:px-12',
          view === 'home' ? 'lg:justify-center lg:gap-14 lg:py-12' : 'gap-4 pt-3 lg:pt-8'
        )}
      >
        <AnimatePresence initial={false} mode="popLayout">
          {view === 'home' ? (
            // On phones the hero takes the room the docked composer leaves, and centres in it
            <m.div
              key="hero"
              exit={{ opacity: 0, y: -24, transition: { duration: 0.25 } }}
              className="flex flex-1 flex-col items-center justify-center py-6 lg:flex-none lg:py-0"
            >
              <Hero assets={highlights} title="One prompt, any workflow" />
            </m.div>
          ) : (
            <m.section
              key="gallery"
              aria-labelledby="gallery-title"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1, transition: { delay: 0.15 } }}
              className="flex flex-1 flex-col gap-4"
            >
              <h1 id="gallery-title" className="text-lg font-bold lg:text-xl">
                My generations
              </h1>
              <Generations />
            </m.section>
          )}
        </AnimatePresence>

        {/* Kept mounted in both views, so a half-written prompt survives; layout animates its move */}
        <m.div
          layout="position"
          className={cn(
            'sticky bottom-0 z-10 mx-auto w-full bg-linear-to-t from-background from-70% to-transparent pt-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] md:max-w-2xl lg:max-w-[68rem] lg:pt-6 lg:pb-5',
            view === 'home' &&
              'animate-rise [--rise-blur:0px] [--rise-distance:18px] [animation-delay:250ms] [animation-duration:650ms] lg:static lg:bg-none lg:p-0'
          )}
        >
          <Composer onGenerated={() => show('gallery')} />
        </m.div>
      </div>
    </AppShell>
  );
}

function Generations() {
  const { data, error, isLoading } = useGenerations();
  if (isLoading) return <p className="text-[#8a8b8c]">Loading…</p>;
  if (error && !data) return <p className="text-[#e8a33d]">{error.message}</p>;
  if (!data?.length) {
    return <p className="text-[#8a8b8c]">Nothing yet. Describe something below and press Generate.</p>;
  }
  return <Gallery generations={data} />;
}
