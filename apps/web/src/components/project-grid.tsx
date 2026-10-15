import Image from 'next/image';
import { ChevronRightIcon, FolderPlusIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Generation, Project } from '@/lib/types';

export function ProjectGrid({ projects, generations }: { projects: Project[]; generations: Generation[] }) {
  return (
    <section aria-labelledby="my-projects" className="flex flex-col gap-5">
      <h2 id="my-projects" className="flex items-center gap-1.5 text-xl font-bold">
        My projects
        <ChevronRightIcon className="size-5 text-[#8a8b8c]" />
      </h2>
      <ul className="grid grid-cols-1 gap-x-[30px] gap-y-6 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
        <li>
          <button
            type="button"
            className="group flex aspect-[358/230] w-full items-center justify-center rounded-2xl border border-white/[0.04] bg-[#1f2022] transition-colors hover:bg-[#232426]"
          >
            <span className="flex size-[72px] items-center justify-center rounded-full bg-linear-to-b from-[#3a3b3d] to-[#2a2b2d] shadow-[inset_0_1px_0_rgb(255_255_255/0.12),0_6px_16px_rgb(0_0_0/0.45)] ring-1 ring-white/10 transition-transform group-hover:scale-105">
              <FolderPlusIcon className="size-7 text-white" />
            </span>
            <span className="sr-only">New project</span>
          </button>
        </li>
        {projects.map(project => {
          const covers = generations.filter(g => g.project_id === project.id).flatMap(g => g.outputs);
          return (
            <li key={project.id} className="flex flex-col gap-2.5">
              <div className="grid aspect-[358/230] grid-cols-[1fr_96px] grid-rows-2 gap-2.5">
                {[0, 1, 2].map(slot => (
                  <div key={slot} className={cn('relative overflow-hidden rounded-2xl bg-[#1f2022]', slot === 0 && 'row-span-2')}>
                    {covers[slot] ? (
                      <Image src={covers[slot].thumbnail_url} alt="" fill sizes={slot === 0 ? '260px' : '96px'} className="object-cover" />
                    ) : (
                      <Stripes />
                    )}
                  </div>
                ))}
              </div>
              <div className="flex items-baseline justify-between gap-2 px-0.5">
                <span className="truncate font-semibold">{project.name}</span>
                <span className="shrink-0 text-sm text-[#8a8b8c]">
                  {covers.length} {covers.length === 1 ? 'item' : 'items'}
                </span>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/** Fills an empty cover slot. */
function Stripes() {
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice" aria-hidden className="size-full text-[#2a2b2d]">
      <path
        d="M-10 70C20 40 30 20 45-10M15 110C45 70 60 40 80-10M55 115C75 80 90 60 115 40"
        stroke="currentColor"
        strokeWidth="14"
        fill="none"
      />
    </svg>
  );
}
