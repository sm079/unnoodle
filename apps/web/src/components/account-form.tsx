'use client';

import { useEffect, useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { BrandMark } from '@/components/brand-mark';
import { ApiError, api, messageOf } from '@/lib/api';

// The API's minimum, checked here too so a short one is caught before sending
const MIN_PASSWORD = 8;
// The health check goes through the proxy to the API, which takes up to a few seconds when it's up
const HEALTH_TIMEOUT_MS = 6000;

const copy = {
  'sign-in': {
    title: 'Sign in',
    submit: 'Sign in',
    sending: 'Signing in…',
    other: { prompt: 'New here?', label: 'Make an account', href: '/sign-up' },
    passwordAutocomplete: 'current-password'
  },
  'sign-up': {
    title: 'Make an account',
    submit: 'Make account',
    sending: 'Making your account…',
    other: { prompt: 'Have an account?', label: 'Sign in', href: '/sign-in' },
    passwordAutocomplete: 'new-password'
  }
} as const;

/** Email and password, to sign in or to make an account, then on to where the person was going. */
export function AccountForm({ mode }: { mode: keyof typeof copy }) {
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [sending, setSending] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const invites = useInvites(mode === 'sign-up');
  const [closed, setClosed] = useState(false);
  const text = copy[mode];
  // Only a path in this app, so a link can't send someone elsewhere after they sign in
  const requested = params.get('next');
  const next = requested?.startsWith('/') && !requested.startsWith('//') ? requested : '/generate';

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (sending) return;
    if (mode === 'sign-up' && password.length < MIN_PASSWORD) {
      return setProblem(`Use at least ${MIN_PASSWORD} characters for your password`);
    }
    setSending(true);
    setProblem(null);
    try {
      await (mode === 'sign-in' ? api.signIn(email, password) : api.signUp(email, password));
      router.replace(next);
    } catch (error) {
      // The API went away after the page checked it
      if (mode === 'sign-up' && error instanceof ApiError && (error.status === 0 || error.status >= 500)) setClosed(true);
      setProblem(messageOf(error));
      setSending(false);
    }
  }

  if (mode === 'sign-up' && (closed || invites === 'closed')) return <InvitesClosed />;

  const otherHref = requested ? `${text.other.href}?next=${encodeURIComponent(requested)}` : text.other.href;
  const field =
    'w-full rounded-xl bg-white/[0.06] px-3.5 py-3 text-base outline-none placeholder:text-[#7c7d7f] focus-visible:ring-2 focus-visible:ring-white/20 disabled:opacity-60';

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-sm flex-col justify-center px-4 py-10">
      <Link href="/" aria-label="unnoodle home" className="mb-8 self-start">
        <BrandMark />
      </Link>
      <h1 className={title}>{text.title}</h1>
      <form
        onSubmit={submit}
        aria-label={text.title}
        aria-busy={invites === 'checking'}
        className={`mt-6 flex flex-col gap-3 transition-opacity duration-300 ${invites === 'checking' ? 'pointer-events-none opacity-0' : ''}`}
      >
        <label className="flex flex-col gap-1.5 text-sm text-[#a0a1a3]">
          Email
          <input
            type="email"
            name="email"
            autoComplete="email"
            required
            value={email}
            onChange={event => setEmail(event.target.value)}
            disabled={sending}
            className={field}
          />
        </label>
        <label className="flex flex-col gap-1.5 text-sm text-[#a0a1a3]">
          Password
          <input
            type="password"
            name="password"
            autoComplete={text.passwordAutocomplete}
            required
            value={password}
            onChange={event => setPassword(event.target.value)}
            disabled={sending}
            className={field}
          />
        </label>
        {problem && (
          <p role="alert" className="text-sm text-[#e8a33d]">
            {problem}
          </p>
        )}
        <button
          type="submit"
          disabled={sending}
          className="mt-2 rounded-xl bg-brand px-4 py-3 font-medium text-white transition-opacity disabled:opacity-60"
        >
          {sending ? text.sending : text.submit}
        </button>
      </form>
      <p className="mt-6 text-sm text-[#828282]">
        {text.other.prompt}{' '}
        <Link href={otherHref} className="text-white underline underline-offset-4">
          {text.other.label}
        </Link>
      </p>
    </main>
  );
}

const title = 'font-display text-3xl font-bold tracking-[-0.01em] uppercase font-stretch-[86%]';

/**
 * Whether new accounts can be made: only while the API answers. The web app stays up when the API's machine is off,
 * and a closed door reads better than a form that fails once it's filled in.
 */
function useInvites(check: boolean): 'checking' | 'open' | 'closed' {
  const [state, setState] = useState<'checking' | 'open' | 'closed'>(check ? 'checking' : 'open');
  useEffect(() => {
    if (!check) return;
    let left = false;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS);
    fetch('/api/health', { signal: controller.signal, cache: 'no-store' })
      .then(response => !left && setState(response.ok ? 'open' : 'closed'))
      // Unreachable, or no answer in time
      .catch(() => !left && setState('closed'));
    return () => {
      left = true;
      clearTimeout(timer);
      controller.abort();
    };
  }, [check]);
  return state;
}

function InvitesClosed() {
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-sm flex-col justify-center px-4 py-10">
      <Link href="/" aria-label="unnoodle home" className="mb-8 self-start">
        <BrandMark />
      </Link>
      <h1 className={title}>Invites closed</h1>
      <p className="mt-4 text-[#a0a1a3]">unnoodle lets people in a few at a time, and this round is full.</p>
      <p className="mt-2 text-[#a0a1a3]">The studio and everything made in it are open to look around.</p>
      <Link href="/demo" className="mt-8 rounded-xl bg-brand px-4 py-3 text-center font-medium text-white">
        Look around
      </Link>
      <p className="mt-6 text-sm text-[#828282]">
        Have an account?{' '}
        <Link href="/sign-in" className="text-white underline underline-offset-4">
          Sign in
        </Link>
      </p>
    </main>
  );
}
