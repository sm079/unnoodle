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
import type { Workflow } from '@/lib/types';

interface WorkflowMenuProps {
  /** The workflows for the capability the inputs route to: one per model. */
  models: Workflow[];
  /** Where the request goes now, or null when the inputs route nowhere. */
  value: Workflow | null;
  onChange: (workflow: Workflow) => void;
  className?: string;
}

/** Shows where the request goes, as "capability · model", and lets the user pick another model that does the same. */
export function WorkflowMenu({ models, value, onChange, className }: WorkflowMenuProps) {
  const [open, setOpen] = useState(false);
  const label = value ? `${capabilityLabels[value.capability]} · ${value.model_name}` : 'No route';

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        aria-label={`Route: ${label}`}
        disabled={!value}
        // The noodle straightens under the pointer and stays straight while the menu is open
        render={<m.button initial={false} animate={open ? 'straight' : 'tangled'} whileHover="straight" />}
        className={cn('group', className)}
      >
        <NoodleGlyph className="text-lime" />
        <RollingValue value={label} className="max-w-64" />
        <ChevronRightIcon className="text-[#8a8b8c] transition-[rotate] duration-300 ease-spring group-data-[popup-open]:-rotate-90" />
      </PopoverTrigger>
      {value && (
        <PopoverContent
          side="top"
          align="start"
          sideOffset={10}
          className="w-[min(500px,calc(100vw-2rem))] gap-0 overflow-hidden rounded-[20px] border border-white/[0.07] bg-[#25282c]/85 p-0 shadow-[0_24px_60px_rgb(0_0_0/0.6)] ring-0 backdrop-blur-2xl"
        >
          <section aria-label={capabilityLabels[value.capability]} className="max-h-[min(460px,var(--available-height))] overflow-y-auto p-2">
            <h3 className="flex items-center gap-2 px-2 py-2 text-[15px] text-[#8a8b8c]">
              <SparkleIcon className="size-4 fill-current" />
              {capabilityLabels[value.capability]}
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
                      <span className="flex size-[50px] shrink-0 items-center justify-center rounded-[10px] bg-white/[0.06] transition-colors duration-200 group-hover/item:bg-white/[0.09]">
                        <NoodleGlyph
                          className={cn(
                            'size-5 transition-colors duration-200',
                            selected ? 'text-lime' : 'text-[#8a8b8c] group-hover/item:text-white'
                          )}
                        />
                      </span>
                      <span className="flex min-w-0 flex-1 flex-col gap-1">
                        <span className="flex flex-wrap items-center gap-1.5">
                          <span className="text-[15px] font-semibold">{workflow.model_name}</span>
                          {workflowTags(workflow).map(tag => (
                            <span key={tag} className="rounded-md bg-white/[0.07] px-1.5 py-0.5 text-[11px] leading-none text-[#9a9b9c]">
                              {tag}
                            </span>
                          ))}
                        </span>
                        <span className="truncate text-[13px] text-[#8a8b8c]">{workflow.description}</span>
                      </span>
                      {selected && <CheckIcon className="size-5 shrink-0 text-lime" />}
                    </m.button>
                  </li>
                );
              })}
            </ul>
          </section>
        </PopoverContent>
      )}
    </Popover>
  );
}

function workflowTags({ resolutions, durations_s }: Workflow): string[] {
  const range = (values: string[]) => (values.length > 1 ? `${values[0]}–${values.at(-1)}` : values[0]);
  const tags = [range(Object.keys(resolutions))];
  if (durations_s.length > 0) tags.push(range(durations_s.map(s => `${s}s`)));
  return tags;
}
