'use client';

import { useState, type ReactNode } from 'react';
import Image from 'next/image';
import { ClockIcon, ImageIcon, LoaderCircleIcon, PlayIcon, TriangleAlertIcon, VideoIcon } from 'lucide-react';
import { ResultView } from '@/components/result-view';
import { capabilityLabels, outputType } from '@/lib/capabilities';
import type { Asset, Generation } from '@/lib/types';

interface GalleryProps {
  generations: Generation[];
  /** Attaches an output to the composer. */
  onUseAsInput: (asset: Asset) => void;
}

/**
 * Generations newest first: finished ones show their output and open in the result view, the rest show where they
 * are in the queue.
 */
export function Gallery({ generations, onUseAsInput }: GalleryProps) {
  const [viewing, setViewing] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  return (
    <>
      <ul aria-label="Gallery" className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 lg:gap-3">
        {generations.map(generation => (
          <li key={generation.id} className="[--rise-blur:4px] [--rise-distance:10px] motion-safe:animate-rise">
            <GalleryTile
              generation={generation}
              onOpen={() => {
                setViewing(generation.id);
                setOpen(true);
              }}
            />
          </li>
        ))}
      </ul>
      <ResultView
        generation={generations.find(g => g.id === viewing) ?? null}
        open={open}
        onOpenChange={setOpen}
        onUseAsInput={onUseAsInput}
      />
    </>
  );
}

const tileClass = 'relative block aspect-square overflow-hidden rounded-2xl bg-panel';

function GalleryTile({ generation, onOpen }: { generation: Generation; onOpen: () => void }) {
  const cover = generation.outputs[0];

  if (generation.status === 'done' && cover) {
    return (
      <button type="button" onClick={onOpen} aria-label={generation.prompt} className={`${tileClass} group w-full`}>
        <Image
          src={cover.thumbnail_url}
          alt=""
          fill
          sizes="(min-width: 1024px) 25vw, (min-width: 640px) 33vw, 50vw"
          className="object-cover transition-[scale] duration-700 ease-out-quint group-hover:scale-[1.04]"
        />
        <div className="absolute inset-x-2 top-2 flex justify-between">
          {cover.media_type === 'video' && cover.duration_s !== null ? (
            <TileBadge>
              <PlayIcon className="size-3" />
              {formatDuration(cover.duration_s)}
            </TileBadge>
          ) : (
            <span />
          )}
          {generation.outputs.length > 1 && <TileBadge>{generation.outputs.length}</TileBadge>}
        </div>
      </button>
    );
  }

  const TypeIcon = outputType(generation.capability) === 'video' ? VideoIcon : ImageIcon;

  return (
    <div className={`${tileClass} flex flex-col gap-2 p-3 text-[0.8125rem]`}>
      <span className="flex items-center gap-1.5 text-[#8a8b8c]">
        <TypeIcon className="size-4" aria-hidden />
        {capabilityLabels[generation.capability]}
      </span>
      <div className="mt-auto flex flex-col gap-2">
        <StatusLine generation={generation} />
        <p className="line-clamp-3 text-[#8a8b8c]">{generation.prompt}</p>
      </div>
    </div>
  );
}

function StatusLine({ generation }: { generation: Generation }) {
  switch (generation.status) {
    case 'queued':
      return (
        <p className="flex items-center gap-1.5 font-semibold">
          <ClockIcon className="size-3.5" /> Queued
        </p>
      );
    case 'running': {
      const percent = Math.round((generation.progress ?? 0) * 100);
      // Before the first step a model loads and sets up, which reports nothing and can take over a minute for a video
      const settingUp = percent === 0;
      return (
        <div className="flex flex-col gap-1.5">
          <p className="flex items-center gap-1.5 font-semibold">
            <LoaderCircleIcon className="size-3.5 animate-spin" /> {settingUp ? 'Getting ready' : `Generating · ${percent}%`}
          </p>
          <div
            role="progressbar"
            aria-label="Progress"
            // Left out while setting up, which makes it an indeterminate bar
            aria-valuenow={settingUp ? undefined : percent}
            aria-valuemin={0}
            aria-valuemax={100}
            className="h-1 overflow-hidden rounded-full bg-white/10"
          >
            {settingUp ? (
              <div className="h-full w-1/3 animate-[sheen_1.6s_ease-in-out_infinite] rounded-full bg-lime/60 motion-reduce:w-full motion-reduce:animate-none motion-reduce:bg-lime/25" />
            ) : (
              <div className="h-full rounded-full bg-lime transition-[width] duration-700 ease-out" style={{ width: `${percent}%` }} />
            )}
          </div>
        </div>
      );
    }
    case 'failed':
      return (
        <p className="flex items-start gap-1.5 font-semibold text-[#ff6b6b]">
          <TriangleAlertIcon className="mt-px size-3.5 shrink-0" /> {generation.error}
        </p>
      );
    case 'done':
      // A finished generation with no outputs; the API never sends one
      return null;
  }
}

function TileBadge({ children }: { children: ReactNode }) {
  return (
    <span className="flex items-center gap-1 rounded-md bg-black/60 px-1.5 py-0.5 text-[0.6875rem] font-semibold text-white backdrop-blur-sm">
      {children}
    </span>
  );
}

function formatDuration(seconds: number) {
  const s = Math.round(seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}
