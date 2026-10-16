import { cn } from '@/lib/utils';

/** The sign for credits: a four-pointed spark with a small one beside it. Drawn in the current text colour. */
export function CreditGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden className={cn('size-[1.1em] shrink-0', className)} fill="currentColor">
      <path d="M14.5 2.5c.6 4.9 2.6 6.9 7.5 7.5-4.9.6-6.9 2.6-7.5 7.5-.6-4.9-2.6-6.9-7.5-7.5 4.9-.6 6.9-2.6 7.5-7.5Z" />
      <path d="M5.5 14c.3 2.5 1.2 3.4 3.5 3.75-2.3.35-3.2 1.25-3.5 3.75-.3-2.5-1.2-3.4-3.5-3.75 2.3-.35 3.2-1.25 3.5-3.75Z" />
    </svg>
  );
}

/** An amount of credits as the app shows it everywhere: the spark, then the number. */
export function CreditAmount({ value, className }: { value: number; className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-[0.2em] tabular-nums', className)}>
      <CreditGlyph />
      {value.toLocaleString('en')}
      <span className="sr-only"> {value === 1 ? 'credit' : 'credits'}</span>
    </span>
  );
}
