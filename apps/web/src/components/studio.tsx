'use client';

import { useRef, useState } from 'react';
import { AnimatePresence, m } from 'motion/react';
import { AppShell, type View } from '@/components/app-shell';
import { Composer } from '@/components/composer';
import { Gallery } from '@/components/gallery';
import { Hero } from '@/components/hero';
import { ProjectGrid } from '@/components/project-grid';
import { useGenerations } from '@/lib/data';
import { cn } from '@/lib/utils';
import type { Asset, Project } from '@/lib/types';

interface StudioProps {
  /** The outputs the hero shows. */
  highlights: Asset[];
  projects: Project[];
}

/**
 * The one screen the app is: the home screen (hero, composer, projects) until something is generating, then the
 * gallery, with the composer sliding down to stay docked under it.
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
        className={cn(
          'flex min-h-full flex-col px-4 lg:px-[50px]',
          view === 'home' ? 'gap-10 pt-6 pb-16 lg:gap-[55px] lg:pt-[73px]' : 'gap-4 pt-4 lg:pt-8'
        )}
      >
        <AnimatePresence initial={false} mode="popLayout">
          {view === 'home' ? (
            <m.div key="hero" exit={{ opacity: 0, y: -24, transition: { duration: 0.25 } }} className="flex flex-col items-center">
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
              <h1 id="gallery-title" className="text-xl font-bold">
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
            'mx-auto w-full max-w-[1092px]',
            view === 'home'
              ? 'animate-rise [--rise-blur:0px] [--rise-distance:18px] [animation-delay:250ms] [animation-duration:650ms]'
              : 'sticky bottom-0 z-10 bg-linear-to-t from-background from-70% to-transparent pt-6 pb-3 lg:pb-5'
          )}
        >
          <Composer onGenerated={() => show('gallery')} />
        </m.div>

        {view === 'home' && (
          // Further from the composer than the hero is
          <div className="mt-10 lg:mt-[37px]">
            <ProjectGrid projects={projects} />
          </div>
        )}
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
