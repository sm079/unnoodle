'use client';

// The /demo page: the studio on a copy of the demo project (demo-snapshot.json, made by the API's app.snapshot), so it
// can be looked around without an account or the API. Reads are answered from the copy; anything that would change
// something asks the visitor to sign in instead.

import { createContext, useContext, useState, type ReactNode } from 'react';
import { SWRConfig, type Middleware } from 'swr';
import { DemoSheet, type DemoReason } from '@/components/demo-sheet';
import snapshot from './demo-snapshot.json';

const answers: Record<string, unknown> = snapshot;

/** Every request by its API path; anything not in the copy (the account, its settings) is empty */
const fromSnapshot: Middleware = useSWRNext => (key, fetcher, config) => {
  const answer = async (path: string) => answers[path] ?? null;
  return useSWRNext(key, fetcher && (answer as typeof fetcher), config);
};

const DemoContext = createContext<((reason: DemoReason) => void) | null>(null);

/** Inside the demo: a function that explains why something needs an account. Outside it: null. */
export function useDemo() {
  return useContext(DemoContext);
}

export function DemoProvider({ children }: { children: ReactNode }) {
  const [reason, setReason] = useState<DemoReason | null>(null);
  // Kept while the sheet closes, so its words don't change on the way out
  const [shown, setShown] = useState<DemoReason>('generate');

  function ask(next: DemoReason) {
    setShown(next);
    setReason(next);
  }

  return (
    <SWRConfig value={{ use: [fromSnapshot], revalidateOnFocus: false, revalidateOnReconnect: false }}>
      <DemoContext value={ask}>
        {children}
        <DemoSheet open={reason !== null} onOpenChange={open => !open && setReason(null)} reason={shown} />
      </DemoContext>
    </SWRConfig>
  );
}
