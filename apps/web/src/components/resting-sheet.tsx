'use client';

import { MoonIcon } from 'lucide-react';
import { Sheet, SheetClose, SheetContent, SheetDescription, SheetTitle } from '@/components/ui/sheet';

/** Opens from Generate when today's GPU time is used up: why nothing can be made now, and when it can again. */
export function RestingSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="bottom"
        className="mx-auto max-h-[94dvh] max-w-lg gap-0 overflow-y-auto overscroll-contain rounded-t-[28px] border-0 bg-panel px-5 pt-6 pb-[max(1.25rem,env(safe-area-inset-bottom))]"
      >
        <div className="flex items-center gap-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-linear-to-b from-[#f5c26b] to-[#e8a33d] text-[#2a1a05] shadow-[inset_0_1px_0_rgb(255_255_255/0.5)]">
            <MoonIcon className="size-5" />
          </span>
          <div className="flex min-w-0 flex-col">
            <SheetTitle className="font-display text-xl font-bold tracking-[-0.01em] uppercase font-stretch-[86%]">
              Resting until tomorrow
            </SheetTitle>
            <SheetDescription className="text-sm text-[#a0a1a3]">
              The GPU has done its hours for today, so nothing new can start. Your prompt stays here.
            </SheetDescription>
          </div>
        </div>
        <p className="mt-5 rounded-2xl bg-panel-raised p-4 text-sm leading-relaxed text-[#c8c9cb]">
          A GPU is rented only while there is something to make, for a few hours a day at most, so a small app stays cheap to run. Nothing
          was charged.
        </p>
        <SheetClose className="mt-5 flex h-12 w-full items-center justify-center rounded-[16px] bg-white/[0.08] text-[0.9375rem] font-semibold text-white transition-[background-color,scale] duration-200 ease-spring hover:bg-white/[0.14] active:scale-[0.98]">
          OK
        </SheetClose>
      </SheetContent>
    </Sheet>
  );
}
