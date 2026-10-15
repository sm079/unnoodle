import Image from 'next/image';
import { FolderIcon, LibraryIcon, PlayIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet';
import type { Asset, Project } from '@/lib/types';

export function LibraryDrawer({ uploads, projects }: { uploads: Asset[]; projects: Project[] }) {
  return (
    <Sheet>
      <SheetTrigger render={<Button variant="ghost" size="icon" aria-label="Open library" />}>
        <LibraryIcon />
      </SheetTrigger>
      <SheetContent side="left" className="overflow-y-auto">
        <SheetHeader>
          <SheetTitle>Library</SheetTitle>
          <SheetDescription>Your uploads and projects.</SheetDescription>
        </SheetHeader>

        <section aria-labelledby="library-uploads" className="flex flex-col gap-2 px-4">
          <h3 id="library-uploads" className="text-xs font-medium text-muted-foreground">
            Uploads
          </h3>
          <ul className="grid grid-cols-3 gap-1">
            {uploads.map(asset => (
              <li key={asset.id} className="relative aspect-square overflow-hidden rounded-md bg-muted">
                <Image src={asset.thumbnail_url} alt="" fill sizes="100px" className="object-cover" />
                {asset.media_type === 'video' && (
                  <PlayIcon className="absolute top-1 left-1 size-3.5 text-white drop-shadow" aria-label="Video" />
                )}
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="library-projects" className="flex flex-col gap-1 px-4 pb-4">
          <h3 id="library-projects" className="text-xs font-medium text-muted-foreground">
            Projects
          </h3>
          <ul>
            {projects.map(project => (
              <li key={project.id} className="flex items-center gap-2 py-2">
                <FolderIcon className="size-4 text-muted-foreground" />
                {project.name}
              </li>
            ))}
          </ul>
        </section>
      </SheetContent>
    </Sheet>
  );
}
