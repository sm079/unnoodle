'use client';

import { useRef, useState } from 'react';
import { AnimatePresence, m } from 'motion/react';
import { ChevronRightIcon } from 'lucide-react';
import { AppShell } from '@/components/app-shell';
import { Composer, type ComposerHandle } from '@/components/composer';
import { Gallery } from '@/components/gallery';
import { Hero } from '@/components/hero';
import { ProjectGrid } from '@/components/project-grid';
import { useGenerations, useProjects } from '@/lib/data';
import type { Asset } from '@/lib/types';
import { cn } from '@/lib/utils';
import { allProjects, folder, home, projectOf, type View } from '@/lib/views';

// The hero shows this many of the newest outputs
const HIGHLIGHTS = 8;

/**
 * The one screen the app is: the home screen (hero and composer), All projects, or one folder's gallery. On phones
 * the composer is docked at the bottom everywhere; on wide screens it sits under the hero, then docks under the rest.
 * Generating from a project files the result there; from anywhere else it goes to My generations, which opens. So
 * does generating from a demo someone else owns, since only its owner adds to it.
 */
export function Studio() {
  const [view, setView] = useState<View>(home);
  const { data: generations = [] } = useGenerations();
  const { data: projects = [] } = useProjects();
  // Until someone has made anything, the hero shows the demo's outputs (the same request as My generations without one)
  const demo = projects.find(p => p.demo);
  const { data: demoGenerations = [] } = useGenerations(demo?.id ?? null);
  const own = generations.flatMap(g => g.outputs);
  const highlights = (own.length > 0 ? own : demoGenerations.flatMap(g => g.outputs)).slice(0, HIGHLIGHTS);
  const open = projectOf(view);
  const fileInto = projects.find(p => p.id === open)?.mine === false ? null : open;
  const top = useRef<HTMLDivElement>(null);
  const composer = useRef<ComposerHandle>(null);
  const attachToComposer = (asset: Asset) => composer.current?.attach(asset);

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
              <Hero assets={highlights} title="Pictures and videos from one prompt" />
            </m.div>
          ) : (
            <m.div
              key={view.name === 'folder' ? `folder-${view.project}` : 'projects'}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1, transition: { delay: 0.15 } }}
              className="flex flex-1 flex-col"
            >
              {view.name === 'projects' ? (
                <ProjectGrid onView={show} />
              ) : (
                <Folder project={view.project} onView={show} onUseAsInput={attachToComposer} />
              )}
            </m.div>
          )}
        </AnimatePresence>

        {/* Kept mounted in every view, so a half-written prompt survives; layout animates its move. Docked, its backing
            spans the whole width so nothing scrolls past at its sides, and fades out above it over what scrolls under. */}
        <m.div
          layout="position"
          className={cn(
            'sticky bottom-0 z-10 -mx-4 bg-background px-4 pt-2 pb-[max(0.75rem,env(safe-area-inset-bottom))] before:pointer-events-none before:absolute before:inset-x-0 before:bottom-full before:h-12 before:bg-linear-to-t before:from-background before:to-transparent lg:-mx-12 lg:px-12 lg:pt-3 lg:pb-5 lg:before:h-20',
            view.name === 'home' &&
              'animate-rise [--rise-blur:0px] [--rise-distance:18px] [animation-delay:250ms] [animation-duration:650ms] lg:static lg:mx-0 lg:bg-transparent lg:p-0 lg:before:hidden'
          )}
        >
          <div className="mx-auto w-full md:max-w-2xl lg:max-w-[68rem]">
            <Composer
              ref={composer}
              projectId={fileInto}
              onGenerated={generation => show(view.name === 'folder' && fileInto === open ? view : folder(generation.project_id))}
            />
          </div>
        </m.div>
      </div>
    </AppShell>
  );
}

/** A folder's gallery: one project's generations, or every generation for My generations. */
function Folder({
  project,
  onView,
  onUseAsInput
}: {
  project: string | null;
  onView: (view: View) => void;
  onUseAsInput: (asset: Asset) => void;
}) {
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
      <Generations project={project} name={name} onUseAsInput={onUseAsInput} />
    </section>
  );
}

function Generations({ project, name, onUseAsInput }: { project: string | null; name: string; onUseAsInput: (asset: Asset) => void }) {
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
  return <Gallery generations={data} onUseAsInput={onUseAsInput} />;
}
