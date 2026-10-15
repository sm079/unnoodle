'use client';

import { useState, type FormEvent } from 'react';
import { api, messageOf } from '@/lib/api';
import { useAddToCache } from '@/lib/data';
import { cn } from '@/lib/utils';
import type { Project } from '@/lib/types';

interface NewProjectFormProps {
  onCreated: (project: Project) => void;
  onCancel: () => void;
  className?: string;
  inputClassName?: string;
}

/** A name field that creates a project on Enter. Escape, or leaving it empty, cancels. */
export function NewProjectForm({ onCreated, onCancel, className, inputClassName }: NewProjectFormProps) {
  const addToCache = useAddToCache();
  const [name, setName] = useState('');
  const [sending, setSending] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (sending) return;
    if (name.trim() === '') return onCancel();
    setSending(true);
    setProblem(null);
    try {
      const project = await api.createProject(name.trim());
      void addToCache.project(project);
      onCreated(project);
    } catch (error) {
      setProblem(messageOf(error));
      setSending(false);
    }
  }

  return (
    <form onSubmit={submit} aria-label="New project" className={cn('flex min-w-0 flex-col gap-1', className)}>
      <input
        // Opened by a tap on New project, so the name is what comes next
        autoFocus
        value={name}
        onChange={event => {
          setName(event.target.value);
          setProblem(null);
        }}
        onKeyDown={event => event.key === 'Escape' && onCancel()}
        onBlur={() => name.trim() === '' && !sending && onCancel()}
        aria-label="Project name"
        placeholder="Project name"
        maxLength={80}
        enterKeyHint="done"
        disabled={sending}
        // 16px at least, or iOS zooms the page in when the field gets focus
        className={cn(
          'w-full min-w-0 rounded-lg bg-white/[0.06] px-2.5 py-1.5 text-base outline-none placeholder:text-[#7c7d7f] focus-visible:ring-2 focus-visible:ring-white/20 disabled:opacity-60',
          inputClassName
        )}
      />
      {problem && (
        <p role="status" className="px-1 text-xs text-[#e8a33d]">
          {problem}
        </p>
      )}
    </form>
  );
}
