'use client';

import { useState, type ReactNode } from 'react';
import Image from 'next/image';
import { DownloadIcon, ImagePlusIcon } from 'lucide-react';
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet';
import { capabilityLabels, outputType, qualityLabels, shapeLabels } from '@/lib/capabilities';
import { handleOf, mentionPattern } from '@/lib/mentions';
import type { Asset, Generation } from '@/lib/types';

interface ResultViewProps {
  /** Kept while the view closes, so it slides away with its content. */
  generation: Generation | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Attaches the output to the composer; the view closes. */
  onUseAsInput: (asset: Asset) => void;
}

/** A finished generation: its output, what it was asked for and with which settings, and what to do with it next. */
export function ResultView({ generation, open, onOpenChange, onUseAsInput }: ResultViewProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="bottom"
        className="mx-auto max-h-[94dvh] max-w-5xl gap-0 overflow-y-auto overscroll-contain rounded-t-[28px] border-0 bg-panel pb-[env(safe-area-inset-bottom)] lg:flex-row lg:overflow-hidden"
      >
        <SheetTitle className="sr-only">Result</SheetTitle>
        {generation && (
          // Keyed, so another generation starts on its first output
          <Result
            key={generation.id}
            generation={generation}
            onUseAsInput={asset => {
              onUseAsInput(asset);
              onOpenChange(false);
            }}
          />
        )}
      </SheetContent>
    </Sheet>
  );
}

function Result({ generation, onUseAsInput }: { generation: Generation; onUseAsInput: (asset: Asset) => void }) {
  const [shown, setShown] = useState(0);
  const output = generation.outputs[shown] ?? generation.outputs[0];
  const kinds = generation.inputs.map(i => i.asset.media_type);
  const handles = kinds.map((_, index) => handleOf(kinds, index));
  const { params } = generation;
  const shape = params.aspect_ratio ? shapeLabels[params.aspect_ratio] : handles[0] && `Same as ${handles[0]}`;
  const made = new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' });

  if (!output) return null;

  return (
    <>
      <div className="flex shrink-0 flex-col gap-2 bg-black/40 p-2 pt-12 lg:flex-1 lg:justify-center lg:p-4">
        <div className="flex justify-center">
          {output.media_type === 'video' ? (
            <video
              key={output.id}
              src={output.url}
              poster={output.thumbnail_url}
              controls
              playsInline
              preload="metadata"
              width={output.width}
              height={output.height}
              style={{ aspectRatio: `${output.width} / ${output.height}` }}
              className="h-auto max-h-[60dvh] w-auto max-w-full rounded-2xl bg-black lg:max-h-[80dvh]"
            />
          ) : (
            <Image
              key={output.id}
              src={output.url}
              alt={generation.prompt}
              width={output.width}
              height={output.height}
              sizes="(min-width: 1024px) 40rem, 100vw"
              className="h-auto max-h-[60dvh] w-auto max-w-full rounded-2xl lg:max-h-[80dvh]"
            />
          )}
        </div>
        {/* Made before each generation had one output */}
        {generation.outputs.length > 1 && (
          <div role="group" aria-label="Outputs" className="no-scrollbar flex justify-center gap-1.5 overflow-x-auto">
            {generation.outputs.map((asset, index) => (
              <button
                key={asset.id}
                type="button"
                aria-label={`Output ${index + 1} of ${generation.outputs.length}`}
                aria-pressed={index === shown}
                onClick={() => setShown(index)}
                className="relative size-12 shrink-0 overflow-hidden rounded-lg opacity-50 transition-[opacity,scale] duration-200 ease-spring active:scale-90 aria-pressed:opacity-100 aria-pressed:ring-2 aria-pressed:ring-brand"
              >
                <Image src={asset.thumbnail_url} alt="" fill sizes="48px" className="object-cover" />
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="flex flex-col gap-5 p-4 lg:w-80 lg:shrink-0 lg:overflow-y-auto lg:pt-14">
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => onUseAsInput(output)}
            className="flex h-11 flex-1 items-center justify-center gap-2 rounded-[14px] bg-brand text-sm font-bold text-white transition-[scale,filter] duration-200 ease-spring hover:brightness-105 active:scale-[0.97]"
          >
            <ImagePlusIcon className="size-4" />
            Use as input
          </button>
          <a
            href={output.url}
            download={fileName(generation, output, shown)}
            aria-label="Download"
            className="flex size-11 shrink-0 items-center justify-center rounded-[14px] bg-chip text-white transition-[background-color,scale] duration-200 ease-spring hover:bg-[#3b3c3e] active:scale-[0.95]"
          >
            <DownloadIcon className="size-4.5" />
          </a>
        </div>

        <p className="text-base leading-snug whitespace-pre-wrap">
          <Prompt text={generation.prompt} handles={handles} />
        </p>

        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
          <Detail term="Made">{capabilityLabels[generation.capability]}</Detail>
          <Detail term="Quality">{qualityLabels[params.quality]}</Detail>
          {shape && <Detail term="Shape">{shape}</Detail>}
          {outputType(generation.capability) === 'video' && params.duration_s != null && (
            <Detail term="Length">{params.duration_s} sec</Detail>
          )}
          <Detail term="When">{made.format(new Date(generation.finished_at ?? generation.created_at))}</Detail>
        </dl>

        {generation.inputs.length > 0 && (
          <div className="flex flex-col gap-2">
            <p className="text-sm text-[#8a8b8c]">Used</p>
            <ul aria-label="Used" className="flex flex-wrap gap-2">
              {generation.inputs.map(({ asset }, index) => (
                <li key={`${asset.id}-${index}`} className="flex items-center gap-1 rounded-xl bg-chip p-1 pr-2">
                  <Image
                    src={asset.thumbnail_url}
                    alt=""
                    width={36}
                    height={36}
                    className="size-9 max-w-none rounded-lg bg-muted object-cover"
                  />
                  <Handle>{handles[index]}</Handle>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </>
  );
}

/** The prompt as typed, with the handles of what it used shown the way the composer shows them. */
function Prompt({ text, handles }: { text: string; handles: string[] }) {
  return text
    .split(mentionPattern)
    .map((part, index) => (index % 2 === 1 && handles.includes(part) ? <Handle key={index}>{part}</Handle> : part));
}

function Handle({ children }: { children: ReactNode }) {
  return (
    <span className="rounded-md bg-brand/12 px-1.5 py-0.5 text-[0.8125rem] font-semibold whitespace-nowrap text-brand">{children}</span>
  );
}

function Detail({ term, children }: { term: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-[#8a8b8c]">{term}</dt>
      <dd className="font-medium">{children}</dd>
    </>
  );
}

/** "unnoodle-3f2a9c1d.png", or "-2" and on for the later outputs of an old generation. */
function fileName(generation: Generation, asset: Asset, index: number) {
  const extension = asset.url.match(/\.\w+$/)?.[0] ?? '';
  return `unnoodle-${generation.id.slice(0, 8)}${index > 0 ? `-${index + 1}` : ''}${extension}`;
}
