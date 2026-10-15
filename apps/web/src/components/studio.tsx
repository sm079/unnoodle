'use client';

import { useRef, useState } from 'react';
import { AnimatePresence, m } from 'motion/react';
import { ChevronRightIcon } from 'lucide-react';
import { AppShell } from '@/components/app-shell';
import { Composer } from '@/components/composer';
import { Gallery } from '@/components/gallery';
import { Hero } from '@/components/hero';
import { ProjectGrid } from '@/components/project-grid';
import { useGenerations, useProjects } from '@/lib/data';
import { cn } from '@/lib/utils';
import { allProjects, folder, home, projectOf, type View } from '@/lib/views';
import type { Asset } from '@/lib/types';

interface StudioProps {
  /** The outputs the hero shows. */
  highlights: Asset[];
}

/**
 * The one screen the app is: the home screen (hero and composer), All projects, or one folder's gallery. On phones
 * the composer is docked at the bottom everywhere; on wide screens it sits under the hero, then docks under the rest.
 * Generating from a project files the result there; from anywhere else it goes to My generations, which opens.
 */
export function Studio({ highlights }: StudioProps) {
  const [view, setView] = useState<View>(home);
  const top = useRef<HTMLDivElement>(null);

  function show(next: View) {
    setView(next);
    // The newest generation is at the top of the gallery
    top.current?.scrollIntoView({ block: 'start' });
  }

  return (
    <AppShell view={view} onView={show}>
      <div
        ref={top}
        // Clear of the sticky phone header when scrolled to
        className={cn(
          'flex flex-1 scroll-mt-12 flex-col px-4 lg:px-12',
          view.name === 'home' ? 'lg:justify-center lg:gap-14 lg:py-12' : 'gap-4 pt-3 lg:pt-8'
        )}
      >
        <AnimatePresence initial={false} mode="popLayout">
          {view.name === 'home' ? (
            // On phones the hero takes the room the docked composer leaves, and centres in it
            <m.div
              key="hero"
              exit={{ opacity: 0, y: -24, transition: { duration: 0.25 } }}
              className="flex flex-1 flex-col items-center justify-center py-6 lg:flex-none lg:py-0"
            >
              <Hero assets={highlights} title="One prompt, any workflow" />
            </m.div>
          ) : (
            <m.div
              key={view.name === 'folder' ? `folder-${view.project}` : 'projects'}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1, transition: { delay: 0.15 } }}
              className="flex flex-1 flex-col"
            >
              {view.name === 'projects' ? <ProjectGrid onView={show} /> : <Folder project={view.project} onView={show} />}
            </m.div>
          )}
        </AnimatePresence>

        {/* Kept mounted in every view, so a half-written prompt survives; layout animates its move */}
        <m.div
          layout="position"
          className={cn(
            'sticky bottom-0 z-10 mx-auto w-full bg-linear-to-t from-background from-70% to-transparent pt-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] md:max-w-2xl lg:max-w-[68rem] lg:pt-6 lg:pb-5',
            view.name === 'home' &&
              'animate-rise [--rise-blur:0px] [--rise-distance:18px] [animation-delay:250ms] [animation-duration:650ms] lg:static lg:bg-none lg:p-0'
          )}
        >
          <Composer
            projectId={projectOf(view)}
            onGenerated={generation => show(view.name === 'folder' ? view : folder(generation.project_id))}
          />
        </m.div>
      </div>
    </AppShell>
  );
}

/** A folder's gallery: one project's generations, or every generation for My generations. */
function Folder({ project, onView }: { project: string | null; onView: (view: View) => void }) {
  const { data: projects } = useProjects();
  const name = project === null ? 'My generations' : (projects?.find(p => p.id === project)?.name ?? '');
  return (
    <section aria-labelledby="gallery-title" className="flex flex-1 flex-col gap-4">
      <div className="flex flex-col gap-0.5">
        <button
          type="button"
          onClick={() => onView(allProjects)}
          className="flex w-fit items-center gap-0.5 text-sm text-[#8a8b8c] transition-colors hover:text-foreground"
        >
          All projects
          <ChevronRightIcon className="size-4" />
        </button>
        <h1 id="gallery-title" className="text-lg font-bold lg:text-xl">
          {name}
        </h1>
      </div>
      <Generations project={project} name={name} />
    </section>
  );
}

function Generations({ project, name }: { project: string | null; name: string }) {
  const { data, error, isLoading } = useGenerations(project);
  if (isLoading) return <p className="text-[#8a8b8c]">Loading…</p>;
  if (error && !data) return <p className="text-[#e8a33d]">{error.message}</p>;
  if (!data?.length) {
    return (
      <p className="text-[#8a8b8c]">
        {project === null
          ? 'Nothing yet. Describe something below and press Generate.'
          : `Nothing in ${name} yet. What you generate here is filed in it, and shows in My generations too.`}
      </p>
    );
  }
  return <Gallery generations={data} />;
}
