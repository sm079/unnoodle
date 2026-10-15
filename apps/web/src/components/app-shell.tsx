'use client';

import { useState, type ComponentType, type ReactNode } from 'react';
import Link from 'next/link';
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
  /** Left out for pages that don't exist yet. */
  href?: string;
}

const navItems: NavItem[] = [
  { label: 'Home', icon: HouseIcon, tile: 'from-[#d4d4d4] to-[#4d4d4d]', href: '/generate' },
  { label: 'My generations', icon: SparklesIcon, tile: 'from-[#8de7f5] to-[#2687b3]' },
  { label: 'My favorites', icon: HeartIcon, tile: 'from-[#ffa1cb] to-[#d23c7c]' }
];

interface AppShellProps {
  projects: Project[];
  children: ReactNode;
}

export function AppShell({ projects, children }: AppShellProps) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="flex h-dvh flex-col lg:flex-row">
      <aside
        data-collapsed={collapsed}
        aria-label="Sidebar"
        className="group/sidebar hidden w-[293px] shrink-0 flex-col overflow-hidden rounded-r-2xl border-r transition-[width] duration-300 ease-in-out-quart data-[collapsed=true]:w-[76px] motion-reduce:transition-none lg:flex"
      >
        <SidebarBody
          projects={projects}
          action={
            <button type="button" onClick={() => setCollapsed(!collapsed)} aria-label="Toggle sidebar" className={topButtonClass}>
              <PanelLeftIcon className="size-[18px]" />
            </button>
          }
        />
      </aside>

      <header className="flex h-14 shrink-0 items-center gap-3 px-4 lg:hidden">
        <Sheet>
          <SheetTrigger
            aria-label="Open menu"
            className="flex size-10 items-center justify-center rounded-xl bg-panel text-muted-foreground transition-[color,scale] duration-200 ease-spring hover:text-foreground active:scale-90"
          >
            <MenuIcon className="size-5" />
          </SheetTrigger>
          <SheetContent side="left" showCloseButton={false} className="w-[293px] gap-0 bg-background">
            <SheetTitle className="sr-only">Menu</SheetTitle>
            <SidebarBody
              projects={projects}
              action={
                <SheetClose aria-label="Close menu" className={topButtonClass}>
                  <XIcon className="size-[18px]" />
                </SheetClose>
              }
            />
          </SheetContent>
        </Sheet>
        <BrandMark />
        <span className="text-[17px] font-semibold">unnoodle</span>
      </header>

      <main className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto lg:ml-[5px] lg:rounded-l-2xl lg:border-l">{children}</main>
    </div>
  );
}

const topButtonClass =
  'flex h-[43px] w-11 shrink-0 items-center justify-center rounded-[14px] bg-panel text-muted-foreground transition-[color,scale] duration-200 ease-spring hover:text-foreground active:scale-90 group-data-[collapsed=true]/sidebar:w-full';
const rowClass =
  'group/row flex h-[45px] items-center gap-2.5 rounded-xl px-2 text-[17px] font-semibold transition-[background-color,scale] duration-200 ease-spring active:scale-[0.98]';
// Labels and secondary parts fade out when the sidebar collapses to icons. On the way back they wait for the sidebar
// to widen, so they don't show up squeezed.
const collapsible =
  'transition-[opacity,display] transition-discrete duration-200 starting:opacity-0 group-data-[collapsed=false]/sidebar:delay-150 group-data-[collapsed=true]/sidebar:hidden group-data-[collapsed=true]/sidebar:opacity-0';
const label = cn('truncate', collapsible);

const smallButtonClass = 'rounded-md p-1 transition-[color,scale] duration-200 ease-spring hover:text-foreground active:scale-85';

function SidebarBody({ projects, action }: { projects: Project[]; action: ReactNode }) {
  return (
    <div className="flex h-full min-h-0 flex-col px-4 pt-2.5 pb-5 group-data-[collapsed=true]/sidebar:px-2.5">
      <div className="flex gap-1.5 group-data-[collapsed=true]/sidebar:flex-col">
        <m.div
          initial={false}
          animate="tangled"
          whileHover="straight"
          className="flex h-[43px] min-w-0 flex-1 items-center gap-2.5 rounded-[14px] bg-panel px-2 group-data-[collapsed=true]/sidebar:justify-center"
        >
          <BrandMark />
          <span className={cn(label, 'text-[17px] font-semibold')}>unnoodle</span>
        </m.div>
        {action}
      </div>

      <nav aria-label="Main" className="mt-5 flex flex-col gap-[3px]">
        {navItems.map(item => {
          const content = (
            <>
              <IconTile className={cn('bg-linear-to-b', item.tile)}>
                <item.icon className="size-[18px] fill-white/25 text-white" />
              </IconTile>
              <span className={label}>{item.label}</span>
            </>
          );
          const className = cn(rowClass, 'hover:bg-sidebar-accent aria-[current=page]:bg-sidebar-accent');
          return item.href ? (
            <Link key={item.label} href={item.href} aria-current="page" title={item.label} className={className}>
              {content}
            </Link>
          ) : (
            <button key={item.label} type="button" title={item.label} className={className}>
              {content}
            </button>
          );
        })}
      </nav>

      <section aria-labelledby="sidebar-projects" className={cn(collapsible, 'mt-10 flex min-h-0 flex-1 flex-col')}>
        <div className="flex items-center justify-between px-2 pb-3">
          <h2 id="sidebar-projects" className="text-[15px] text-[#828282]">
            Projects
          </h2>
          <div className="flex gap-1 text-[#9a9a9a]">
            <button type="button" aria-label="Search projects" className={smallButtonClass}>
              <SearchIcon className="size-[18px]" />
            </button>
            <button type="button" aria-label="Sort projects" className={smallButtonClass}>
              <ArrowDownWideNarrowIcon className="size-[18px]" />
            </button>
          </div>
        </div>
        <ul className="flex min-h-0 flex-col gap-[3px] overflow-y-auto">
          <li>
            <button type="button" className={cn(rowClass, 'w-full text-[#828282] hover:bg-sidebar-accent')}>
              <IconTile className="size-[30px] border border-white/10 bg-[#29292b]">
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
                <IconTile className="size-[30px] bg-[#232426]">
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
          <ArchiveIcon className="size-[18px] text-white" />
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
        'flex size-8 shrink-0 items-center justify-center rounded-[9px] shadow-[inset_0_1px_0_rgb(255_255_255/0.35),0_1px_2px_rgb(0_0_0/0.4)] transition-[scale,rotate] duration-500 ease-spring-bouncy group-hover/row:scale-110 group-hover/row:-rotate-6',
        className
      )}
    >
      {children}
    </span>
  );
}
