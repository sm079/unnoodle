'use client';

import { useState, type ComponentType, type ReactNode } from 'react';
import { m } from 'motion/react';
import {
  ArchiveIcon,
  ChevronRightIcon,
  HeartIcon,
  HouseIcon,
  LogOutIcon,
  MenuIcon,
  PanelLeftIcon,
  PlusIcon,
  SparklesIcon,
  XIcon,
  ZapIcon
} from 'lucide-react';
import { BrandMark, NoodleGlyph } from '@/components/brand-mark';
import { NewProjectForm } from '@/components/new-project';
import { Sheet, SheetClose, SheetContent, SheetTitle, SheetTrigger } from '@/components/ui/sheet';
import { api } from '@/lib/api';
import { useCredits, useMe, usePreferences, useProjects } from '@/lib/data';
import { cn } from '@/lib/utils';
import { allProjects, folder, home, sameView, type View } from '@/lib/views';

interface NavItem {
  label: string;
  icon: ComponentType<{ className?: string }>;
  /** Gradient of the icon tile. */
  tile: string;
  /** The view it opens; left out for ones that don't exist yet. */
  view?: View;
}

const navItems: NavItem[] = [
  { label: 'Home', icon: HouseIcon, tile: 'from-[#d4d4d4] to-[#4d4d4d]', view: home },
  { label: 'My favorites', icon: HeartIcon, tile: 'from-[#ffa1cb] to-[#d23c7c]' }
];

interface AppShellProps {
  view: View;
  onView: (view: View) => void;
  children: ReactNode;
}

export function AppShell({ view, onView, children }: AppShellProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    // On phones the page itself scrolls, so the browser can tuck its toolbars away; on wide screens only the main
    // area scrolls, beside the sidebar
    <div className="flex min-h-dvh flex-col pr-[env(safe-area-inset-right)] pl-[env(safe-area-inset-left)] lg:h-dvh lg:flex-row">
      <aside
        data-collapsed={collapsed}
        aria-label="Sidebar"
        className="group/sidebar hidden w-72 shrink-0 flex-col overflow-hidden rounded-r-2xl border-r transition-[width] duration-300 ease-in-out-quart data-[collapsed=true]:w-19 motion-reduce:transition-none lg:flex"
      >
        <SidebarBody
          view={view}
          onView={onView}
          action={
            <button type="button" onClick={() => setCollapsed(!collapsed)} aria-label="Toggle sidebar" className={topButtonClass}>
              <PanelLeftIcon className="size-4.5" />
            </button>
          }
        />
      </aside>

      <header className="sticky top-0 z-20 flex h-12 shrink-0 items-center gap-2.5 bg-background/85 px-4 backdrop-blur-lg lg:hidden">
        <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
          <SheetTrigger
            aria-label="Open menu"
            className="-ml-1 flex size-10 items-center justify-center rounded-xl text-muted-foreground transition-[color,scale] duration-200 ease-spring hover:text-foreground active:scale-90"
          >
            <MenuIcon className="size-5" />
          </SheetTrigger>
          <SheetContent side="left" showCloseButton={false} className="w-72 max-w-[85vw] gap-0 bg-background">
            <SheetTitle className="sr-only">Menu</SheetTitle>
            <SidebarBody
              view={view}
              onView={next => {
                onView(next);
                setMenuOpen(false);
              }}
              action={
                <SheetClose aria-label="Close menu" className={topButtonClass}>
                  <XIcon className="size-4.5" />
                </SheetClose>
              }
            />
          </SheetContent>
        </Sheet>
        <BrandMark className="size-7 rounded-lg" />
        <span className="text-base font-semibold">unnoodle</span>
      </header>

      {/* Clipped, not hidden, sideways: hidden would make it a scroll container and stop the docked composer sticking */}
      <main className="flex flex-1 flex-col overflow-x-clip lg:ml-[5px] lg:min-h-0 lg:overflow-y-auto lg:rounded-l-2xl lg:border-l">
        {children}
      </main>
    </div>
  );
}

const topButtonClass =
  'flex size-11 shrink-0 items-center justify-center rounded-[14px] bg-panel text-muted-foreground transition-[color,scale] duration-200 ease-spring hover:text-foreground active:scale-90 lg:size-10 group-data-[collapsed=true]/sidebar:w-full';
// Rows are taller in the phone menu, where fingers press them, than in the sidebar beside a mouse
const rowClass =
  'group/row flex h-11 items-center gap-2.5 rounded-xl px-2 text-base font-semibold transition-[background-color,scale] duration-200 ease-spring hover:bg-sidebar-accent active:scale-[0.98] aria-[current=page]:bg-sidebar-accent lg:h-10 lg:text-sm';
// Labels and secondary parts fade out when the sidebar collapses to icons. On the way back they wait for the sidebar
// to widen, so they don't show up squeezed.
const collapsible =
  'transition-[opacity,display] transition-discrete duration-200 starting:opacity-0 group-data-[collapsed=false]/sidebar:delay-150 group-data-[collapsed=true]/sidebar:hidden group-data-[collapsed=true]/sidebar:opacity-0';
const label = cn('truncate', collapsible);

const current = (item: View | undefined, view: View) => (item && sameView(item, view) ? 'page' : undefined);

function SidebarBody({ view, onView, action }: { view: View; onView: (view: View) => void; action: ReactNode }) {
  const { data: projects = [] } = useProjects();
  const { data: me } = useMe();
  const [creating, setCreating] = useState(false);

  return (
    <div className="flex h-full min-h-0 flex-col px-4 pt-2.5 pb-[max(1.25rem,env(safe-area-inset-bottom))] group-data-[collapsed=true]/sidebar:px-2.5">
      <div className="flex gap-1.5 group-data-[collapsed=true]/sidebar:flex-col">
        <m.div
          initial={false}
          animate="tangled"
          whileHover="straight"
          className="flex h-11 min-w-0 flex-1 items-center gap-2.5 rounded-[14px] bg-panel px-2 group-data-[collapsed=true]/sidebar:justify-center lg:h-10"
        >
          <BrandMark className="lg:size-7 lg:rounded-lg" />
          <span className={cn(label, 'text-base font-semibold')}>unnoodle</span>
        </m.div>
        {action}
      </div>

      <nav aria-label="Main" className="mt-5 flex flex-col gap-[3px]">
        {navItems.map(item => (
          <button
            key={item.label}
            type="button"
            title={item.label}
            aria-current={current(item.view, view)}
            onClick={() => item.view && onView(item.view)}
            className={rowClass}
          >
            <IconTile className={cn('bg-linear-to-b', item.tile)}>
              <item.icon className="size-4.5 fill-white/25 text-white lg:size-4" />
            </IconTile>
            <span className={label}>{item.label}</span>
          </button>
        ))}
      </nav>

      <section aria-labelledby="sidebar-projects" className="mt-8 flex min-h-0 flex-1 flex-col">
        <div className={cn(collapsible, 'flex items-center justify-between pr-1 pb-2 pl-2')}>
          <h2 id="sidebar-projects" className="text-sm text-[#828282]">
            Projects
          </h2>
          <button
            type="button"
            aria-label="New project"
            onClick={() => setCreating(true)}
            className="group/new flex size-8 items-center justify-center rounded-lg text-[#9a9a9a] transition-[color,background-color,scale] duration-200 ease-spring hover:bg-sidebar-accent hover:text-foreground active:scale-90"
          >
            <PlusIcon className="size-4.5 transition-[rotate] duration-500 ease-spring-bouncy group-hover/new:rotate-90 lg:size-4" />
          </button>
        </div>

        {/* The default folder: every generation, so it stays when the sidebar collapses to icons */}
        <button
          type="button"
          title="My generations"
          aria-current={current(folder(null), view)}
          onClick={() => onView(folder(null))}
          className={rowClass}
        >
          <IconTile className="bg-linear-to-b from-[#8de7f5] to-[#2687b3]">
            <SparklesIcon className="size-4.5 fill-white/25 text-white lg:size-4" />
          </IconTile>
          <span className={label}>My generations</span>
        </button>

        <ul aria-label="Projects" className={cn(collapsible, 'mt-[3px] flex min-h-0 flex-col gap-[3px] overflow-y-auto')}>
          {creating && (
            <li className="flex items-start gap-2.5 px-2 py-1">
              <IconTile className="mt-1 border border-white/10 bg-[#29292b] lg:mt-0.5">
                <PlusIcon className="size-4 text-[#b0b0b0]" />
              </IconTile>
              <NewProjectForm
                onCreated={project => {
                  setCreating(false);
                  onView(folder(project.id));
                }}
                onCancel={() => setCreating(false)}
                className="flex-1"
                inputClassName="h-9 lg:h-8 lg:text-sm"
              />
            </li>
          )}
          {projects.map(project => (
            <li key={project.id}>
              <m.button
                type="button"
                aria-current={current(folder(project.id), view)}
                onClick={() => onView(folder(project.id))}
                initial={false}
                animate="tangled"
                whileHover="straight"
                className={cn(rowClass, 'w-full')}
              >
                <IconTile className="bg-[#232426]">
                  <NoodleGlyph className="size-5 text-[#5c5d60] transition-colors duration-200 group-hover/row:text-[#a0a1a3] group-aria-[current=page]/row:text-lime" />
                </IconTile>
                <span className="truncate">{project.name}</span>
              </m.button>
            </li>
          ))}
        </ul>
      </section>

      <button
        type="button"
        title="All projects"
        aria-current={current(allProjects, view)}
        onClick={() => onView(allProjects)}
        className={cn(rowClass, 'mt-3')}
      >
        <IconTile className="border border-white/10 bg-linear-to-b from-[#3a3a3c] to-[#202022]">
          <ArchiveIcon className="size-4.5 text-white lg:size-4" />
        </IconTile>
        <span className={cn(label, 'flex-1 text-left')}>All projects</span>
        <ChevronRightIcon
          className={cn(label, 'size-5 text-[#8a8a8a] transition-[translate,opacity,display] group-hover/row:translate-x-0.5')}
        />
      </button>

      {me?.is_admin && <SmartQueueSwitch />}
      {me && <Account email={me.email} />}
    </div>
  );
}

/** Who is signed in, their credits, and a way out. */
function Account({ email }: { email: string }) {
  const [leaving, setLeaving] = useState(false);
  const { data: credits } = useCredits();

  async function signOut() {
    setLeaving(true);
    await api.signOut().catch(() => undefined);
    // A full load rather than a client-side move, so nothing cached for this account is left for the next one
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign('/');
  }

  return (
    <button
      type="button"
      title={`Signed in as ${email}. Sign out`}
      disabled={leaving}
      onClick={() => void signOut()}
      className={cn(rowClass, 'mt-[3px] h-auto py-1.5 disabled:opacity-60 lg:h-auto')}
    >
      <IconTile className="bg-[#232426]">
        <LogOutIcon className="size-4 text-[#a0a1a3] lg:size-3.5" />
      </IconTile>
      <span className={cn(collapsible, 'flex min-w-0 flex-1 flex-col text-left')}>
        <span className="truncate">Sign out</span>
        <span className="truncate text-xs font-normal text-[#828282]">
          {credits ? `${credits.balance} ${credits.balance === 1 ? 'credit' : 'credits'} · ` : ''}
          {email}
        </span>
      </span>
    </button>
  );
}

/** Lets quick generations go ahead of long ones in the queue. Off until turned on. Admins only, since it reorders
 * everyone's jobs. */
function SmartQueueSwitch() {
  const { data, update } = usePreferences();
  const on = data?.smart_queue ?? false;

  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-describedby="smart-queue-hint"
      title={`Smart Queue: ${on ? 'on' : 'off'}`}
      disabled={data === undefined}
      onClick={() => void update({ smart_queue: !on }).catch(() => undefined)}
      className={cn(rowClass, 'mt-[3px] h-auto py-1.5 disabled:opacity-60 lg:h-auto')}
    >
      <IconTile className="bg-linear-to-b from-[#f5d76e] to-[#c48a12]">
        <ZapIcon className="size-4.5 fill-white/25 text-white lg:size-4" />
      </IconTile>
      <span className={cn(collapsible, 'flex min-w-0 flex-1 flex-col text-left')}>
        <span className="truncate">Smart Queue</span>
        <span id="smart-queue-hint" className="truncate text-xs font-normal text-[#828282]">
          Quick ones go first
        </span>
      </span>
      <span
        aria-hidden
        className={cn(
          collapsible,
          'relative h-6 w-10 shrink-0 rounded-full transition-colors duration-200',
          on ? 'bg-lime' : 'bg-[#3a3a3c]'
        )}
      >
        <span
          className={cn(
            'absolute top-0.5 left-0.5 size-5 rounded-full bg-white shadow transition-[translate] duration-300 ease-spring',
            on && 'translate-x-4'
          )}
        />
      </span>
    </button>
  );
}

function IconTile({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <span
      className={cn(
        'flex size-8 shrink-0 items-center justify-center rounded-[9px] shadow-[inset_0_1px_0_rgb(255_255_255/0.35),0_1px_2px_rgb(0_0_0/0.4)] transition-[scale,rotate] duration-500 ease-spring-bouncy group-hover/row:scale-110 group-hover/row:-rotate-6 lg:size-7 lg:rounded-lg',
        className
      )}
    >
      {children}
    </span>
  );
}
