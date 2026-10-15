'use client';

import { useRef, useState, type ChangeEvent, type FormEvent, type ReactNode } from 'react';
import Image from 'next/image';
import { AnimatePresence, m } from 'motion/react';
import {
  ChevronDownIcon,
  ChevronRightIcon,
  ClockIcon,
  FocusIcon,
  GemIcon,
  ImageIcon,
  MinusIcon,
  PlusIcon,
  VideoIcon,
  Volume2Icon,
  VolumeXIcon,
  XIcon
} from 'lucide-react';
import { RollingValue } from '@/components/rolling-value';
import { WorkflowMenu } from '@/components/workflow-menu';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Textarea } from '@/components/ui/textarea';
import { defaultRole, roleLabels } from '@/lib/capabilities';
import { menuItemClass, menuItemDelay } from '@/lib/motion';
import { rolesFor, route } from '@/lib/routing';
import { cn } from '@/lib/utils';
import type { AspectRatio, Asset, InputRole, MediaType, Workflow } from '@/lib/types';

interface ComposerProps {
  workflows: Workflow[];
  /** Earlier uploads that can be attached again. */
  library: Asset[];
}

interface DraftInput {
  /** Identifies the chip while it animates in and out; the same asset can be attached twice. */
  key: string;
  asset: Asset;
  role: InputRole;
  /** Seconds into the clip. Keyframes only. */
  position_s: number | null;
}

/** What the user picked. Each render fits it to the settings the routed workflow offers. */
interface Settings {
  aspect_ratio: AspectRatio;
  resolution: string;
  duration_s: number;
  count: number;
  audio: boolean;
}

interface Draft {
  prompt: string;
  inputs: DraftInput[];
  /** A model picked from the menu, or null for the default of whatever the inputs route to. */
  model: string | null;
  settings: Settings;
}

const modeLabels: Record<MediaType, string> = { image: 'Image', video: 'Video' };

const placeholders: Record<MediaType, string> = {
  image: 'Describe the image you want to create...',
  video: 'Describe the video you want to create...'
};

const initialDrafts: Record<MediaType, Draft> = {
  image: {
    prompt: '',
    inputs: [],
    model: null,
    settings: { aspect_ratio: '3:4', resolution: '1K', duration_s: 5, count: 1, audio: false }
  },
  video: {
    prompt: '',
    inputs: [],
    model: null,
    settings: { aspect_ratio: '16:9', resolution: '720p', duration_s: 5, count: 1, audio: true }
  }
};

// Enough for the keyframe workflows; nothing else takes more
const MAX_INPUTS = 8;

let lastInputKey = 0;
const nextKey = () => `input-${++lastInputKey}`;

export function Composer({ workflows, library }: ComposerProps) {
  const [mode, setMode] = useState<MediaType>('video');
  const [drafts, setDrafts] = useState(initialDrafts);
  const promptRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const draft = drafts[mode];
  const routed = route(workflows, mode, draft.inputs.map(i => i.role), draft.model);
  const workflow = routed.ok ? routed.value : null;
  const settings = workflow ? fitSettings(draft.settings, workflow) : draft.settings;
  const full = draft.inputs.length >= MAX_INPUTS;

  function update(patch: Partial<Draft>) {
    setDrafts(current => ({ ...current, [mode]: { ...current[mode], ...patch } }));
  }

  function setSetting<K extends keyof Settings>(key: K, value: Settings[K]) {
    // Fitted values are kept too, so a later change of workflow starts from what was on screen
    update({ settings: { ...settings, [key]: value } });
  }

  function attach(assets: Asset[]) {
    const inputs = [...draft.inputs];
    for (const asset of assets.slice(0, MAX_INPUTS - inputs.length)) {
      const role = defaultRole(
        mode,
        inputs.map(i => i.role),
        asset
      );
      inputs.push({ key: nextKey(), asset, role, position_s: null });
    }
    // The model menu only lists models for the new route, so a model picked for the old one no longer applies
    update({ inputs, model: null });
  }

  function detach(index: number) {
    const { asset } = draft.inputs[index];
    if (asset.url.startsWith('blob:')) URL.revokeObjectURL(asset.url);
    update({ inputs: draft.inputs.filter((_, i) => i !== index), model: null });
  }

  function setRole(index: number, role: InputRole) {
    // Keyframes go a second apart until there is a timeline to place them on
    const keyframes = draft.inputs.filter((input, i) => i !== index && input.role === 'keyframe').length;
    const inputs = draft.inputs.map((input, i) =>
      i === index ? { ...input, role, position_s: role === 'keyframe' ? keyframes : null } : input
    );
    update({ inputs, model: null });
  }

  function attachFiles(event: ChangeEvent<HTMLInputElement>) {
    attach(Array.from(event.target.files ?? [], fileAsset));
    event.target.value = '';
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (draft.prompt.trim() === '') {
      promptRef.current?.focus();
      shake(promptRef.current);
    }
  }

  return (
    <form onSubmit={submit} aria-label="Composer" className="flex w-full flex-col gap-1.5 lg:flex-row lg:items-end">
      <div
        role="group"
        aria-label="Output type"
        data-mode={mode}
        className="group/mode relative flex gap-1 rounded-[22px] bg-panel p-1.5 lg:h-[140px] lg:w-[88px] lg:shrink-0 lg:flex-col lg:rounded-[28px]"
      >
        {/* The backing of the chosen type slides between the two buttons */}
        <span
          aria-hidden
          className="absolute top-1.5 left-1.5 h-10 w-[calc(50%-8px)] rounded-2xl bg-panel-raised shadow-[inset_0_1px_0_rgb(255_255_255/0.06)] transition-[translate] duration-500 ease-spring group-data-[mode=video]/mode:translate-x-[calc(100%+4px)] motion-reduce:transition-none lg:h-[calc(50%-8px)] lg:w-[calc(100%-12px)] lg:rounded-[22px] lg:group-data-[mode=video]/mode:translate-x-0 lg:group-data-[mode=video]/mode:translate-y-[calc(100%+4px)]"
        />
        {(['image', 'video'] as const).map(type => {
          const Icon = type === 'image' ? ImageIcon : VideoIcon;
          return (
            <button
              key={type}
              type="button"
              aria-pressed={mode === type}
              onClick={() => setMode(type)}
              className="relative flex h-10 flex-1 items-center justify-center gap-2 rounded-2xl text-[13px] font-semibold text-[#8a8b8c] transition-[color,scale] duration-200 ease-out-quint hover:text-foreground active:scale-95 aria-pressed:text-foreground lg:h-auto lg:flex-col lg:gap-1.5 lg:rounded-[22px] motion-safe:aria-pressed:[&_svg]:animate-pop"
            >
              <Icon className="size-4" />
              {modeLabels[type]}
            </button>
          );
        })}
      </div>

      <div className="min-w-0 flex-1 rounded-[26px] bg-panel p-[5px] transition-shadow duration-300 has-[textarea:focus-visible]:shadow-[inset_0_0_0_1px_rgb(255_255_255/0.07)] lg:rounded-[30px]">
        <AnimatePresence initial={false}>
          {mode === 'video' && (
            <m.div
              key="frames"
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0, transition: { duration: 0.22, ease: easeOutQuint } }}
              transition={{ type: 'spring', bounce: 0, visualDuration: 0.4 }}
              className="overflow-hidden"
            >
              <div className="no-scrollbar flex gap-1.5 overflow-x-auto p-[5px] pb-2.5">
                <div className={cn(cardClass, enterClass, 'w-40 shrink-0')}>
                  <button
                    type="button"
                    aria-label="Add frames"
                    disabled={full}
                    onClick={() => fileRef.current?.click()}
                    className="group/add flex size-10 shrink-0 items-center justify-center rounded-[10px] bg-[#19191b] text-[#b5b5b5] shadow-[inset_0_1px_0_rgb(255_255_255/0.08)] ring-1 ring-white/10 transition-[color,scale] duration-150 hover:text-white active:scale-90 disabled:opacity-40"
                  >
                    <PlusIcon className="size-5 transition-[rotate] duration-500 ease-spring-bouncy group-hover/add:rotate-90 group-disabled/add:rotate-0" />
                  </button>
                  <CardText label="Frames" value={String(draft.inputs.length)} />
                </div>
              </div>
            </m.div>
          )}
        </AnimatePresence>

        <div className="flex flex-col gap-3 rounded-[22px] bg-panel-raised p-3 lg:flex-row lg:items-end lg:gap-2 lg:rounded-[24px] lg:py-3.5 lg:pr-3 lg:pl-4">
          <div className="flex min-w-0 flex-1 flex-col gap-3 lg:self-stretch">
            <AnimatePresence initial={false}>
              {draft.inputs.length > 0 && (
                <m.div
                  key="inputs"
                  // The negative margin cancels the column gap, so the gap closes along with the row
                  initial={{ height: 0, opacity: 0, marginBottom: -12 }}
                  animate={{ height: 'auto', opacity: 1, marginBottom: 0 }}
                  exit={{ height: 0, opacity: 0, marginBottom: -12 }}
                  className="overflow-hidden"
                >
                  <ul aria-label="Inputs" className="no-scrollbar flex overflow-x-auto">
                    <AnimatePresence initial={false}>
                      {draft.inputs.map((input, index) => (
                        <m.li
                          key={input.key}
                          initial={{ width: 0, opacity: 0, scale: 0.6 }}
                          animate={{ width: 'auto', opacity: 1, scale: 1 }}
                          exit={{ width: 0, opacity: 0, scale: 0.6 }}
                          // Clips the chip while the slot opens and closes around it
                          className="shrink-0 origin-left overflow-hidden pr-2"
                        >
                          <div className="flex w-max items-center gap-1 rounded-xl bg-chip p-1 pr-1.5">
                            <Thumbnail asset={input.asset} />
                            <RoleMenu
                              roles={rolesFor[mode]}
                              value={input.role}
                              position={input.position_s}
                              onChange={role => setRole(index, role)}
                            />
                            <button
                              type="button"
                              aria-label={`Remove ${roleLabels[input.role].toLowerCase()}`}
                              onClick={() => detach(index)}
                              className="flex size-6 items-center justify-center rounded-md text-[#8a8b8c] transition-[color,background-color,scale] duration-150 hover:bg-white/10 hover:text-white active:scale-85"
                            >
                              <XIcon className="size-3.5" />
                            </button>
                          </div>
                        </m.li>
                      ))}
                    </AnimatePresence>
                  </ul>
                </m.div>
              )}
            </AnimatePresence>

            <Textarea
              ref={promptRef}
              value={draft.prompt}
              onChange={event => update({ prompt: event.target.value })}
              placeholder={placeholders[mode]}
              aria-label="Prompt"
              className="max-h-48 min-h-14 flex-1 resize-none rounded-none border-0 bg-transparent px-1 py-0.5 text-[17px] leading-snug placeholder:text-[#7c7d7f] focus-visible:ring-0 md:text-[17px] dark:bg-transparent"
            />

            <div className="-mx-3 no-scrollbar flex gap-[7px] overflow-x-auto px-3 lg:mx-0 lg:px-0">
              <button
                type="button"
                aria-label="Attach files"
                disabled={full}
                onClick={() => fileRef.current?.click()}
                className={cn(chipClass, 'w-[35px] justify-center px-0')}
              >
                <PlusIcon />
              </button>
              <LibraryPicker assets={library} disabled={full} onPick={asset => attach([asset])} />
              <WorkflowMenu
                models={workflow ? workflows.filter(w => w.capability === workflow.capability) : []}
                value={workflow}
                onChange={next => update({ model: next.model })}
                className={cn(chipClass, 'px-3')}
              />
              {workflow && (
                <>
                  <OptionChip
                    label="Resolution"
                    icon={<GemIcon />}
                    value={settings.resolution}
                    options={Object.keys(workflow.resolutions)}
                    onChange={value => setSetting('resolution', value)}
                  />
                  <OptionChip
                    label="Aspect ratio"
                    icon={<AspectIcon ratio={settings.aspect_ratio} />}
                    value={settings.aspect_ratio}
                    options={workflow.resolutions[settings.resolution]}
                    onChange={value => setSetting('aspect_ratio', value as AspectRatio)}
                  />
                  {workflow.durations_s.length > 0 && (
                    <OptionChip
                      label="Duration"
                      icon={<ClockIcon strokeWidth={2.5} />}
                      value={`${settings.duration_s}s`}
                      options={workflow.durations_s.map(s => `${s}s`)}
                      onChange={value => setSetting('duration_s', parseFloat(value))}
                      className={enterClass}
                    />
                  )}
                  {workflow.audio && (
                    <button
                      type="button"
                      aria-label="Sound"
                      aria-pressed={settings.audio}
                      onClick={() => setSetting('audio', !settings.audio)}
                      className={cn(chipClass, enterClass)}
                    >
                      {settings.audio ? <Volume2Icon /> : <VolumeXIcon />}
                      <RollingValue value={settings.audio ? 'On' : 'Off'} />
                    </button>
                  )}
                  {workflow.max_count > 1 &&
                    (mode === 'video' ? (
                      <CountStepper
                        count={settings.count}
                        max={workflow.max_count}
                        onChange={count => setSetting('count', count)}
                        className={enterClass}
                      />
                    ) : (
                      <Popover>
                        <PopoverTrigger
                          aria-label="More settings"
                          className={cn(chipClass, enterClass, 'group/more w-[35px] justify-center px-0')}
                        >
                          <ChevronRightIcon className="transition-[rotate] duration-300 ease-spring group-data-[popup-open]/more:-rotate-90" />
                        </PopoverTrigger>
                        <PopoverContent
                          side="top"
                          align="start"
                          sideOffset={8}
                          className={cn(menuClass, 'w-auto flex-row items-center gap-3 p-2 pl-3.5')}
                        >
                          <span className="text-sm text-[#8a8b8c]">Outputs</span>
                          <CountStepper count={settings.count} max={workflow.max_count} onChange={count => setSetting('count', count)} />
                        </PopoverContent>
                      </Popover>
                    ))}
                </>
              )}
            </div>
          </div>

          <button
            type="submit"
            aria-disabled={!workflow}
            className="group/generate relative mb-[3px] flex h-14 w-full shrink-0 items-center justify-center gap-3 overflow-hidden rounded-[14px] bg-linear-to-b from-[#d8ff17] via-[#f4ff1f] to-[#ffff17] text-[#191b04] shadow-[0_3px_0_var(--color-lime-edge),0_10px_20px_rgb(0_0_0/0.45)] transition-[translate,box-shadow,filter,opacity] duration-300 ease-spring hover:shadow-[0_3px_0_var(--color-lime-edge),0_10px_28px_rgb(220_255_23/0.2)] hover:brightness-105 active:translate-y-[2px] active:shadow-[0_1px_0_var(--color-lime-edge),0_4px_10px_rgb(0_0_0/0.4)] active:duration-75 active:ease-out aria-disabled:pointer-events-none aria-disabled:opacity-40 lg:h-24 lg:w-40"
          >
            {/* A glint crosses the button as the pointer arrives */}
            <span
              aria-hidden
              className="pointer-events-none absolute inset-0 -translate-x-[120%] bg-linear-to-r from-transparent from-30% via-white/60 to-transparent to-70% motion-safe:group-hover/generate:animate-sheen"
            />
            <span className="font-display text-[15px] font-extrabold tracking-[0.02em] uppercase font-stretch-[88%]">Generate</span>
          </button>
        </div>

        {!routed.ok && (
          <p role="status" className="px-3 pt-2 pb-1 text-sm text-[#e8a33d]">
            {routed.error}
          </p>
        )}
      </div>

      <input ref={fileRef} type="file" accept="image/*,video/*" multiple hidden onChange={attachFiles} />
    </form>
  );
}

// Controls dip slightly while pressed and spring back on release
const chipClass =
  "flex h-[35px] shrink-0 items-center gap-1.5 rounded-[10px] bg-chip px-2.5 text-[15px] font-bold whitespace-nowrap text-white transition-[color,background-color,scale] duration-200 ease-spring outline-none hover:bg-[#3b3c3e] focus-visible:ring-2 focus-visible:ring-white/30 active:scale-[0.95] active:duration-100 disabled:opacity-40 data-[popup-open]:bg-[#3b3c3e] [&_svg:not([class*='size-'])]:size-[18px] [&_svg]:shrink-0";
const cardClass =
  'flex h-[60px] items-center gap-2.5 rounded-[18px] bg-panel-raised px-2.5 transition-[background-color,scale] duration-200 ease-spring outline-none focus-visible:ring-2 focus-visible:ring-white/30';
// Controls that come and go with the output type rise into place, one after another
const enterClass = 'motion-safe:animate-rise [--rise-blur:3px] [--rise-distance:8px] [animation-duration:450ms]';
const easeOutQuint = [0.23, 1, 0.32, 1] as const;
const menuClass =
  'rounded-2xl border border-white/[0.07] bg-[#25282c]/90 p-1.5 shadow-[0_18px_40px_rgb(0_0_0/0.55)] ring-0 backdrop-blur-xl';

/** The picked settings, moved to the nearest ones the workflow offers. */
export function fitSettings(settings: Settings, workflow: Workflow): Settings {
  const pick = <T,>(value: T, allowed: T[]) => (allowed.includes(value) ? value : allowed[0]);
  const resolution = pick(settings.resolution, Object.keys(workflow.resolutions));
  return {
    resolution,
    aspect_ratio: pick(settings.aspect_ratio, workflow.resolutions[resolution]),
    duration_s: workflow.durations_s.length > 0 ? pick(settings.duration_s, workflow.durations_s) : settings.duration_s,
    count: Math.min(settings.count, workflow.max_count),
    audio: workflow.audio && settings.audio
  };
}

/** A short head shake: the prompt is needed before anything can be generated. */
function shake(element: HTMLElement | null) {
  if (!element || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  element.animate({ translate: ['0', '-6px', '5px', '-3px', '2px', '0'] }, { duration: 400, easing: 'ease-out' });
}

function fileAsset(file: File): Asset {
  const url = URL.createObjectURL(file);
  return {
    id: `local_${crypto.randomUUID()}`,
    media_type: file.type.startsWith('video/') ? 'video' : 'image',
    source: 'upload',
    url,
    thumbnail_url: url,
    width: 0,
    height: 0,
    duration_s: null,
    created_at: new Date().toISOString()
  };
}

function CardText({ label, value }: { label: string; value: string }) {
  return (
    <span className="flex min-w-0 flex-col">
      <span className="truncate font-mono text-[11px] text-[#6d6e70]">{label}</span>
      <RollingValue value={value} className="text-[17px] leading-tight font-bold" />
    </span>
  );
}

/** The role an input plays, as a chip that opens the roles it could play instead. */
function RoleMenu({
  roles,
  value,
  position,
  onChange
}: {
  roles: InputRole[];
  value: InputRole;
  position: number | null;
  onChange: (role: InputRole) => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label={`Role: ${roleLabels[value]}`}
        className="group/role flex items-center gap-0.5 rounded-md py-0.5 pr-0.5 pl-1.5 text-[13px] font-semibold whitespace-nowrap transition-colors duration-150 outline-none hover:bg-white/10 focus-visible:ring-2 focus-visible:ring-white/30 data-[popup-open]:bg-white/10"
      >
        <RollingValue value={roleLabels[value]} />
        {position !== null && <span className="text-[#8a8b8c]">&nbsp;· {position}s</span>}
        <ChevronDownIcon className="size-3.5 text-[#8a8b8c] transition-[rotate] duration-300 ease-spring group-data-[popup-open]/role:rotate-180" />
      </DropdownMenuTrigger>
      <OptionList
        label="Role"
        value={value}
        options={roles}
        labels={roleLabels}
        onChange={role => onChange(role as InputRole)}
      />
    </DropdownMenu>
  );
}

function OptionChip({
  label,
  icon,
  value,
  options,
  onChange,
  className
}: {
  label: string;
  icon: ReactNode;
  value: string;
  options: string[];
  onChange: (value: string) => void;
  className?: string;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger aria-label={`${label}: ${value}`} className={cn(chipClass, className)}>
        {icon}
        <RollingValue value={value} />
      </DropdownMenuTrigger>
      <OptionList label={label} value={value} options={options} onChange={onChange} />
    </DropdownMenu>
  );
}

function OptionList({
  label,
  value,
  options,
  labels,
  onChange
}: {
  label: string;
  value: string;
  options: string[];
  /** Shown in place of the values, where they aren't words. */
  labels?: Record<string, string>;
  onChange: (value: string) => void;
}) {
  return (
    <DropdownMenuContent side="top" sideOffset={8} aria-label={label} className={cn(menuClass, 'w-auto min-w-40')}>
      <DropdownMenuRadioGroup value={value} onValueChange={next => onChange(String(next))}>
        {options.map((option, index) => (
          <DropdownMenuRadioItem
            key={option}
            value={option}
            // One choice per menu, so picking it is done with the menu
            closeOnClick
            style={menuItemDelay(index)}
            className={cn(menuItemClass, 'h-9 rounded-[10px] px-2.5 text-sm font-medium transition-colors focus:bg-white/[0.07]')}
          >
            {labels?.[option] ?? option}
          </DropdownMenuRadioItem>
        ))}
      </DropdownMenuRadioGroup>
    </DropdownMenuContent>
  );
}

/** A frame drawn at the exact ratio; it reshapes itself when the ratio changes. */
function AspectIcon({ ratio }: { ratio: AspectRatio }) {
  const [width, height] = ratio.split(':').map(Number);
  const fit = 14 / Math.max(width, height);
  return (
    <span aria-hidden className="flex size-[18px] shrink-0 items-center justify-center">
      <span
        className="rounded-[3px] border-2 border-current transition-[width,height] duration-500 ease-spring"
        style={{ width: width * fit, height: height * fit }}
      />
    </span>
  );
}

function CountStepper({
  count,
  max,
  onChange,
  className
}: {
  count: number;
  max: number;
  onChange: (count: number) => void;
  className?: string;
}) {
  const step =
    'flex size-8 items-center justify-center rounded-lg text-[#8a8b8c] transition-[color,scale] duration-200 ease-spring hover:text-white active:scale-85 disabled:opacity-40 disabled:hover:text-[#8a8b8c]';
  return (
    <div role="group" aria-label="Outputs" className={cn(chipClass, 'gap-0 px-1 hover:bg-chip active:scale-100', className)}>
      <button type="button" aria-label="Fewer outputs" disabled={count <= 1} onClick={() => onChange(count - 1)} className={step}>
        <MinusIcon />
      </button>
      <span className="flex min-w-12 justify-center tabular-nums">
        <RollingValue value={count} />
        <span className="text-[#8a8b8c]">/{max}</span>
      </span>
      <button type="button" aria-label="More outputs" disabled={count >= max} onClick={() => onChange(count + 1)} className={step}>
        <PlusIcon />
      </button>
    </div>
  );
}

function Thumbnail({ asset }: { asset: Asset }) {
  const className = 'size-9 max-w-none shrink-0 overflow-hidden rounded-lg bg-muted object-cover';
  // Local video files have no poster yet, so show their first frame
  if (asset.media_type === 'video' && asset.thumbnail_url.startsWith('blob:')) {
    return <video src={asset.url} muted preload="metadata" className={className} />;
  }
  return <Image src={asset.thumbnail_url} alt="" width={36} height={36} className={className} />;
}

function LibraryPicker({ assets, disabled, onPick }: { assets: Asset[]; disabled: boolean; onPick: (asset: Asset) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger aria-label="Add from library" disabled={disabled} className={cn(chipClass, 'w-[33px] justify-center px-0')}>
        <FocusIcon />
      </PopoverTrigger>
      <PopoverContent side="top" align="start" sideOffset={8} className={cn(menuClass, 'w-72 p-3')}>
        <p className="text-sm font-semibold">Library</p>
        <ul className="grid grid-cols-4 gap-1.5">
          {assets.map((asset, index) => (
            <li key={asset.id} style={menuItemDelay(index)} className={menuItemClass}>
              <button
                type="button"
                aria-label={`Attach ${asset.media_type} ${asset.id}`}
                onClick={() => {
                  onPick(asset);
                  setOpen(false);
                }}
                className="relative block aspect-square w-full overflow-hidden rounded-lg bg-muted ring-white/40 transition-[scale] duration-200 ease-spring hover:ring-2 active:scale-90"
              >
                <Image src={asset.thumbnail_url} alt="" fill sizes="64px" className="object-cover" />
                {asset.media_type === 'video' && <VideoIcon className="absolute top-1 left-1 size-3.5 text-white drop-shadow" />}
              </button>
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
