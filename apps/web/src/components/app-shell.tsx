'use client';

import { useState, type ComponentType, type ReactNode } from 'react';
import Link from 'next/link';
import {
  ArchiveIcon,
  ArrowDownWideNarrowIcon,
  AtSignIcon,
  BellIcon,
  ChevronRightIcon,
  GemIcon,
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
import type { Project, User } from '@/lib/types';

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
  { label: 'My elements', icon: AtSignIcon, tile: 'from-[#8db5ff] to-[#2c58d0]' },
  { label: 'My favorites', icon: HeartIcon, tile: 'from-[#ffa1cb] to-[#d23c7c]' }
];

interface AppShellProps {
  projects: Project[];
  user: User;
  children: ReactNode;
}

export function AppShell({ projects, user, children }: AppShellProps) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="flex h-dvh flex-col lg:flex-row">
      <aside
        data-collapsed={collapsed}
        aria-label="Sidebar"
        className="group/sidebar hidden w-[293px] shrink-0 flex-col rounded-r-2xl border-r transition-[width] duration-200 data-[collapsed=true]:w-[76px] lg:flex"
      >
        <SidebarBody
          projects={projects}
          user={user}
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
            className="flex size-10 items-center justify-center rounded-xl bg-panel text-muted-foreground hover:text-foreground"
          >
            <MenuIcon className="size-5" />
          </SheetTrigger>
          <SheetContent side="left" showCloseButton={false} className="w-[293px] gap-0 bg-background">
            <SheetTitle className="sr-only">Menu</SheetTitle>
            <SidebarBody
              projects={projects}
              user={user}
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
  'flex h-[43px] w-11 shrink-0 items-center justify-center rounded-[14px] bg-panel text-muted-foreground hover:text-foreground group-data-[collapsed=true]/sidebar:w-full';
const rowClass = 'flex h-[45px] items-center gap-2.5 rounded-xl px-2 text-[17px] font-semibold transition-colors';
// Labels and secondary parts disappear when the sidebar is collapsed to icons
const label = 'truncate group-data-[collapsed=true]/sidebar:hidden';

function SidebarBody({ projects, user, action }: { projects: Project[]; user: User; action: ReactNode }) {
  return (
    <div className="flex h-full min-h-0 flex-col px-4 pt-2.5 pb-5 group-data-[collapsed=true]/sidebar:px-2.5">
      <div className="flex gap-1.5 group-data-[collapsed=true]/sidebar:flex-col">
        <div className="flex h-[43px] min-w-0 flex-1 items-center gap-2.5 rounded-[14px] bg-panel px-2 group-data-[collapsed=true]/sidebar:justify-center">
          <BrandMark />
          <span className={cn(label, 'text-[17px] font-semibold')}>unnoodle</span>
        </div>
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

      <section aria-labelledby="sidebar-projects" className="mt-10 flex min-h-0 flex-1 flex-col group-data-[collapsed=true]/sidebar:hidden">
        <div className="flex items-center justify-between px-2 pb-3">
          <h2 id="sidebar-projects" className="text-[15px] text-[#828282]">
            Projects
          </h2>
          <div className="flex gap-1 text-[#9a9a9a]">
            <button type="button" aria-label="Search projects" className="rounded-md p-1 hover:text-foreground">
              <SearchIcon className="size-[18px]" />
            </button>
            <button type="button" aria-label="Sort projects" className="rounded-md p-1 hover:text-foreground">
              <ArrowDownWideNarrowIcon className="size-[18px]" />
            </button>
          </div>
        </div>
        <ul className="flex min-h-0 flex-col gap-[3px] overflow-y-auto">
          <li>
            <button type="button" className={cn(rowClass, 'w-full text-[#828282] hover:bg-sidebar-accent')}>
              <IconTile className="size-[30px] border border-white/10 bg-[#29292b]">
                <PlusIcon className="size-4 text-[#b0b0b0]" />
              </IconTile>
              New project
            </button>
          </li>
          {projects.map(project => (
            <li key={project.id}>
              <button type="button" className={cn(rowClass, 'w-full hover:bg-sidebar-accent')}>
                <IconTile className="size-[30px] bg-[#232426]">
                  <NoodleGlyph className="size-5 text-[#5c5d60]" />
                </IconTile>
                <span className="truncate">{project.name}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      <div className="mt-auto hidden flex-1 group-data-[collapsed=true]/sidebar:block" />

      <button type="button" title="All projects" className={cn(rowClass, 'mb-3 hover:bg-sidebar-accent')}>
        <IconTile className="border border-white/10 bg-linear-to-b from-[#3a3a3c] to-[#202022]">
          <ArchiveIcon className="size-[18px] text-white" />
        </IconTile>
        <span className={cn(label, 'flex-1 text-left')}>All projects</span>
        <ChevronRightIcon className={cn(label, 'size-5 text-[#8a8a8a]')} />
      </button>

      <div className="-mx-4 border-t group-data-[collapsed=true]/sidebar:-mx-2.5" />

      <button type="button" title="Pricing" className={cn(rowClass, 'mt-3 bg-[#21131a] px-3 hover:bg-[#2a1720]')}>
        <GemIcon className="size-5 shrink-0 text-[#ff2a6d]" />
        <span className={cn(label, 'flex-1 text-left')}>Pricing</span>
        <span
          className={cn(label, 'rounded-full bg-linear-to-r from-[#ff1f6a] to-[#ff3dba] px-2 py-0.5 text-[13px] leading-tight font-bold')}
        >
          30% OFF
        </span>
      </button>

      <div className="mt-2 flex items-center gap-2.5 px-2 group-data-[collapsed=true]/sidebar:justify-center">
        <span
          aria-hidden
          className="flex size-[30px] shrink-0 items-center justify-center rounded-full bg-linear-to-br from-[#f6a35b] to-[#7a3d8c] text-sm font-bold ring-[2.5px] ring-lime ring-offset-2 ring-offset-background"
        >
          {user.name.slice(0, 1)}
        </span>
        <span className={cn(label, 'flex-1 text-[17px] font-semibold')}>{user.name}</span>
        <button
          type="button"
          aria-label="Notifications"
          className={cn(
            label,
            'flex size-[30px] items-center justify-center rounded-full bg-sidebar-accent text-[#9a9a9a] hover:text-foreground'
          )}
        >
          <BellIcon className="size-4" />
        </button>
      </div>
    </div>
  );
}

function IconTile({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <span
      className={cn(
        'flex size-8 shrink-0 items-center justify-center rounded-[9px] shadow-[inset_0_1px_0_rgb(255_255_255/0.35),0_1px_2px_rgb(0_0_0/0.4)]',
        className
      )}
    >
      {children}
    </span>
  );
}
