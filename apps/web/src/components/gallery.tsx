import type { ReactNode } from 'react';
import Image from 'next/image';
import { ClockIcon, ImageIcon, LoaderCircleIcon, PlayIcon, TriangleAlertIcon, VideoIcon } from 'lucide-react';
import { outputType } from '@/lib/capabilities';
import type { Generation } from '@/lib/types';

export function Gallery({ generations }: { generations: Generation[] }) {
  return (
    <ul aria-label="Gallery" className="grid grid-cols-2 gap-1 p-1 sm:grid-cols-3 lg:grid-cols-4">
      {generations.map(generation => (
        <li key={generation.id}>
          <GalleryTile generation={generation} />
        </li>
      ))}
    </ul>
  );
}

function GalleryTile({ generation }: { generation: Generation }) {
  const cover = generation.outputs[0];

  if (generation.status === 'done' && cover) {
    return (
      <div className="relative aspect-square overflow-hidden rounded-md bg-muted">
        <Image
          src={cover.thumbnail_url}
          alt={generation.prompt}
          fill
          sizes="(min-width: 1024px) 25vw, (min-width: 640px) 33vw, 50vw"
          className="object-cover"
        />
        <div className="absolute inset-x-1.5 top-1.5 flex justify-between">
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
      </div>
    );
  }

  const TypeIcon = outputType(generation.capability) === 'video' ? VideoIcon : ImageIcon;

  return (
    <div className="flex aspect-square flex-col gap-2 rounded-md bg-muted p-3 text-xs">
      <TypeIcon className="size-4 text-muted-foreground" aria-hidden />
      <div className="mt-auto flex flex-col gap-1.5">
        <StatusLine generation={generation} />
        <p className="line-clamp-3 text-muted-foreground">{generation.prompt}</p>
      </div>
    </div>
  );
}

function StatusLine({ generation }: { generation: Generation }) {
  switch (generation.status) {
    case 'queued':
      return (
        <p className="flex items-center gap-1.5 font-medium">
          <ClockIcon className="size-3.5" /> Queued
        </p>
      );
    case 'running': {
      const percent = Math.round((generation.progress ?? 0) * 100);
      return (
        <div className="flex flex-col gap-1.5">
          <p className="flex items-center gap-1.5 font-medium">
            <LoaderCircleIcon className="size-3.5 animate-spin" /> Generating · {percent}%
          </p>
          <div
            role="progressbar"
            aria-valuenow={percent}
            aria-valuemin={0}
            aria-valuemax={100}
            className="h-1 rounded-full bg-foreground/10"
          >
            <div className="h-full rounded-full bg-foreground" style={{ width: `${percent}%` }} />
          </div>
        </div>
      );
    }
    case 'failed':
      return (
        <p className="flex items-start gap-1.5 font-medium text-destructive">
          <TriangleAlertIcon className="size-3.5 shrink-0" /> {generation.error}
        </p>
      );
    case 'done':
      // A finished generation with no outputs; the API never sends one
      return null;
  }
}

function TileBadge({ children }: { children: ReactNode }) {
  return (
    <span className="flex items-center gap-1 rounded-sm bg-black/60 px-1.5 py-0.5 text-[11px] font-medium text-white">{children}</span>
  );
}

function formatDuration(seconds: number) {
  const s = Math.round(seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}
