'use client';

import { useState, type FormEvent, type ReactNode } from 'react';
import Image from 'next/image';
import { ArrowUpIcon, ChevronDownIcon, ClockIcon, LayersIcon, PlusIcon, RatioIcon, ScanIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { capabilityLabels, roleLabels } from '@/lib/capabilities';
import type { ComposerDraft, GenerationParams, MediaType, Workflow } from '@/lib/types';

interface ComposerProps {
  drafts: Record<MediaType, ComposerDraft>;
  workflows: Workflow[];
}

export function Composer({ drafts, workflows }: ComposerProps) {
  const [mode, setMode] = useState<MediaType>('video');
  const [prompts, setPrompts] = useState<Record<MediaType, string>>({ image: drafts.image.prompt, video: drafts.video.prompt });

  const draft = drafts[mode];
  const prompt = prompts[mode];
  const workflow = workflows.find(w => w.id === draft.workflow_id);

  function submit(event: FormEvent) {
    // Nothing to send to until the API exists
    event.preventDefault();
  }

  return (
    <form onSubmit={submit} aria-label="Composer" className="shrink-0 border-t bg-background p-2">
      <div className="mx-auto flex max-w-3xl flex-col gap-2 rounded-xl bg-card p-2">
        <div className="flex items-center justify-between gap-2">
          <ToggleGroup
            value={[mode]}
            onValueChange={([next]) => {
              // Pressing the selected item again empties the group; keep the current mode then
              if (next === 'image' || next === 'video') setMode(next);
            }}
            variant="outline"
            size="sm"
            spacing={0}
            aria-label="Output type"
          >
            {(['image', 'video'] as const).map(type => (
              <ToggleGroupItem
                key={type}
                value={type}
                className="text-muted-foreground capitalize aria-pressed:bg-foreground/15 aria-pressed:text-foreground"
              >
                {type}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          {workflow && (
            <Button type="button" variant="ghost" size="sm" className="min-w-0 text-muted-foreground">
              <span className="truncate">
                → {capabilityLabels[workflow.capability]} · {workflow.name}
              </span>
              <ChevronDownIcon />
            </Button>
          )}
        </div>

        {draft.inputs.length > 0 && (
          <ul aria-label="Inputs" className="flex gap-2 overflow-x-auto">
            {draft.inputs.map(input => (
              <li key={`${input.role}-${input.asset.id}`} className="flex w-16 shrink-0 flex-col gap-1">
                <div className="relative aspect-square overflow-hidden rounded-md bg-muted">
                  <Image src={input.asset.thumbnail_url} alt="" fill sizes="64px" className="object-cover" />
                </div>
                <span className="truncate text-[11px] text-muted-foreground">
                  {roleLabels[input.role]}
                  {input.position_s !== null && ` · ${input.position_s}s`}
                </span>
              </li>
            ))}
          </ul>
        )}

        <Textarea
          value={prompt}
          onChange={event => setPrompts({ ...prompts, [mode]: event.target.value })}
          placeholder={mode === 'video' ? 'Describe the shot' : 'Describe the image'}
          aria-label="Prompt"
          rows={2}
          className="max-h-40 min-h-0 resize-none border-0 bg-transparent px-1 dark:bg-transparent"
        />

        <div className="flex items-center gap-2">
          <Button type="button" variant="outline" size="icon" aria-label="Add input">
            <PlusIcon />
          </Button>
          <div className="flex min-w-0 flex-1 gap-1.5 overflow-x-auto">
            <SettingChips mode={mode} params={draft.params} />
          </div>
          <Button type="submit" size="icon" aria-label="Generate" disabled={prompt.trim() === ''}>
            <ArrowUpIcon />
          </Button>
        </div>
      </div>
    </form>
  );
}

function SettingChips({ mode, params }: { mode: MediaType; params: GenerationParams }) {
  return (
    <>
      <Chip icon={<RatioIcon />} label={params.aspect_ratio} />
      <Chip icon={<ScanIcon />} label={params.resolution} />
      {mode === 'video' ? (
        <Chip icon={<ClockIcon />} label={`${params.duration_s}s`} />
      ) : (
        <Chip icon={<LayersIcon />} label={`×${params.count}`} />
      )}
    </>
  );
}

function Chip({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <Button type="button" variant="secondary" size="sm" className="shrink-0">
      {icon}
      {label}
    </Button>
  );
}
