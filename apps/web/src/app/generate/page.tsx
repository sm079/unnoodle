import type { Metadata } from 'next';
import { Composer } from '@/components/composer';
import { Gallery } from '@/components/gallery';
import { LibraryDrawer } from '@/components/library-drawer';
import { SettingsSheet } from '@/components/settings-sheet';
import { composerDrafts, generations, projects, uploads, workflows } from '@/lib/fixtures';

export const metadata: Metadata = {
  title: 'Generate · unnoodle'
};

// Renders the mock fixtures until the API serves real data
export default function GeneratePage() {
  return (
    <div className="flex h-dvh flex-col">
      <header className="flex shrink-0 items-center justify-between border-b px-2 py-1">
        <LibraryDrawer uploads={uploads} projects={projects} />
        <span className="text-sm font-medium">unnoodle</span>
        <SettingsSheet />
      </header>
      <main className="min-h-0 flex-1 overflow-y-auto">
        <Gallery generations={generations} />
      </main>
      <Composer drafts={composerDrafts} workflows={workflows} />
    </div>
  );
}
