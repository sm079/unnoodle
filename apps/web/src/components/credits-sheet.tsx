'use client';

import { useRef, useState, type FormEvent } from 'react';
import { AnimatePresence, m, type Variants } from 'motion/react';
import { useSWRConfig } from 'swr';
import { CreditAmount, CreditGlyph } from '@/components/credit-glyph';
import { RollingValue } from '@/components/rolling-value';
import { Sheet, SheetContent, SheetDescription, SheetTitle } from '@/components/ui/sheet';
import { api, messageOf, paths } from '@/lib/api';
import { shake } from '@/lib/motion';
import { cn } from '@/lib/utils';

// What buying will offer once it opens. Shown now so the way to more credits is clear, marked as not open yet.
const packs = [
  { credits: 100, name: 'Starter' },
  { credits: 500, name: 'Creator' },
  { credits: 2000, name: 'Studio' }
];

const rise: Variants = {
  hidden: { opacity: 0, y: 14 },
  shown: (n: number) => ({ opacity: 1, y: 0, transition: { type: 'spring', bounce: 0.25, visualDuration: 0.4, delay: 0.12 + n * 0.06 } })
};

interface CreditsSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** What the request that opened it costs. */
  cost: number;
  balance: number;
  /** Goes ahead with that request, once there's enough. */
  onContinue: () => void;
}

/** Opens when Generate is pressed without enough credits: how far short, how to get more, and a way to carry on. */
export function CreditsSheet({ open, onOpenChange, cost, balance, onContinue }: CreditsSheetProps) {
  const enough = balance >= cost;
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="bottom"
        className="mx-auto max-h-[94dvh] max-w-lg gap-0 overflow-y-auto overscroll-contain rounded-t-[28px] border-0 bg-panel px-5 pt-6 pb-[max(1.25rem,env(safe-area-inset-bottom))] lg:bottom-6 lg:rounded-[28px]"
      >
        <div className="flex items-center gap-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-linear-to-b from-[#ff8763] to-brand text-white shadow-[inset_0_1px_0_rgb(255_255_255/0.5)]">
            <CreditGlyph className="size-5" />
          </span>
          <div className="flex min-w-0 flex-col">
            <SheetTitle className="font-display text-xl font-bold tracking-[-0.01em] uppercase font-stretch-[86%]">
              {enough ? "You're all set" : 'Get more credits'}
            </SheetTitle>
            <SheetDescription className="text-sm text-[#a0a1a3]">
              {enough ? 'You have enough for this one now.' : 'Every picture and video is paid for in credits.'}
            </SheetDescription>
          </div>
        </div>

        {/* Keyed by open, so the bar fills from empty each time the sheet opens */}
        <Shortfall key={String(open)} cost={cost} balance={balance} />

        <AnimatePresence initial={false} mode="popLayout">
          {enough ? (
            <m.button
              key="continue"
              type="button"
              onClick={onContinue}
              initial={{ opacity: 0, scale: 0.94 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              className="mt-5 flex h-13 w-full items-center justify-center gap-3 rounded-[16px] bg-linear-to-b from-[#ff6a45] via-[#ff5b3a] to-[#f24a2a] text-white shadow-[0_3px_0_var(--color-brand-edge)] transition-[translate,box-shadow] duration-75 active:translate-y-[2px] active:shadow-[0_1px_0_var(--color-brand-edge)]"
            >
              <span className="font-display text-base font-extrabold tracking-[0.02em] uppercase font-stretch-[88%]">Generate</span>
              <CreditAmount value={cost} className="text-sm font-semibold opacity-75" />
            </m.button>
          ) : (
            <m.div key="packs" exit={{ opacity: 0, transition: { duration: 0.15 } }}>
              <ul className="mt-5 grid grid-cols-3 gap-2" aria-label="Credit packs">
                {packs.map((pack, n) => (
                  <m.li
                    key={pack.credits}
                    custom={n}
                    variants={rise}
                    initial="hidden"
                    animate="shown"
                    aria-disabled
                    className="relative flex flex-col items-center gap-1 overflow-hidden rounded-2xl border border-white/[0.06] bg-panel-raised px-2 pt-4 pb-3 text-center"
                  >
                    <CreditAmount value={pack.credits} className="text-lg font-bold text-white [&_svg]:text-brand" />
                    <span className="text-xs text-[#828282]">{pack.name}</span>
                    <span className="mt-1.5 rounded-full bg-white/[0.06] px-2 py-0.5 text-[0.6875rem] font-semibold text-[#a0a1a3]">
                      Coming soon
                    </span>
                  </m.li>
                ))}
              </ul>
              <p className="mt-3 text-center text-xs text-[#828282]">Buying opens soon. For now, credits come with an invite code.</p>
            </m.div>
          )}
        </AnimatePresence>

        <CodeEntry balance={balance} />
      </SheetContent>
    </Sheet>
  );
}

/** What it needs, what there is, and a bar between them that fills as credits arrive. */
function Shortfall({ cost, balance }: { cost: number; balance: number }) {
  const share = Math.min(1, balance / Math.max(cost, 1));
  const enough = balance >= cost;
  return (
    <div className="mt-6 rounded-2xl bg-panel-raised p-4">
      <div className="flex items-end justify-between gap-3">
        <div className="flex flex-col">
          <span className="text-xs text-[#828282]">This needs</span>
          <CreditAmount value={cost} className="text-2xl font-bold" />
        </div>
        <div className="flex flex-col items-end">
          <span className="text-xs text-[#828282]">You have</span>
          <span
            className={cn('inline-flex items-center gap-[0.2em] text-2xl font-bold tabular-nums', enough ? 'text-brand' : 'text-white')}
          >
            <CreditGlyph />
            <RollingValue value={balance} />
          </span>
        </div>
      </div>
      <div
        className="mt-3 h-2 overflow-hidden rounded-full bg-white/[0.07]"
        role="meter"
        aria-label="Credits you have of what this needs"
        aria-valuemin={0}
        aria-valuemax={cost}
        aria-valuenow={Math.min(balance, cost)}
      >
        <m.div
          className={cn('h-full origin-left rounded-full', enough ? 'bg-brand' : 'bg-[#e8a33d]')}
          initial={{ scaleX: 0 }}
          animate={{ scaleX: share }}
          transition={{ type: 'spring', bounce: 0.15, visualDuration: 0.6, delay: 0.15 }}
        />
      </div>
      <AnimatePresence initial={false} mode="wait">
        <m.p
          key={enough ? 'enough' : balance}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          className="mt-2 text-xs text-[#a0a1a3]"
        >
          {enough ? (
            'Enough for this request.'
          ) : (
            <>
              Short by <CreditAmount value={cost - balance} className="font-semibold text-white" />
            </>
          )}
        </m.p>
      </AnimatePresence>
    </div>
  );
}

/** A small link that opens into a field for an invite code. */
function CodeEntry({ balance }: { balance: number }) {
  const { mutate } = useSWRConfig();
  const [entering, setEntering] = useState(false);
  const [code, setCode] = useState('');
  const [sending, setSending] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [added, setAdded] = useState<number | null>(null);
  const field = useRef<HTMLDivElement>(null);

  async function redeem(event: FormEvent) {
    event.preventDefault();
    if (sending || code.trim() === '') return;
    setSending(true);
    setProblem(null);
    try {
      const credits = await mutate(paths.credits, api.redeem(code.trim()), { revalidate: false });
      setAdded((credits?.balance ?? balance) - balance);
      setCode('');
      setEntering(false);
    } catch (error) {
      setProblem(messageOf(error));
      shake(field.current);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="mt-5 flex min-h-11 flex-col items-center justify-center">
      {/* One leaves before the other comes, so the link never shows through the field */}
      <AnimatePresence initial={false} mode="wait">
        {entering ? (
          <m.form
            key="field"
            onSubmit={redeem}
            aria-label="Invite code"
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.96 }}
            className="flex w-full flex-col gap-1.5"
          >
            <div ref={field} className="flex gap-2">
              <input
                autoFocus
                value={code}
                onChange={event => {
                  setCode(event.target.value);
                  setProblem(null);
                }}
                onKeyDown={event => event.key === 'Escape' && code === '' && setEntering(false)}
                aria-label="Invite code"
                aria-invalid={problem !== null}
                placeholder="Invite code"
                autoCapitalize="characters"
                autoComplete="off"
                spellCheck={false}
                enterKeyHint="done"
                disabled={sending}
                // 16px at least, or iOS zooms the page in when the field gets focus
                className="h-11 min-w-0 flex-1 rounded-xl bg-white/[0.06] px-3.5 text-base tracking-[0.08em] uppercase outline-none placeholder:tracking-normal placeholder:text-[#7c7d7f] placeholder:normal-case focus-visible:ring-2 focus-visible:ring-white/20 disabled:opacity-60 aria-invalid:ring-2 aria-invalid:ring-[#e8a33d]/60"
              />
              <button
                type="submit"
                disabled={sending || code.trim() === ''}
                className="h-11 shrink-0 rounded-xl bg-white px-4 text-sm font-semibold text-black transition-[opacity,scale] duration-200 ease-spring active:scale-95 disabled:opacity-40"
              >
                {sending ? 'Adding…' : 'Add'}
              </button>
            </div>
            {problem && (
              <p role="alert" className="px-1 text-xs text-[#e8a33d]">
                {problem}
              </p>
            )}
          </m.form>
        ) : (
          <m.p key="link" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="text-sm text-[#828282]">
            {added !== null ? (
              <span role="status" className="text-brand">
                <CreditAmount value={added} className="font-semibold" /> added.{' '}
              </span>
            ) : (
              'Have a code? '
            )}
            <button
              type="button"
              onClick={() => {
                setEntering(true);
                setAdded(null);
              }}
              className="font-semibold text-white underline decoration-white/30 underline-offset-4 transition-colors hover:decoration-white"
            >
              {added !== null ? 'Enter another' : 'Enter code'}
            </button>
          </m.p>
        )}
      </AnimatePresence>
    </div>
  );
}
