'use client';

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { AnimatePresence, m } from 'motion/react';
import {
  ArrowLeftIcon,
  CheckIcon,
  ClockIcon,
  CopyIcon,
  CpuIcon,
  ImageIcon,
  LoaderCircleIcon,
  PlayIcon,
  PlusIcon,
  PowerIcon,
  TicketIcon,
  Trash2Icon,
  TriangleAlertIcon,
  UsersIcon,
  XIcon
} from 'lucide-react';
import useSWR from 'swr';
import useSWRInfinite from 'swr/infinite';
import { BrandMark } from '@/components/brand-mark';
import { CreditAmount } from '@/components/credit-glyph';
import { Sheet, SheetContent, SheetDescription, SheetTitle } from '@/components/ui/sheet';
import { api, messageOf, paths, request } from '@/lib/api';
import { useMe } from '@/lib/data';
import { shake } from '@/lib/motion';
import { cn } from '@/lib/utils';
import type { AdminGeneration, AdminGpu, AdminUser, GpuSession, Invite } from '@/lib/types';

const tabs = [
  { id: 'gpu', label: 'GPU', icon: CpuIcon },
  { id: 'generations', label: 'Generations', icon: ImageIcon },
  { id: 'people', label: 'People', icon: UsersIcon },
  { id: 'codes', label: 'Codes', icon: TicketIcon },
  { id: 'words', label: 'Words', icon: TriangleAlertIcon }
] as const;
type Tab = (typeof tabs)[number]['id'];

const field =
  'h-11 min-w-0 rounded-xl bg-white/[0.06] px-3.5 text-base outline-none placeholder:text-[#7c7d7f] focus-visible:ring-2 focus-visible:ring-white/20 aria-invalid:ring-2 aria-invalid:ring-[#e8a33d]/60 disabled:opacity-60';
const primary =
  'flex h-11 shrink-0 items-center justify-center gap-1.5 rounded-xl bg-brand px-4 text-sm font-bold text-white transition-[scale,opacity] duration-200 ease-spring active:scale-95 disabled:opacity-40';
const quiet =
  'flex h-9 shrink-0 items-center gap-1.5 rounded-[10px] bg-chip px-3 text-sm font-semibold text-white transition-[background-color,scale] duration-200 ease-spring hover:bg-[#3b3c3e] active:scale-95 disabled:opacity-40';

/** The rented GPU, everyone's generations to see and delete, people and their credits, invite codes and banned
 * words. */
export function Admin() {
  const { data: me, isLoading } = useMe();
  const [tab, setTab] = useState<Tab>('gpu');

  if (isLoading) return null;
  if (!me?.is_admin) {
    return (
      <main className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center gap-3 px-4">
        <h1 className="font-display text-2xl font-bold uppercase font-stretch-[86%]">For admins only</h1>
        <p className="text-[#a0a1a3]">This page is for the people who run unnoodle.</p>
        <Link href="/generate" className="text-white underline underline-offset-4">
          Back to the app
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-5xl flex-col px-4 pt-3 pb-[max(1.5rem,env(safe-area-inset-bottom))] lg:px-8 lg:pt-6">
      <header className="flex items-center gap-3">
        <Link
          href="/generate"
          aria-label="Back to the app"
          className="flex size-10 items-center justify-center rounded-xl bg-panel text-[#a0a1a3] transition-colors hover:text-white"
        >
          <ArrowLeftIcon className="size-5" />
        </Link>
        <BrandMark />
        <h1 className="font-display text-2xl font-bold tracking-[-0.01em] uppercase font-stretch-[86%]">Admin</h1>
      </header>

      <nav aria-label="Admin sections" className="sticky top-0 z-10 -mx-4 mt-4 bg-background/90 px-4 py-2 backdrop-blur lg:mx-0 lg:px-0">
        <div role="tablist" className="flex gap-1 rounded-[14px] bg-panel p-1">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              onClick={() => setTab(id)}
              className="relative flex h-10 flex-1 items-center justify-center gap-1.5 rounded-[10px] text-sm font-semibold text-[#8a8b8c] transition-colors aria-selected:text-white"
            >
              {tab === id && <m.span layoutId="admin-tab" className="absolute inset-0 rounded-[10px] bg-chip" />}
              <Icon className="relative size-4 max-sm:hidden" />
              <span className="relative">{label}</span>
            </button>
          ))}
        </div>
      </nav>

      <AnimatePresence mode="wait" initial={false}>
        <m.section
          key={tab}
          role="tabpanel"
          aria-label={tabs.find(t => t.id === tab)?.label}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4, transition: { duration: 0.12 } }}
          className="mt-3 flex flex-col"
        >
          {tab === 'gpu' && <GpuPanel />}
          {tab === 'generations' && <Generations />}
          {tab === 'people' && <People />}
          {tab === 'codes' && <Codes />}
          {tab === 'words' && <Words />}
        </m.section>
      </AnimatePresence>
    </main>
  );
}

// What each pipeline makes, for the download a GPU is on
const makes: Record<string, string> = { 'krea2-turbo': 'pictures', 'flux2-klein-edit': 'edits', 'minimax-h3': 'videos' };

function phaseWords(phase: string | null): string {
  if (phase === 'waiting-for-gpu') return 'Waiting for a free GPU';
  if (phase === 'launching') return 'Renting a GPU';
  if (phase === 'setup') return 'Setting it up';
  if (phase?.startsWith('models:')) return `Getting ${makes[phase.slice(7)] ?? 'models'} ready`;
  return 'Starting';
}

/** "5090" from "NVIDIA GeForce RTX 5090" */
const shortGpu = (type: string | null) => type?.replace(/^NVIDIA (GeForce )?(RTX )?/, '') ?? 'GPU';

function duration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ${String(s % 60).padStart(2, '0')}s`;
  return `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, '0')}m`;
}

const dollars = (n: number | null | undefined) => (n == null ? '–' : `$${n.toFixed(2)}`);

/** Seconds since the page last heard from the API, so clocks move between checks. */
function useSince(stamp: unknown) {
  const [since, setSince] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const timer = setInterval(() => setSince((Date.now() - started) / 1000), 1000);
    return () => {
      clearInterval(timer);
      setSince(0);
    };
  }, [stamp]);
  return since;
}

/** The rented GPU: what it's doing, what it costs, today's GPU time, a way to start or stop it, and past sessions. */
function GpuPanel() {
  const { data, mutate } = useSWR(paths.admin.gpu, path => request<AdminGpu>(path), {
    // Often while one is up or on its way, so phases and the idle clock stay current
    refreshInterval: gpu => (gpu && gpu.gpu.state !== 'asleep' && gpu.gpu.state !== 'off' ? 3000 : 15000)
  });
  const since = useSince(data);
  const [stopping, setStopping] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  if (!data) return null;
  if (!data.enabled) return <Empty>Renting GPUs is off on this server: the renderer is run by hand.</Empty>;

  const live = data.sessions.find(s => s.status !== 'stopped' && s.status !== 'failed') ?? null;
  const state = data.gpu.state;
  const title =
    state === 'ready' ? 'Ready' : state === 'starting' ? phaseWords(data.gpu.phase) : state === 'resting' ? 'Resting' : 'Asleep';
  const billed = live ? live.billed_s + (live.launched_at ? since : 0) : 0;

  async function start() {
    setBusy(true);
    setProblem(null);
    try {
      await mutate(api.startGpu(), { revalidate: false });
    } catch (error) {
      setProblem(messageOf(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-[22px] bg-panel p-4">
        <div className="flex items-center gap-3">
          <StateLight state={state} />
          <div className="flex min-w-0 flex-1 flex-col">
            <p className="font-display text-xl font-bold uppercase font-stretch-[86%]">{title}</p>
            <p className="text-sm text-[#a0a1a3]">
              {live
                ? `${shortGpu(live.gpu_type)} · ${live.cost_per_hour != null ? `$${live.cost_per_hour.toFixed(2)}/h` : 'renting'}`
                : state === 'resting'
                  ? "Today's GPU time is used up. Generating is off until tomorrow."
                  : 'Starts by itself when someone generates.'}
            </p>
          </div>
          {live ? (
            <button
              type="button"
              onClick={() => setStopping(true)}
              className="flex h-10 shrink-0 items-center gap-1.5 rounded-xl bg-[#4a1a22] px-3.5 text-sm font-bold text-[#ff9aa6] transition-[scale] duration-200 ease-spring active:scale-95"
            >
              <PowerIcon className="size-4" /> Stop
            </button>
          ) : (
            state === 'asleep' && (
              <button type="button" onClick={() => void start()} disabled={busy} className={cn(primary, 'h-10')}>
                <PowerIcon className="size-4" /> {busy ? 'Starting…' : 'Start'}
              </button>
            )
          )}
        </div>

        {live && (
          <>
            <dl className="mt-4 grid grid-cols-3 gap-2">
              <Stat label="Up for" value={duration(billed)} />
              <Stat label="Cost so far" value={dollars(live.cost_per_hour != null ? (billed / 3600) * live.cost_per_hour : null)} />
              <Stat
                label="Idle stop in"
                value={data.idle_left_s == null ? 'Busy' : duration(data.idle_left_s - since)}
                warn={data.idle_left_s != null && data.idle_left_s - since < 60}
              />
            </dl>
            <ul aria-label="Ready for" className="mt-3 flex flex-wrap gap-1.5">
              {Object.entries(makes).map(([pipeline, words]) => (
                <li
                  key={pipeline}
                  className={cn(
                    'rounded-full px-2.5 py-1 text-xs font-semibold',
                    pipeline in live.ready ? 'bg-brand/15 text-brand' : 'bg-white/[0.06] text-[#828282]'
                  )}
                >
                  {pipeline in live.ready ? '✓ ' : ''}
                  {words[0].toUpperCase() + words.slice(1)}
                </li>
              ))}
            </ul>
          </>
        )}
        {problem && (
          <p role="alert" className="mt-3 text-sm text-[#e8a33d]">
            {problem}
          </p>
        )}
      </div>

      <Usage used={data.used_today_s + (live?.launched_at ? since : 0)} limit={data.daily_limit_s} />

      {data.sessions.length > 0 && (
        <section aria-labelledby="gpu-sessions" className="flex flex-col gap-1.5">
          <h2 id="gpu-sessions" className="mt-2 px-1 text-sm text-[#828282]">
            Recent sessions
          </h2>
          <ul className="flex flex-col gap-1.5">
            {data.sessions.map(session => (
              <SessionRow key={session.id} session={session} />
            ))}
          </ul>
        </section>
      )}

      <StopSheet
        open={stopping}
        onOpenChange={setStopping}
        onStopped={next => {
          setStopping(false);
          void mutate(next, { revalidate: false });
        }}
      />
    </div>
  );
}

function StateLight({ state }: { state: string }) {
  const color =
    state === 'ready' ? 'bg-[#4ade80]' : state === 'starting' ? 'bg-brand' : state === 'resting' ? 'bg-[#e8a33d]' : 'bg-[#5c5d60]';
  return (
    <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-panel-raised">
      <span className="relative flex size-3">
        {(state === 'starting' || state === 'ready') && (
          <span className={cn('absolute inset-0 animate-ping rounded-full opacity-60 motion-reduce:animate-none', color)} />
        )}
        <span className={cn('relative size-3 rounded-full', color)} />
      </span>
    </span>
  );
}

function Stat({ label, value, warn = false }: { label: string; value: string; warn?: boolean }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-2xl bg-panel-raised px-3 py-2.5">
      <dt className="text-xs text-[#828282]">{label}</dt>
      <dd className={cn('text-base font-bold tabular-nums', warn && 'text-[#e8a33d]')}>{value}</dd>
    </div>
  );
}

function Usage({ used, limit }: { used: number; limit: number }) {
  const share = Math.min(1, used / Math.max(limit, 1));
  return (
    <div className="rounded-[22px] bg-panel p-4">
      <div className="flex items-end justify-between gap-3">
        <span className="text-sm text-[#a0a1a3]">GPU time today</span>
        <span className="text-sm font-semibold tabular-nums">
          {duration(used)} <span className="font-normal text-[#828282]">of {duration(limit)}</span>
        </span>
      </div>
      <div
        className="mt-2.5 h-2 overflow-hidden rounded-full bg-white/[0.07]"
        role="meter"
        aria-label="GPU time used today"
        aria-valuemin={0}
        aria-valuemax={limit}
        aria-valuenow={Math.min(used, limit)}
      >
        <div
          className={cn('h-full rounded-full transition-[width] duration-700 ease-out', share > 0.8 ? 'bg-[#e8a33d]' : 'bg-brand')}
          style={{ width: `${share * 100}%` }}
        />
      </div>
    </div>
  );
}

function SessionRow({ session }: { session: GpuSession }) {
  const when = new Date(session.created_at).toLocaleString('en', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' });
  const ended = session.status === 'stopped' || session.status === 'failed';
  return (
    <li className="flex items-center gap-3 rounded-2xl bg-panel px-3.5 py-3">
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="truncate text-sm font-semibold">
          {when} · {shortGpu(session.gpu_type)}
        </span>
        <span className={cn('truncate text-xs', session.status === 'failed' ? 'text-[#ff9aa6]' : 'text-[#828282]')}>
          {ended ? (session.stop_reason ?? session.status) : 'Up now'}
          {session.requested_by !== 'queue' ? ` · started by ${session.requested_by}` : ''}
        </span>
      </div>
      <div className="flex shrink-0 flex-col items-end gap-0.5 text-sm tabular-nums">
        <span className="font-semibold">{dollars(session.cost)}</span>
        <span className="text-xs text-[#828282]">{duration(session.billed_s)}</span>
      </div>
    </li>
  );
}

function StopSheet({
  open,
  onOpenChange,
  onStopped
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onStopped: (gpu: AdminGpu) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function stop() {
    setBusy(true);
    setProblem(null);
    try {
      onStopped(await api.stopGpu());
    } catch (error) {
      setProblem(messageOf(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="bottom"
        className="mx-auto max-h-[94dvh] max-w-md gap-0 overflow-y-auto rounded-t-[28px] border-0 bg-panel px-5 pt-6 pb-[max(1.25rem,env(safe-area-inset-bottom))]"
      >
        <SheetTitle className="font-display text-xl font-bold uppercase font-stretch-[86%]">Stop the GPU?</SheetTitle>
        <SheetDescription className="mt-1 text-sm text-[#a0a1a3]">
          {"It's handed back now. Anything waiting for it or running on it fails, and those people get their credits back."}
        </SheetDescription>
        {problem && (
          <p role="alert" className="mt-3 text-sm text-[#e8a33d]">
            {problem}
          </p>
        )}
        <div className="mt-5 flex gap-2">
          <button type="button" onClick={() => onOpenChange(false)} className={cn(quiet, 'h-12 flex-1 justify-center rounded-[14px]')}>
            Keep it
          </button>
          <button
            type="button"
            onClick={() => void stop()}
            disabled={busy}
            className="flex h-12 flex-1 items-center justify-center gap-2 rounded-[14px] bg-[#4a1a22] text-sm font-bold text-[#ff9aa6] transition-[scale,opacity] duration-200 ease-spring active:scale-95 disabled:opacity-60"
          >
            <PowerIcon className="size-4" />
            {busy ? 'Stopping…' : 'Stop'}
          </button>
        </div>
      </SheetContent>
    </Sheet>
  );
}

const PAGE = 30;

function Generations() {
  const { data, size, setSize, mutate, isValidating } = useSWRInfinite<AdminGeneration[]>(
    (index, previous: AdminGeneration[] | null) => {
      if (previous && previous.length < PAGE) return null;
      const before = previous?.at(-1)?.id;
      return `${paths.admin.generations}?limit=${PAGE}${before ? `&before=${encodeURIComponent(before)}` : ''}`;
    },
    path => request<AdminGeneration[]>(path)
  );
  const [deleting, setDeleting] = useState<AdminGeneration | null>(null);
  const [open, setOpen] = useState(false);
  const generations = data?.flat() ?? [];
  const more = data !== undefined && (data.at(-1)?.length ?? 0) === PAGE;

  if (data && generations.length === 0) return <Empty>Nothing has been generated yet.</Empty>;

  return (
    <>
      <ul aria-label="Everyone's generations" className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 lg:gap-3">
        {generations.map(generation => (
          <li key={generation.id} className="[--rise-blur:4px] [--rise-distance:10px] motion-safe:animate-rise">
            <button
              type="button"
              onClick={() => {
                setDeleting(generation);
                setOpen(true);
              }}
              aria-label={`${generation.prompt}, by ${generation.owner_email}`}
              className="group flex w-full flex-col overflow-hidden rounded-2xl bg-panel text-left transition-[scale] duration-200 ease-spring active:scale-[0.98]"
            >
              <Cover generation={generation} />
              <span className="flex min-w-0 flex-col gap-0.5 p-2.5">
                <span className="line-clamp-2 text-sm leading-snug">{generation.prompt}</span>
                <span className="truncate text-xs text-[#828282]">{generation.owner_email}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
      {more && (
        <button type="button" onClick={() => void setSize(size + 1)} disabled={isValidating} className={cn(quiet, 'mx-auto mt-4')}>
          {isValidating ? 'Loading…' : 'Show older'}
        </button>
      )}
      <DeleteSheet
        generation={deleting}
        open={open}
        onOpenChange={setOpen}
        onDeleted={id => {
          setOpen(false);
          void mutate(pages => pages?.map(page => page.filter(g => g.id !== id)), { revalidate: false });
        }}
      />
    </>
  );
}

function Cover({ generation, className }: { generation: AdminGeneration; className?: string }) {
  const cover = generation.outputs[0];
  return (
    <span className={cn('relative block aspect-square w-full overflow-hidden bg-panel-raised', className)}>
      {cover ? (
        <>
          <Image
            unoptimized
            src={cover.thumbnail_url}
            alt=""
            fill
            sizes="(min-width: 1024px) 25vw, (min-width: 640px) 33vw, 50vw"
            className="object-cover"
          />
          {cover.media_type === 'video' && (
            <PlayIcon className="absolute right-2 bottom-2 size-5 fill-white text-white drop-shadow" aria-hidden />
          )}
        </>
      ) : (
        <span className="absolute inset-0 flex flex-col items-center justify-center gap-1.5 text-xs text-[#828282]">
          {generation.status === 'failed' ? (
            <TriangleAlertIcon className="size-5 text-[#e8a33d]" />
          ) : generation.status === 'running' ? (
            <LoaderCircleIcon className="size-5 animate-spin" />
          ) : (
            <ClockIcon className="size-5" />
          )}
          {generation.status === 'failed' ? 'Failed' : generation.status === 'running' ? 'Running' : 'Waiting'}
        </span>
      )}
    </span>
  );
}

function DeleteSheet({
  generation,
  open,
  onOpenChange,
  onDeleted
}: {
  generation: AdminGeneration | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDeleted: (id: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function remove() {
    if (!generation || busy) return;
    setBusy(true);
    setProblem(null);
    try {
      await api.deleteGeneration(generation.id);
      onDeleted(generation.id);
    } catch (error) {
      setProblem(messageOf(error));
    } finally {
      setBusy(false);
    }
  }

  const uploads = generation?.inputs.filter(i => i.asset.source === 'upload').length ?? 0;
  return (
    <Sheet
      open={open}
      onOpenChange={next => {
        onOpenChange(next);
        if (!next) setProblem(null);
      }}
    >
      <SheetContent
        side="bottom"
        className="mx-auto max-h-[94dvh] max-w-md gap-0 overflow-y-auto rounded-t-[28px] border-0 bg-panel px-5 pt-6 pb-[max(1.25rem,env(safe-area-inset-bottom))]"
      >
        <SheetTitle className="font-display text-xl font-bold uppercase font-stretch-[86%]">Delete this generation?</SheetTitle>
        <SheetDescription className="mt-1 text-sm text-[#a0a1a3]">
          It goes for good
          {generation?.outputs.length ? `, with its ${generation.outputs[0].media_type === 'video' ? 'video' : 'picture'}` : ''}
          {uploads > 0 ? ' and the uploads made for it that nothing else uses' : ''}. Credits it took stay taken.
        </SheetDescription>
        {generation && (
          <div className="mt-5 flex gap-3 rounded-2xl bg-panel-raised p-2.5">
            <Cover generation={generation} className="size-20 shrink-0 rounded-xl" />
            <div className="flex min-w-0 flex-col gap-1 py-0.5">
              <p className="line-clamp-3 text-sm">{generation.prompt}</p>
              <p className="truncate text-xs text-[#828282]">
                {generation.owner_email} · {new Date(generation.created_at).toLocaleDateString('en', { day: 'numeric', month: 'short' })}
              </p>
            </div>
          </div>
        )}
        {problem && (
          <p role="alert" className="mt-3 text-sm text-[#e8a33d]">
            {problem}
          </p>
        )}
        <div className="mt-5 flex gap-2">
          <button type="button" onClick={() => onOpenChange(false)} className={cn(quiet, 'h-12 flex-1 justify-center rounded-[14px]')}>
            Keep it
          </button>
          <button
            type="button"
            onClick={() => void remove()}
            disabled={busy}
            className="flex h-12 flex-1 items-center justify-center gap-2 rounded-[14px] bg-[#4a1a22] text-sm font-bold text-[#ff9aa6] transition-[scale,opacity] duration-200 ease-spring active:scale-95 disabled:opacity-60"
          >
            <Trash2Icon className="size-4" />
            {busy ? 'Deleting…' : 'Delete'}
          </button>
        </div>
      </SheetContent>
    </Sheet>
  );
}

function People() {
  const { data: users, mutate } = useSWR(paths.admin.users, path => request<AdminUser[]>(path));
  const [granting, setGranting] = useState<AdminUser | null>(null);
  const [open, setOpen] = useState(false);

  if (users?.length === 0) return <Empty>No one has signed up yet.</Empty>;
  return (
    <>
      <ul aria-label="People" className="flex flex-col gap-1.5">
        {users?.map(user => (
          <li
            key={user.id}
            className="flex items-center gap-3 rounded-2xl bg-panel px-3.5 py-3 [--rise-blur:0px] [--rise-distance:6px] motion-safe:animate-rise"
          >
            <div className="flex min-w-0 flex-1 flex-col gap-0.5">
              <span className="flex items-center gap-2 truncate text-sm font-semibold">
                <span className="truncate">{user.email}</span>
                {user.is_admin && (
                  <span className="shrink-0 rounded-full bg-[#4a5fd1]/30 px-2 py-0.5 text-[0.6875rem] text-[#b9c6ff]">Admin</span>
                )}
              </span>
              <span className="text-xs text-[#828282]">
                <CreditAmount value={user.balance} className="text-[#c8c9cb]" /> · {user.generation_count}{' '}
                {user.generation_count === 1 ? 'generation' : 'generations'}
              </span>
            </div>
            <button
              type="button"
              onClick={() => {
                setGranting(user);
                setOpen(true);
              }}
              className={quiet}
              aria-label={`Give credits to ${user.email}`}
            >
              <PlusIcon className="size-4" />
              Credits
            </button>
          </li>
        ))}
      </ul>
      <GrantSheet
        user={granting}
        open={open}
        onOpenChange={setOpen}
        onGranted={updated => {
          setOpen(false);
          void mutate(current => current?.map(u => (u.id === updated.id ? updated : u)), { revalidate: false });
        }}
      />
    </>
  );
}

const amounts = [10, 50, 100, 500];

function GrantSheet({
  user,
  open,
  onOpenChange,
  onGranted
}: {
  user: AdminUser | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onGranted: (user: AdminUser) => void;
}) {
  const [amount, setAmount] = useState('50');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const value = Number.parseInt(amount, 10);
  const valid = Number.isInteger(value) && value !== 0;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!user || busy || !valid) return;
    setBusy(true);
    setProblem(null);
    try {
      onGranted(await api.grant(user.id, value, note.trim() || null));
      setNote('');
    } catch (error) {
      setProblem(messageOf(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="bottom"
        className="mx-auto max-h-[94dvh] max-w-md gap-0 overflow-y-auto rounded-t-[28px] border-0 bg-panel px-5 pt-6 pb-[max(1.25rem,env(safe-area-inset-bottom))]"
      >
        <SheetTitle className="font-display text-xl font-bold uppercase font-stretch-[86%]">Give credits</SheetTitle>
        <SheetDescription className="mt-1 truncate text-sm text-[#a0a1a3]">
          {user?.email} has <CreditAmount value={user?.balance ?? 0} className="text-white" />
        </SheetDescription>
        <form onSubmit={submit} className="mt-5 flex flex-col gap-3">
          <div className="grid grid-cols-4 gap-2" role="group" aria-label="Amount">
            {amounts.map(n => (
              <button
                key={n}
                type="button"
                aria-pressed={value === n}
                onClick={() => setAmount(String(n))}
                className="h-11 rounded-xl bg-panel-raised text-sm font-semibold text-[#c8c9cb] transition-[background-color,color,scale] duration-200 ease-spring active:scale-95 aria-pressed:bg-brand aria-pressed:text-white"
              >
                +{n}
              </button>
            ))}
          </div>
          <label className="flex flex-col gap-1.5 text-sm text-[#a0a1a3]">
            Or any amount (negative takes back)
            <input
              value={amount}
              onChange={event => setAmount(event.target.value)}
              inputMode="numeric"
              aria-invalid={!valid}
              className={field}
            />
          </label>
          <label className="flex flex-col gap-1.5 text-sm text-[#a0a1a3]">
            Note, for the record
            <input value={note} onChange={event => setNote(event.target.value)} maxLength={200} placeholder="Optional" className={field} />
          </label>
          {problem && (
            <p role="alert" className="text-sm text-[#e8a33d]">
              {problem}
            </p>
          )}
          <button type="submit" disabled={busy || !valid} className={cn(primary, 'mt-1 h-12 rounded-[14px]')}>
            {busy ? (
              'Giving…'
            ) : valid ? (
              <>
                Give <CreditAmount value={value} />
              </>
            ) : (
              'Give credits'
            )}
          </button>
        </form>
      </SheetContent>
    </Sheet>
  );
}

function Codes() {
  const { data: invites, mutate } = useSWR(paths.admin.invites, path => request<Invite[]>(path));
  const [code, setCode] = useState('');
  const [credits, setCredits] = useState('50');
  const [uses, setUses] = useState('10');
  const [days, setDays] = useState('');
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const form = useRef<HTMLFormElement>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setProblem(null);
    try {
      const made = await api.createInvite({
        code: code.trim(),
        credits: Number(credits),
        max_uses: Number(uses),
        days: days.trim() === '' ? null : Number(days)
      });
      void mutate(current => [made, ...(current ?? [])], { revalidate: false });
      setCode('');
    } catch (error) {
      setProblem(messageOf(error));
      shake(form.current);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <form ref={form} onSubmit={submit} aria-label="New invite code" className="flex flex-col gap-2 rounded-2xl bg-panel p-3">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-[2fr_1fr_1fr_1fr]">
          <Labelled label="Code" className="col-span-2 sm:col-span-1">
            <input
              value={code}
              onChange={event => setCode(event.target.value)}
              aria-label="Code"
              placeholder="WELCOME"
              autoCapitalize="characters"
              autoComplete="off"
              spellCheck={false}
              required
              minLength={3}
              maxLength={32}
              pattern="[A-Za-z0-9\-]+"
              title="Letters, numbers and dashes"
              className={cn(field, 'w-full tracking-[0.08em] uppercase')}
            />
          </Labelled>
          <Labelled label="Credits each">
            <input
              value={credits}
              onChange={event => setCredits(event.target.value)}
              inputMode="numeric"
              required
              className={cn(field, 'w-full')}
            />
          </Labelled>
          <Labelled label="Uses">
            <input
              value={uses}
              onChange={event => setUses(event.target.value)}
              inputMode="numeric"
              required
              className={cn(field, 'w-full')}
            />
          </Labelled>
          <Labelled label="Days" className="col-span-2 sm:col-span-1">
            <input
              value={days}
              onChange={event => setDays(event.target.value)}
              inputMode="numeric"
              placeholder="No end"
              className={cn(field, 'w-full')}
            />
          </Labelled>
        </div>
        {problem && (
          <p role="alert" className="px-1 text-sm text-[#e8a33d]">
            {problem}
          </p>
        )}
        <button type="submit" disabled={busy} className={primary}>
          <PlusIcon className="size-4" />
          {busy ? 'Making…' : 'Make code'}
        </button>
      </form>

      {invites?.length === 0 && <Empty>No invite codes yet.</Empty>}
      <ul aria-label="Invite codes" className="mt-3 grid gap-2 sm:grid-cols-2">
        <AnimatePresence initial={false}>
          {invites?.map(invite => (
            <m.li key={invite.code} layout initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }}>
              <InviteCard invite={invite} />
            </m.li>
          ))}
        </AnimatePresence>
      </ul>
    </>
  );
}

function Labelled({ label, className, children }: { label: string; className?: string; children: ReactNode }) {
  return (
    <label className={cn('relative flex flex-col', className)}>
      <span className="pointer-events-none absolute top-1 left-3.5 text-[0.625rem] font-semibold tracking-wide text-[#7c7d7f] uppercase">
        {label}
      </span>
      <span className="[&_input]:pt-3">{children}</span>
    </label>
  );
}

function InviteCard({ invite }: { invite: Invite }) {
  const [copied, setCopied] = useState(false);
  const share = Math.min(1, invite.uses / invite.max_uses);
  const expired = invite.expires_at !== null && new Date(invite.expires_at) <= new Date();
  const ended = expired || invite.uses >= invite.max_uses;

  return (
    <div className={cn('flex flex-col gap-2.5 rounded-2xl bg-panel p-3.5', ended && 'opacity-60')}>
      <div className="flex items-center gap-2">
        <span className="font-mono text-base font-semibold tracking-[0.08em]">{invite.code}</span>
        <button
          type="button"
          aria-label={`Copy ${invite.code}`}
          onClick={() => {
            void navigator.clipboard?.writeText(invite.code).then(() => {
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            });
          }}
          className="flex size-7 items-center justify-center rounded-lg text-[#8a8b8c] transition-colors hover:text-white"
        >
          {copied ? <CheckIcon className="size-4 text-brand" /> : <CopyIcon className="size-4" />}
        </button>
        <CreditAmount value={invite.credits} className="ml-auto text-sm font-semibold text-brand" />
      </div>
      <div
        className="h-1.5 overflow-hidden rounded-full bg-white/[0.07]"
        role="meter"
        aria-label="Used"
        aria-valuemin={0}
        aria-valuemax={invite.max_uses}
        aria-valuenow={invite.uses}
      >
        <m.div className="h-full origin-left rounded-full bg-brand" initial={{ scaleX: 0 }} animate={{ scaleX: share }} />
      </div>
      <p className="text-xs text-[#828282]">
        {invite.uses} of {invite.max_uses} used ·{' '}
        {invite.expires_at === null
          ? 'no end date'
          : `${expired ? 'ended' : 'ends'} ${new Date(invite.expires_at).toLocaleDateString('en', { day: 'numeric', month: 'short' })}`}
      </p>
    </div>
  );
}

function Words() {
  const { data: words, mutate } = useSWR(paths.admin.words, path => request<string[]>(path));
  const [word, setWord] = useState('');
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function add(event: FormEvent) {
    event.preventDefault();
    if (busy || word.trim() === '') return;
    setBusy(true);
    setProblem(null);
    try {
      await mutate(api.addBannedWord(word.trim()), { revalidate: false });
      setWord('');
    } catch (error) {
      setProblem(messageOf(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <p className="px-1 text-sm text-[#a0a1a3]">
        Prompts with these are refused, also with capitals, accents, numbers for letters, or as plurals.
      </p>
      <form onSubmit={add} aria-label="Ban a word" className="mt-3 flex gap-2">
        <input
          value={word}
          onChange={event => setWord(event.target.value)}
          aria-label="Word or phrase"
          placeholder="Word or phrase"
          maxLength={64}
          autoComplete="off"
          className={cn(field, 'flex-1')}
        />
        <button type="submit" disabled={busy || word.trim() === ''} className={primary}>
          <PlusIcon className="size-4" />
          Ban
        </button>
      </form>
      {problem && (
        <p role="alert" className="mt-2 px-1 text-sm text-[#e8a33d]">
          {problem}
        </p>
      )}
      {words?.length === 0 && <Empty>No banned words. Every prompt goes through.</Empty>}
      <ul aria-label="Banned words" className="mt-4 flex flex-wrap gap-2">
        <AnimatePresence initial={false}>
          {words?.map(w => (
            <m.li
              key={w}
              layout
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8, transition: { duration: 0.15 } }}
              className="flex h-9 items-center gap-1 rounded-full bg-panel pr-1 pl-3.5 text-sm"
            >
              {w}
              <button
                type="button"
                aria-label={`Allow ${w}`}
                onClick={() => void mutate(api.removeBannedWord(w), { optimisticData: words.filter(x => x !== w), revalidate: false })}
                className="flex size-7 items-center justify-center rounded-full text-[#8a8b8c] transition-colors hover:bg-white/10 hover:text-white"
              >
                <XIcon className="size-3.5" />
              </button>
            </m.li>
          ))}
        </AnimatePresence>
      </ul>
    </>
  );
}

function Empty({ children }: { children: ReactNode }) {
  return <p className="mt-10 text-center text-sm text-[#828282]">{children}</p>;
}
