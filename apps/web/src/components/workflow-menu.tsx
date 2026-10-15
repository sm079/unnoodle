'use client';

import { useState } from 'react';
import { CheckIcon, ChevronRightIcon, SparkleIcon } from 'lucide-react';
import { m } from 'motion/react';
import { NoodleGlyph } from '@/components/brand-mark';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { RollingValue } from '@/components/rolling-value';
import { capabilityLabels } from '@/lib/capabilities';
import { menuItemClass, menuItemDelay } from '@/lib/motion';
import { cn } from '@/lib/utils';
import type { Capability, Workflow } from '@/lib/types';

interface WorkflowMenuProps {
  /** What the inputs route to, or null when they route nowhere. */
  capability: Capability | null;
  /** The workflows for that capability: one per model. */
  models: Workflow[];
  /** Where the request goes now, or null when the inputs route nowhere. */
  value: Workflow | null;
  /** Why there is no route, or that it is still loading, in its place. */
  note: string | null;
  onChange: (workflow: Workflow) => void;
  className?: string;
}

/**
 * Says what the request will do. Only where several models can do it is it a control, naming the model with a menu to
 * pick another; otherwise it is a line of text, so it doesn't look like something to tap.
 */
export function WorkflowMenu({ capability, models, value, note, onChange, className }: WorkflowMenuProps) {
  const [open, setOpen] = useState(false);
  const doing = capability ? capabilityLabels[capability] : null;

  if (!value || !doing || models.length < 2) {
    return (
      <p className="flex h-9 shrink-0 items-center gap-1.5 rounded-[10px] bg-chip px-3 text-sm font-semibold whitespace-nowrap">
        <NoodleGlyph className={cn('size-4', value ? 'text-lime' : 'text-[#e8a33d]')} />
        <RollingValue value={value && doing ? doing : (note ?? '')} className={cn(!value && 'text-[#e8a33d]')} />
      </p>
    );
  }
  const label = `${doing} · ${value.model_name}`;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        aria-label={`Route: ${label}`}
        // The noodle straightens under the pointer and stays straight while the menu is open
        render={<m.button initial={false} animate={open ? 'straight' : 'tangled'} whileHover="straight" />}
        className={cn('group', className)}
      >
        <NoodleGlyph className="text-lime" />
        <RollingValue value={label} className="max-w-64" />
        <ChevronRightIcon className="text-[#8a8b8c] transition-[rotate] duration-300 ease-spring group-data-[popup-open]:-rotate-90" />
      </PopoverTrigger>
      <PopoverContent
        side="top"
        align="start"
        sideOffset={10}
        className="w-[min(31rem,calc(100vw-2rem))] gap-0 overflow-hidden rounded-[20px] border border-white/[0.07] bg-[#25282c]/85 p-0 shadow-[0_24px_60px_rgb(0_0_0/0.6)] ring-0 backdrop-blur-2xl"
      >
        <section aria-label={doing} className="max-h-[min(28rem,var(--available-height))] overflow-y-auto p-2">
          <h3 className="flex items-center gap-2 px-2 py-2 text-sm text-[#8a8b8c]">
            <SparkleIcon className="size-4 fill-current" />
            {doing}
          </h3>
          <ul className="flex flex-col gap-1">
            {models.map((workflow, index) => {
              const selected = workflow.id === value.id;
              return (
                <li key={workflow.id} style={menuItemDelay(index)} className={menuItemClass}>
                  <m.button
                    type="button"
                    aria-current={selected}
                    onClick={() => {
                      onChange(workflow);
                      setOpen(false);
                    }}
                    // The chosen model's noodle is already straight; the others straighten under the pointer
                    initial={false}
                    animate={selected ? 'straight' : 'tangled'}
                    whileHover="straight"
                    className="group/item flex w-full items-center gap-3 rounded-xl p-1.5 pr-3 text-left transition-[background-color,scale] duration-200 ease-spring hover:bg-white/[0.05] active:scale-[0.98] aria-[current=true]:bg-white/[0.07]"
                  >
                    <span className="flex size-11 shrink-0 items-center justify-center rounded-[10px] bg-white/[0.06] transition-colors duration-200 group-hover/item:bg-white/[0.09]">
                      <NoodleGlyph
                        className={cn(
                          'size-5 transition-colors duration-200',
                          selected ? 'text-lime' : 'text-[#8a8b8c] group-hover/item:text-white'
                        )}
                      />
                    </span>
                    <span className="flex min-w-0 flex-1 flex-col gap-1">
                      <span className="flex flex-wrap items-center gap-1.5">
                        <span className="text-sm font-semibold">{workflow.model_name}</span>
                        {workflowTags(workflow).map(tag => (
                          <span key={tag} className="rounded-md bg-white/[0.07] px-1.5 py-0.5 text-[0.6875rem] leading-none text-[#9a9b9c]">
                            {tag}
                          </span>
                        ))}
                      </span>
                      <span className="truncate text-[0.8125rem] text-[#8a8b8c]">{workflow.description}</span>
                    </span>
                    {selected && <CheckIcon className="size-5 shrink-0 text-lime" />}
                  </m.button>
                </li>
              );
            })}
          </ul>
        </section>
      </PopoverContent>
    </Popover>
  );
}

function workflowTags({ durations_s }: Workflow): string[] {
  if (durations_s.length === 0) return [];
  return [durations_s.length > 1 ? `${durations_s[0]}–${durations_s.at(-1)} sec` : `${durations_s[0]} sec`];
}
