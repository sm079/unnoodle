'use client';

import Link from 'next/link';
import { m } from 'motion/react';
import { BrandMark } from '@/components/brand-mark';
import { Sheet, SheetContent, SheetDescription, SheetTitle } from '@/components/ui/sheet';

export type DemoReason = 'generate' | 'upload' | 'project';

const words: Record<DemoReason, { title: string; description: string }> = {
  generate: { title: 'Make your own', description: 'This is a look around. Sign in to generate pictures and videos of your own.' },
  upload: { title: 'Use your own photos', description: 'This is a look around. Sign in to attach your own photos and clips.' },
  project: { title: 'Keep your own projects', description: 'This is a look around. Sign in to file what you make in projects.' }
};

// Back in the studio after signing in
const next = encodeURIComponent('/generate');

/** Opens in /demo when something needs an account: what it needs, and the way in. */
export function DemoSheet({ open, onOpenChange, reason }: { open: boolean; onOpenChange: (open: boolean) => void; reason: DemoReason }) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="bottom"
        className="mx-auto max-h-[94dvh] max-w-lg gap-0 overflow-y-auto overscroll-contain rounded-t-[28px] border-0 bg-panel px-5 pt-6 pb-[max(1.25rem,env(safe-area-inset-bottom))]"
      >
        <m.div initial={false} animate="tangled" whileHover="straight" className="flex items-center gap-3">
          <BrandMark className="size-10 shrink-0 rounded-xl" />
          <div className="flex min-w-0 flex-col">
            <SheetTitle className="font-display text-xl font-bold tracking-[-0.01em] uppercase font-stretch-[86%]">
              {words[reason].title}
            </SheetTitle>
            <SheetDescription className="text-sm text-[#a0a1a3]">{words[reason].description}</SheetDescription>
          </div>
        </m.div>

        <div className="mt-6 flex flex-col gap-2">
          <Link
            href={`/sign-in?next=${next}`}
            className="flex h-13 w-full items-center justify-center rounded-[16px] bg-linear-to-b from-[#ff6a45] via-[#ff5b3a] to-[#f24a2a] font-display text-base font-extrabold tracking-[0.02em] text-white uppercase font-stretch-[88%] shadow-[0_3px_0_var(--color-brand-edge)] transition-[translate,box-shadow] duration-75 active:translate-y-[2px] active:shadow-[0_1px_0_var(--color-brand-edge)]"
          >
            Sign in
          </Link>
          <Link
            href={`/sign-up?next=${next}`}
            className="flex h-12 w-full items-center justify-center rounded-[16px] bg-white/[0.08] text-[0.9375rem] font-semibold text-white transition-[background-color,scale] duration-200 ease-spring hover:bg-white/[0.14] active:scale-[0.98]"
          >
            Create an account
          </Link>
        </div>
        <p className="mt-3 text-center text-xs text-[#828282]">Generating is invite only for now. Credits come with an invite code.</p>
      </SheetContent>
    </Sheet>
  );
}
