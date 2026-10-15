'use client';

import { useRef, useState } from 'react';
import { CheckIcon, ChevronRightIcon, SearchIcon, SparkleIcon } from 'lucide-react';
import { NoodleGlyph } from '@/components/brand-mark';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { capabilityLabels } from '@/lib/capabilities';
import { cn } from '@/lib/utils';
import type { Capability, Workflow } from '@/lib/types';

interface WorkflowMenuProps {
  workflows: Workflow[];
  value: Workflow;
  onChange: (workflow: Workflow) => void;
  className?: string;
}

/** The workflow chip and its searchable menu, grouped by capability. */
export function WorkflowMenu({ workflows, value, onChange, className }: WorkflowMenuProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const searchRef = useRef<HTMLInputElement>(null);

  const terms = query.trim().toLowerCase();
  const groups = new Map<Capability, Workflow[]>();
  for (const workflow of workflows) {
    const text = `${workflow.name} ${workflow.description} ${capabilityLabels[workflow.capability]}`.toLowerCase();
    if (!text.includes(terms)) continue;
    groups.set(workflow.capability, [...(groups.get(workflow.capability) ?? []), workflow]);
  }

  return (
    <Popover
      open={open}
      onOpenChange={next => {
        setOpen(next);
        if (!next) setQuery('');
      }}
    >
      <PopoverTrigger aria-label={`Workflow: ${value.name}`} className={cn('group', className)}>
        <NoodleGlyph className="text-lime" />
        <span className="max-w-44 truncate">{value.name}</span>
        <ChevronRightIcon className="text-[#8a8b8c] transition-transform group-data-[popup-open]:rotate-90" />
      </PopoverTrigger>
      <PopoverContent
        side="top"
        align="start"
        sideOffset={10}
        initialFocus={searchRef}
        className="w-[min(500px,calc(100vw-2rem))] gap-0 overflow-hidden rounded-[20px] border border-white/[0.07] bg-[#25282c]/85 p-0 shadow-[0_24px_60px_rgb(0_0_0/0.6)] ring-0 backdrop-blur-2xl"
      >
        <label className="flex h-[52px] shrink-0 items-center gap-3 border-b border-white/[0.07] px-4">
          <SearchIcon className="size-5 text-[#8a8b8c]" />
          <input
            ref={searchRef}
            value={query}
            onChange={event => setQuery(event.target.value)}
            placeholder="Search..."
            aria-label="Search workflows"
            className="min-w-0 flex-1 bg-transparent text-[17px] outline-none placeholder:text-[#8a8b8c]"
          />
        </label>
        <div className="max-h-[min(460px,calc(var(--available-height)-52px))] overflow-y-auto p-2">
          {[...groups].map(([capability, items]) => (
            <section key={capability} aria-label={capabilityLabels[capability]} className="pb-1">
              <h3 className="flex items-center gap-2 px-2 py-2 text-[15px] text-[#8a8b8c]">
                <SparkleIcon className="size-4 fill-current" />
                {capabilityLabels[capability]}
              </h3>
              <ul className="flex flex-col gap-1">
                {items.map(workflow => {
                  const selected = workflow.id === value.id;
                  return (
                    <li key={workflow.id}>
                      <button
                        type="button"
                        aria-current={selected}
                        onClick={() => {
                          onChange(workflow);
                          setOpen(false);
                        }}
                        className="flex w-full items-center gap-3 rounded-xl p-1.5 pr-3 text-left transition-colors hover:bg-white/[0.05] aria-[current=true]:bg-white/[0.07]"
                      >
                        <span className="flex size-[50px] shrink-0 items-center justify-center rounded-[10px] bg-white/[0.06]">
                          <NoodleGlyph className={cn('size-5', selected ? 'text-lime' : 'text-[#8a8b8c]')} />
                        </span>
                        <span className="flex min-w-0 flex-1 flex-col gap-1">
                          <span className="flex flex-wrap items-center gap-1.5">
                            <span className="text-[15px] font-semibold">{workflow.name}</span>
                            {workflowTags(workflow).map(tag => (
                              <span key={tag} className="rounded-md bg-white/[0.07] px-1.5 py-0.5 text-[11px] leading-none text-[#9a9b9c]">
                                {tag}
                              </span>
                            ))}
                          </span>
                          <span className="truncate text-[13px] text-[#8a8b8c]">{workflow.description}</span>
                        </span>
                        {selected && <CheckIcon className="size-5 shrink-0 text-lime" />}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
          {groups.size === 0 && <p className="px-3 py-6 text-center text-sm text-[#8a8b8c]">No workflows match “{query.trim()}”.</p>}
        </div>
      </PopoverContent>
    </Popover>
  );
}

function workflowTags({ options }: Workflow): string[] {
  const range = (values: string[]) => (values.length > 1 ? `${values[0]}–${values.at(-1)}` : values[0]);
  const tags = [range(options.resolutions)];
  if (options.durations_s.length > 0) tags.push(range(options.durations_s.map(s => `${s}s`)));
  return tags;
}
