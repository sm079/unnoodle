'use client';

import { useState } from 'react';
import Image from 'next/image';
import { FolderPlusIcon, SparklesIcon } from 'lucide-react';
import { NewProjectForm } from '@/components/new-project';
import { useGenerations, useProjects } from '@/lib/data';
import { cn } from '@/lib/utils';
import { folder, type View } from '@/lib/views';
import type { Asset } from '@/lib/types';

// Cards lift under the pointer and give a little when pressed
const cardClass = 'group flex w-full flex-col gap-2 rounded-2xl text-left outline-none focus-visible:ring-2 focus-visible:ring-white/30';
const pressClass = 'transition-[translate,scale,background-color] duration-300 ease-spring active:scale-[0.98] active:duration-100';

/** All projects: My generations, the folder that holds everything, then each project, then a card to make one. */
export function ProjectGrid({ onView }: { onView: (view: View) => void }) {
  const { data: projects = [] } = useProjects();
  const { data: everything = [] } = useGenerations(null);
  const [creating, setCreating] = useState(false);

  return (
    <section aria-labelledby="projects-title" className="flex flex-col gap-4">
      <h1 id="projects-title" className="text-lg font-bold lg:text-xl">
        All projects
      </h1>
      <ul className="grid grid-cols-2 gap-x-3 gap-y-5 sm:grid-cols-3 lg:gap-x-6 xl:grid-cols-4">
        <li>
          <FolderCard
            name="My generations"
            detail="Everything you make"
            covers={everything.flatMap(g => g.outputs).slice(0, 3)}
            special
            onOpen={() => onView(folder(null))}
          />
        </li>
        {projects.map(project => (
          <li key={project.id}>
            <FolderCard
              name={project.name}
              detail={`${project.generation_count} ${project.generation_count === 1 ? 'generation' : 'generations'}`}
              covers={project.covers}
              onOpen={() => onView(folder(project.id))}
            />
          </li>
        ))}
        <li>
          {creating ? (
            <div className="flex aspect-[358/230] items-center rounded-2xl border border-white/[0.04] bg-[#1f2022] p-3">
              <NewProjectForm onCreated={project => onView(folder(project.id))} onCancel={() => setCreating(false)} className="w-full" />
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setCreating(true)}
              className={cn(
                cardClass,
                pressClass,
                'aspect-[358/230] items-center justify-center border border-white/[0.04] bg-[#1f2022] hover:bg-[#232426]'
              )}
            >
              <span className="flex size-12 items-center justify-center rounded-full bg-linear-to-b from-[#3a3b3d] to-[#2a2b2d] shadow-[inset_0_1px_0_rgb(255_255_255/0.12),0_6px_16px_rgb(0_0_0/0.45)] ring-1 ring-white/10 transition-[scale] duration-500 ease-spring-bouncy group-hover:scale-110 group-active:scale-95">
                <FolderPlusIcon className="size-5 text-white transition-[rotate] duration-500 ease-spring-bouncy group-hover:-rotate-8" />
              </span>
              <span className="text-sm font-semibold text-[#8a8b8c]">New project</span>
            </button>
          )}
        </li>
      </ul>
    </section>
  );
}

function FolderCard({
  name,
  detail,
  covers,
  special = false,
  onOpen
}: {
  name: string;
  detail: string;
  covers: Asset[];
  special?: boolean;
  onOpen: () => void;
}) {
  return (
    <button type="button" onClick={onOpen} className={cardClass}>
      <span className={cn(pressClass, 'grid aspect-[358/230] w-full grid-cols-[2fr_1fr] grid-rows-2 gap-1.5 group-hover:-translate-y-1')}>
        {[0, 1, 2].map(slot => (
          <span
            key={slot}
            className={cn(
              'relative overflow-hidden rounded-xl bg-[#1f2022] transition-shadow duration-300 group-hover:shadow-[0_12px_28px_rgb(0_0_0/0.45)]',
              slot === 0 && 'row-span-2'
            )}
          >
            {covers[slot] ? (
              <Image
                unoptimized
                src={covers[slot].thumbnail_url}
                alt=""
                fill
                sizes={slot === 0 ? '260px' : '96px'}
                // Each cover zooms a moment after the one before, so the card reads as one object
                style={{ transitionDelay: `${slot * 50}ms` }}
                className="object-cover transition-[scale] duration-700 ease-out-quint group-hover:scale-[1.06]"
              />
            ) : (
              <Stripes />
            )}
            {special && slot === 0 && (
              <span className="absolute top-2 left-2 flex size-7 items-center justify-center rounded-lg bg-linear-to-b from-[#8de7f5] to-[#2687b3] shadow-[inset_0_1px_0_rgb(255_255_255/0.35)]">
                <SparklesIcon className="size-4 fill-white/25 text-white" />
              </span>
            )}
          </span>
        ))}
      </span>
      <span className="flex min-w-0 flex-col px-0.5">
        <span className="truncate text-sm font-semibold">{name}</span>
        <span className="truncate text-xs text-[#8a8b8c]">{detail}</span>
      </span>
    </button>
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
