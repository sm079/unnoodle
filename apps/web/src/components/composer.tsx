'use client';

import { useRef, useState, type ChangeEvent, type ComponentType, type FormEvent, type ReactNode } from 'react';
import Image from 'next/image';
import {
  ApertureIcon,
  AtSignIcon,
  CameraIcon,
  ChevronRightIcon,
  ClockIcon,
  FilmIcon,
  FocusIcon,
  GemIcon,
  ImageIcon,
  LampIcon,
  MinusIcon,
  PaletteIcon,
  PlusIcon,
  RectangleHorizontalIcon,
  RectangleVerticalIcon,
  SlidersHorizontalIcon,
  SparkleIcon,
  SquareIcon,
  UserRoundIcon,
  VideoIcon,
  Volume2Icon,
  VolumeXIcon,
  XIcon
} from 'lucide-react';
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
import { outputType, roleFor, roleLabels } from '@/lib/capabilities';
import { cn } from '@/lib/utils';
import type {
  AspectRatio,
  Asset,
  Capability,
  ComposerDraft,
  GenerationInput,
  GenerationParams,
  MediaType,
  Workflow,
  WorkflowControl,
  WorkflowOptions
} from '@/lib/types';

interface ComposerProps {
  drafts: Record<MediaType, ComposerDraft>;
  workflows: Workflow[];
  /** Earlier uploads that can be attached again. */
  library: Asset[];
}

interface Draft extends ComposerDraft {
  /** The chosen option of each look control, by control id. Controls left out use their first option. */
  look: Record<string, string>;
  /** Videos only. Not part of the request shape yet. */
  audio: boolean;
}

const modeLabels: Record<MediaType, string> = { image: 'Image', video: 'Video' };

const placeholders: Record<MediaType, string> = {
  image: 'Describe the image you want to create...',
  video: 'Describe the shot - use @ to bring in characters and places'
};

export function Composer({ drafts, workflows, library }: ComposerProps) {
  const [mode, setMode] = useState<MediaType>('video');
  const [state, setState] = useState<Record<MediaType, Draft>>(() => ({
    image: { ...drafts.image, look: {}, audio: false },
    video: { ...drafts.video, look: {}, audio: true }
  }));
  const promptRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const draft = state[mode];
  const modeWorkflows = workflows.filter(w => outputType(w.capability) === mode);
  const workflow = modeWorkflows.find(w => w.id === draft.workflow_id) ?? modeWorkflows[0];
  const { options } = workflow;
  const full = draft.inputs.length >= options.max_inputs;

  function update(patch: Partial<Draft>) {
    setState(current => ({ ...current, [mode]: { ...current[mode], ...patch } }));
  }

  function setParam<K extends keyof GenerationParams>(key: K, value: GenerationParams[K]) {
    update({ params: { ...draft.params, [key]: value } });
  }

  function chooseWorkflow(next: Workflow) {
    update({
      workflow_id: next.id,
      params: fitParams(draft.params, next.options),
      inputs: draft.inputs.map((input, index) => withRole(input, next.capability, index))
    });
  }

  function attach(assets: Asset[]) {
    const room = Math.max(0, options.max_inputs - draft.inputs.length);
    const added = assets
      .slice(0, room)
      .map((asset, i) => withRole({ role: 'reference', asset, position_s: null }, workflow.capability, draft.inputs.length + i));
    update({ inputs: [...draft.inputs, ...added] });
  }

  function detach(index: number) {
    const { asset } = draft.inputs[index];
    if (asset.url.startsWith('blob:')) URL.revokeObjectURL(asset.url);
    update({
      inputs: draft.inputs.filter((_, i) => i !== index).map((input, i) => withRole(input, workflow.capability, i))
    });
  }

  function attachFiles(event: ChangeEvent<HTMLInputElement>) {
    attach(Array.from(event.target.files ?? [], fileAsset));
    event.target.value = '';
  }

  function insertMention() {
    const field = promptRef.current;
    if (!field) return;
    const { selectionStart: start, selectionEnd: end } = field;
    update({ prompt: `${draft.prompt.slice(0, start)}@${draft.prompt.slice(end)}` });
    requestAnimationFrame(() => {
      field.focus();
      field.setSelectionRange(start + 1, start + 1);
    });
  }

  function submit(event: FormEvent) {
    // Nothing to send to until the API exists
    event.preventDefault();
    if (draft.prompt.trim() === '') promptRef.current?.focus();
  }

  const looks = options.controls.map(control => ({
    control,
    value: draft.look[control.id] ?? control.options[0],
    onChange: (value: string) => update({ look: { ...draft.look, [control.id]: value } })
  }));

  return (
    <form onSubmit={submit} aria-label="Composer" className="flex w-full flex-col gap-1.5 lg:flex-row lg:items-end">
      <div
        role="group"
        aria-label="Output type"
        className="flex gap-1 rounded-[22px] bg-panel p-1.5 lg:h-[140px] lg:w-[88px] lg:shrink-0 lg:flex-col lg:rounded-[28px]"
      >
        {(['image', 'video'] as const).map(type => {
          const Icon = type === 'image' ? ImageIcon : VideoIcon;
          return (
            <button
              key={type}
              type="button"
              aria-pressed={mode === type}
              onClick={() => setMode(type)}
              className="flex h-10 flex-1 items-center justify-center gap-2 rounded-2xl text-[13px] font-semibold text-[#8a8b8c] transition-colors hover:text-foreground aria-pressed:bg-panel-raised aria-pressed:text-foreground lg:h-auto lg:flex-col lg:gap-1.5 lg:rounded-[22px]"
            >
              <Icon className="size-4" />
              {modeLabels[type]}
            </button>
          );
        })}
      </div>

      <div className="min-w-0 flex-1 rounded-[26px] bg-panel p-[5px] lg:rounded-[30px]">
        {mode === 'video' && (
          <div className="no-scrollbar flex gap-1.5 overflow-x-auto p-[5px] pb-2.5">
            <div className={cn(cardClass, 'w-40 shrink-0')}>
              <button
                type="button"
                aria-label="Add references"
                disabled={full}
                onClick={() => fileRef.current?.click()}
                className="flex size-10 shrink-0 items-center justify-center rounded-[10px] bg-[#19191b] text-[#b5b5b5] shadow-[inset_0_1px_0_rgb(255_255_255/0.08)] ring-1 ring-white/10 transition-colors hover:text-white disabled:opacity-40"
              >
                <PlusIcon className="size-5" />
              </button>
              <CardText label="References" value={`${draft.inputs.length}/${options.max_inputs}`} />
            </div>
            {looks.map(look => (
              <LookMenu key={look.control.id} {...look}>
                <DropdownMenuTrigger className={cn(cardClass, 'min-w-40 flex-1 text-left hover:bg-[#2e2f31] lg:max-w-[200px]')}>
                  <LookArt id={look.control.id} className="size-10 rounded-[10px]" />
                  <CardText label={look.control.label} value={look.value} />
                </DropdownMenuTrigger>
              </LookMenu>
            ))}
          </div>
        )}

        <div className="flex flex-col gap-3 rounded-[22px] bg-panel-raised p-3 lg:flex-row lg:items-end lg:gap-2 lg:rounded-[24px] lg:py-3.5 lg:pr-3 lg:pl-4">
          <div className="flex min-w-0 flex-1 flex-col gap-3 lg:self-stretch">
            {draft.inputs.length > 0 && (
              <ul aria-label="Inputs" className="no-scrollbar flex gap-2 overflow-x-auto">
                {draft.inputs.map((input, index) => (
                  <li
                    key={`${input.asset.id}-${index}`}
                    title={index >= options.max_inputs ? 'Not used by this workflow' : undefined}
                    className={cn(
                      'flex shrink-0 items-center gap-2 rounded-xl bg-chip p-1 pr-1.5',
                      index >= options.max_inputs && 'opacity-40'
                    )}
                  >
                    <Thumbnail asset={input.asset} />
                    <span className="text-[13px] font-semibold">
                      {roleLabels[input.role]}
                      {input.position_s !== null && <span className="text-[#8a8b8c]"> · {input.position_s}s</span>}
                    </span>
                    <button
                      type="button"
                      aria-label={`Remove ${roleLabels[input.role].toLowerCase()}`}
                      onClick={() => detach(index)}
                      className="flex size-6 items-center justify-center rounded-md text-[#8a8b8c] hover:bg-white/10 hover:text-white"
                    >
                      <XIcon className="size-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            )}

            <Textarea
              ref={promptRef}
              value={draft.prompt}
              onChange={event => update({ prompt: event.target.value })}
              placeholder={placeholders[mode]}
              aria-label="Prompt"
              className="max-h-48 min-h-14 flex-1 resize-none rounded-none border-0 bg-transparent px-1 py-0.5 text-[17px] leading-snug placeholder:text-[#7c7d7f] focus-visible:ring-0 md:text-[17px] dark:bg-transparent"
            />

            <div className="-mx-3 no-scrollbar flex gap-[7px] overflow-x-auto px-3 lg:mx-0 lg:px-0">
              <div className={cn(chipClass, 'gap-0 px-0 hover:bg-chip')}>
                <button
                  type="button"
                  aria-label="Attach files"
                  disabled={full}
                  onClick={() => fileRef.current?.click()}
                  className="flex h-full w-[35px] items-center justify-center rounded-l-[10px] hover:bg-white/[0.06] disabled:opacity-40"
                >
                  <PlusIcon />
                </button>
                <span className="h-4 w-px bg-white/15" />
                <button
                  type="button"
                  aria-label="Mention an element"
                  onClick={insertMention}
                  className="flex h-full w-[35px] items-center justify-center rounded-r-[10px] hover:bg-white/[0.06]"
                >
                  <AtSignIcon />
                </button>
              </div>
              <LibraryPicker assets={library} disabled={full} onPick={asset => attach([asset])} />
              <WorkflowMenu workflows={modeWorkflows} value={workflow} onChange={chooseWorkflow} className={cn(chipClass, 'px-3')} />
              <OptionChip
                label="Resolution"
                icon={<GemIcon />}
                value={draft.params.resolution}
                options={options.resolutions}
                onChange={value => setParam('resolution', value)}
              />
              <OptionChip
                label="Aspect ratio"
                icon={<AspectIcon ratio={draft.params.aspect_ratio} />}
                value={draft.params.aspect_ratio}
                options={options.aspect_ratios}
                onChange={value => setParam('aspect_ratio', value as AspectRatio)}
              />
              {draft.params.duration_s !== null && (
                <OptionChip
                  label="Duration"
                  icon={<ClockIcon strokeWidth={2.5} />}
                  value={`${draft.params.duration_s}s`}
                  options={options.durations_s.map(s => `${s}s`)}
                  onChange={value => setParam('duration_s', parseInt(value))}
                />
              )}
              {options.audio && (
                <button
                  type="button"
                  aria-label="Sound"
                  aria-pressed={draft.audio}
                  onClick={() => update({ audio: !draft.audio })}
                  className={chipClass}
                >
                  {draft.audio ? <Volume2Icon /> : <VolumeXIcon />}
                  {draft.audio ? 'On' : 'Off'}
                </button>
              )}
              {mode === 'video' ? (
                <CountStepper count={draft.params.count} max={options.max_count} onChange={count => setParam('count', count)} />
              ) : (
                <Popover>
                  <PopoverTrigger aria-label="More settings" className={cn(chipClass, 'w-[35px] justify-center px-0')}>
                    <ChevronRightIcon />
                  </PopoverTrigger>
                  <PopoverContent
                    side="top"
                    align="start"
                    sideOffset={8}
                    className={cn(menuClass, 'w-auto flex-row items-center gap-3 p-2 pl-3.5')}
                  >
                    <span className="text-sm text-[#8a8b8c]">Outputs</span>
                    <CountStepper count={draft.params.count} max={options.max_count} onChange={count => setParam('count', count)} />
                  </PopoverContent>
                </Popover>
              )}
            </div>
          </div>

          {mode === 'image' && looks.length > 0 && (
            <div className="-mx-3 no-scrollbar flex gap-2 overflow-x-auto px-3 lg:mx-0 lg:px-0">
              {looks.map(look => (
                <LookMenu key={look.control.id} {...look}>
                  <DropdownMenuTrigger className="relative flex h-24 w-[150px] shrink-0 flex-col items-start justify-end rounded-[14px] bg-linear-to-b from-[#3e3e40] to-[#262628] p-3 text-left ring-1 ring-white/[0.06] transition-colors hover:from-[#474749]">
                    <LookArt id={look.control.id} className="absolute top-2.5 right-2.5 size-8 rounded-full" />
                    <span className="text-[13px] font-bold">{look.control.label}</span>
                    <span className="max-w-full truncate text-xs text-[#8a8b8c]">{look.value}</span>
                  </DropdownMenuTrigger>
                </LookMenu>
              ))}
            </div>
          )}

          <button
            type="submit"
            aria-label={`Generate, ${workflow.credits * draft.params.count} credits`}
            className="mb-[3px] flex h-14 w-full shrink-0 items-center justify-center gap-3 rounded-[14px] bg-linear-to-b from-[#d8ff17] via-[#f4ff1f] to-[#ffff17] text-[#191b04] shadow-[0_3px_0_var(--color-lime-edge),0_10px_20px_rgb(0_0_0/0.45)] transition-[translate,box-shadow,filter] hover:brightness-105 active:translate-y-[2px] active:shadow-[0_1px_0_var(--color-lime-edge),0_4px_10px_rgb(0_0_0/0.4)] lg:h-24 lg:w-40 lg:flex-col lg:gap-1"
          >
            <span className="font-display text-[15px] font-extrabold tracking-[0.02em] uppercase font-stretch-[88%]">Generate</span>
            <span className="flex items-center gap-1 text-[15px] font-medium">
              <SparkleIcon className="size-3.5 fill-current" />
              {workflow.credits * draft.params.count}
            </span>
          </button>
        </div>
      </div>

      <input ref={fileRef} type="file" accept="image/*,video/*" multiple hidden onChange={attachFiles} />
    </form>
  );
}

const chipClass =
  "flex h-[35px] shrink-0 items-center gap-1.5 rounded-[10px] bg-chip px-2.5 text-[15px] font-bold whitespace-nowrap text-white transition-colors outline-none hover:bg-[#3b3c3e] focus-visible:ring-2 focus-visible:ring-white/30 disabled:opacity-40 data-[popup-open]:bg-[#3b3c3e] [&_svg:not([class*='size-'])]:size-[18px] [&_svg]:shrink-0";
const cardClass =
  'flex h-[60px] items-center gap-2.5 rounded-[18px] bg-panel-raised px-2.5 outline-none focus-visible:ring-2 focus-visible:ring-white/30';
const menuClass =
  'rounded-2xl border border-white/[0.07] bg-[#25282c]/90 p-1.5 shadow-[0_18px_40px_rgb(0_0_0/0.55)] ring-0 backdrop-blur-xl';

function fitParams(params: GenerationParams, options: WorkflowOptions): GenerationParams {
  const pick = <T,>(value: T, allowed: T[]) => (allowed.includes(value) ? value : allowed[0]);
  return {
    ...params,
    aspect_ratio: pick(params.aspect_ratio, options.aspect_ratios),
    resolution: pick(params.resolution, options.resolutions),
    duration_s: options.durations_s.length > 0 ? pick(params.duration_s ?? options.durations_s[0], options.durations_s) : null,
    count: Math.min(params.count, options.max_count)
  };
}

function withRole(input: GenerationInput, capability: Capability, index: number): GenerationInput {
  const role = roleFor(capability, index);
  // Keyframes go a second apart until there is a timeline to place them on
  return { ...input, role, position_s: role === 'keyframe' ? index : null };
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
      <span className="truncate text-[17px] leading-tight font-bold">{value}</span>
    </span>
  );
}

const lookArt: Record<string, { icon: ComponentType<{ className?: string }>; tile: string }> = {
  character: { icon: UserRoundIcon, tile: 'from-[#9273e0] to-[#36256a] text-white' },
  lens: { icon: CameraIcon, tile: 'from-[#2f3344] to-[#08090d] text-[#9cb4ff]' },
  film_setup: { icon: FilmIcon, tile: 'from-[#ebe9e2] to-[#8d8a82] text-[#37352f]' },
  camera: { icon: ApertureIcon, tile: 'from-[#2b3b6e] to-[#090c18] text-[#8fb0ff]' },
  color_palette: { icon: PaletteIcon, tile: 'from-[#a3922c] to-[#46531a] text-[#f5eca6]' },
  lighting: { icon: LampIcon, tile: 'from-[#3f72d6] to-[#13234b] text-[#d3e2ff]' }
};

function LookArt({ id, className }: { id: string; className?: string }) {
  const art = lookArt[id] ?? { icon: SlidersHorizontalIcon, tile: 'from-[#4a4b4e] to-[#26272a] text-white' };
  return (
    <span
      className={cn(
        'flex shrink-0 items-center justify-center bg-linear-to-br shadow-[inset_0_1px_0_rgb(255_255_255/0.25),0_1px_3px_rgb(0_0_0/0.5)]',
        art.tile,
        className
      )}
    >
      <art.icon className="size-1/2" />
    </span>
  );
}

function LookMenu({
  control,
  value,
  onChange,
  children
}: {
  control: WorkflowControl;
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
}) {
  return (
    <DropdownMenu>
      {children}
      <OptionList label={control.label} value={value} options={control.options} onChange={onChange} />
    </DropdownMenu>
  );
}

function OptionChip({
  label,
  icon,
  value,
  options,
  onChange
}: {
  label: string;
  icon: ReactNode;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger aria-label={`${label}: ${value}`} className={chipClass}>
        {icon}
        {value}
      </DropdownMenuTrigger>
      <OptionList label={label} value={value} options={options} onChange={onChange} />
    </DropdownMenu>
  );
}

function OptionList({
  label,
  value,
  options,
  onChange
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <DropdownMenuContent side="top" sideOffset={8} aria-label={label} className={cn(menuClass, 'w-auto min-w-40')}>
      <DropdownMenuRadioGroup value={value} onValueChange={next => onChange(String(next))}>
        {options.map(option => (
          <DropdownMenuRadioItem
            key={option}
            value={option}
            className="h-9 rounded-[10px] px-2.5 text-sm font-medium focus:bg-white/[0.07]"
          >
            {option}
          </DropdownMenuRadioItem>
        ))}
      </DropdownMenuRadioGroup>
    </DropdownMenuContent>
  );
}

function AspectIcon({ ratio }: { ratio: AspectRatio }) {
  const [width, height] = ratio.split(':').map(Number);
  if (width === height) return <SquareIcon />;
  return width > height ? <RectangleHorizontalIcon /> : <RectangleVerticalIcon />;
}

function CountStepper({ count, max, onChange }: { count: number; max: number; onChange: (count: number) => void }) {
  const step =
    'flex size-8 items-center justify-center rounded-lg text-[#8a8b8c] hover:text-white disabled:opacity-40 disabled:hover:text-[#8a8b8c]';
  return (
    <div role="group" aria-label="Outputs" className={cn(chipClass, 'gap-0 px-1 hover:bg-chip')}>
      <button type="button" aria-label="Fewer outputs" disabled={count <= 1} onClick={() => onChange(count - 1)} className={step}>
        <MinusIcon />
      </button>
      <span className="min-w-12 text-center tabular-nums">
        {count}
        <span className="text-[#8a8b8c]">/{max}</span>
      </span>
      <button type="button" aria-label="More outputs" disabled={count >= max} onClick={() => onChange(count + 1)} className={step}>
        <PlusIcon />
      </button>
    </div>
  );
}

function Thumbnail({ asset }: { asset: Asset }) {
  const className = 'size-9 shrink-0 overflow-hidden rounded-lg bg-muted object-cover';
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
          {assets.map(asset => (
            <li key={asset.id}>
              <button
                type="button"
                aria-label={`Attach ${asset.media_type} ${asset.id}`}
                onClick={() => {
                  onPick(asset);
                  setOpen(false);
                }}
                className="relative block aspect-square w-full overflow-hidden rounded-lg bg-muted ring-white/40 hover:ring-2"
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
