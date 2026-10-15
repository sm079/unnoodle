import { cn } from '@/lib/utils';

/** A tangled line that straightens out. Drawn in currentColor so it works on a tile or on its own. */
export function NoodleGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden className={cn('size-4', className)}>
      <path
        d="M3 15.5c1.6-5 4.4-5 5.2-1.8.7 2.9 3.3 3 4.3-.7.6-2.1 1.6-3 3-3H21"
        stroke="currentColor"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        'flex size-8 shrink-0 items-center justify-center rounded-[9px] bg-linear-to-b from-[#e6ff3d] to-lime text-black shadow-[inset_0_1px_0_rgb(255_255_255/0.5)]',
        className
      )}
    >
      <NoodleGlyph className="size-5" />
    </span>
  );
}
