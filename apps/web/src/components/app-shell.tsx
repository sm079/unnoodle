'use client';

import { useState, type ComponentType, type ReactNode } from 'react';
import { m } from 'motion/react';
import {
  ArchiveIcon,
  ArrowDownWideNarrowIcon,
  ChevronRightIcon,
  HeartIcon,
  HouseIcon,
  MenuIcon,
  PanelLeftIcon,
  PlusIcon,
  SearchIcon,
  SparklesIcon,
  XIcon
} from 'lucide-react';
import { BrandMark, NoodleGlyph } from '@/components/brand-mark';
import { Sheet, SheetClose, SheetContent, SheetTitle, SheetTrigger } from '@/components/ui/sheet';
import { cn } from '@/lib/utils';
import type { Project } from '@/lib/types';

interface NavItem {
  label: string;
  icon: ComponentType<{ className?: string }>;
  /** Gradient of the icon tile. */
  tile: string;
  /** The view it opens; left out for ones that don't exist yet. */
  view?: View;
}

/** The home screen, or the gallery that takes its place once something is generating. */
export type View = 'home' | 'gallery';

const navItems: NavItem[] = [
  { label: 'Home', icon: HouseIcon, tile: 'from-[#d4d4d4] to-[#4d4d4d]', view: 'home' },
  { label: 'My generations', icon: SparklesIcon, tile: 'from-[#8de7f5] to-[#2687b3]', view: 'gallery' },
  { label: 'My favorites', icon: HeartIcon, tile: 'from-[#ffa1cb] to-[#d23c7c]' }
];

interface AppShellProps {
  projects: Project[];
  view: View;
  onView: (view: View) => void;
  children: ReactNode;
}

export function AppShell({ projects, view, onView, children }: AppShellProps) {
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
          projects={projects}
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
              projects={projects}
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
const rowClass =
  'group/row flex h-11 items-center gap-2.5 rounded-xl px-2 text-base font-semibold transition-[background-color,scale] duration-200 ease-spring active:scale-[0.98] lg:h-10 lg:text-sm';
// Labels and secondary parts fade out when the sidebar collapses to icons. On the way back they wait for the sidebar
// to widen, so they don't show up squeezed.
const collapsible =
  'transition-[opacity,display] transition-discrete duration-200 starting:opacity-0 group-data-[collapsed=false]/sidebar:delay-150 group-data-[collapsed=true]/sidebar:hidden group-data-[collapsed=true]/sidebar:opacity-0';
const label = cn('truncate', collapsible);

const smallButtonClass = 'rounded-md p-1 transition-[color,scale] duration-200 ease-spring hover:text-foreground active:scale-85';

function SidebarBody({
  projects,
  view,
  onView,
  action
}: {
  projects: Project[];
  view: View;
  onView: (view: View) => void;
  action: ReactNode;
}) {
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
        {navItems.map(item => {
          const content = (
            <>
              <IconTile className={cn('bg-linear-to-b', item.tile)}>
                <item.icon className="size-4.5 fill-white/25 text-white lg:size-4" />
              </IconTile>
              <span className={label}>{item.label}</span>
            </>
          );
          const className = cn(rowClass, 'hover:bg-sidebar-accent aria-[current=page]:bg-sidebar-accent');
          return (
            <button
              key={item.label}
              type="button"
              title={item.label}
              aria-current={item.view === view ? 'page' : undefined}
              onClick={() => item.view && onView(item.view)}
              className={className}
            >
              {content}
            </button>
          );
        })}
      </nav>

      <section aria-labelledby="sidebar-projects" className={cn(collapsible, 'mt-10 flex min-h-0 flex-1 flex-col')}>
        <div className="flex items-center justify-between px-2 pb-3">
          <h2 id="sidebar-projects" className="text-sm text-[#828282]">
            Projects
          </h2>
          <div className="flex gap-1 text-[#9a9a9a]">
            <button type="button" aria-label="Search projects" className={smallButtonClass}>
              <SearchIcon className="size-4.5 lg:size-4" />
            </button>
            <button type="button" aria-label="Sort projects" className={smallButtonClass}>
              <ArrowDownWideNarrowIcon className="size-4.5 lg:size-4" />
            </button>
          </div>
        </div>
        <ul className="flex min-h-0 flex-col gap-[3px] overflow-y-auto">
          <li>
            <button type="button" className={cn(rowClass, 'w-full text-[#828282] hover:bg-sidebar-accent')}>
              <IconTile className="border border-white/10 bg-[#29292b]">
                <PlusIcon className="size-4 text-[#b0b0b0] transition-[rotate] duration-500 ease-spring-bouncy group-hover/row:rotate-90" />
              </IconTile>
              New project
            </button>
          </li>
          {projects.map(project => (
            <li key={project.id}>
              <m.button
                type="button"
                initial={false}
                animate="tangled"
                whileHover="straight"
                className={cn(rowClass, 'w-full hover:bg-sidebar-accent')}
              >
                <IconTile className="bg-[#232426]">
                  <NoodleGlyph className="size-5 text-[#5c5d60] transition-colors duration-200 group-hover/row:text-[#a0a1a3]" />
                </IconTile>
                <span className="truncate">{project.name}</span>
              </m.button>
            </li>
          ))}
        </ul>
      </section>

      <div className="mt-auto hidden flex-1 group-data-[collapsed=true]/sidebar:block" />

      <button type="button" title="All projects" className={cn(rowClass, 'hover:bg-sidebar-accent')}>
        <IconTile className="border border-white/10 bg-linear-to-b from-[#3a3a3c] to-[#202022]">
          <ArchiveIcon className="size-4.5 text-white lg:size-4" />
        </IconTile>
        <span className={cn(label, 'flex-1 text-left')}>All projects</span>
        <ChevronRightIcon
          className={cn(label, 'size-5 text-[#8a8a8a] transition-[translate,opacity,display] group-hover/row:translate-x-0.5')}
        />
      </button>
    </div>
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
