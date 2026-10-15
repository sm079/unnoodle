import type { Metadata } from 'next';
import { AppShell } from '@/components/app-shell';
import { Composer } from '@/components/composer';
import { Hero } from '@/components/hero';
import { ProjectGrid } from '@/components/project-grid';
import { generations, projects, uploads, workflows } from '@/lib/fixtures';

export const metadata: Metadata = {
  title: 'Home · unnoodle'
};

const highlights = generations.flatMap(g => g.outputs).filter((asset, i, all) => all.findIndex(a => a.url === asset.url) === i);

// Renders the mock fixtures until the API serves real data
export default function HomePage() {
  return (
    <AppShell projects={projects}>
      <div className="flex flex-col gap-20 px-4 pt-6 pb-16 lg:gap-[92px] lg:px-[50px] lg:pt-[73px]">
        <div className="flex flex-col items-center gap-10 lg:gap-[55px]">
          <Hero assets={highlights} title="One prompt, any workflow" />
          {/* Arrives after the highlights are dealt and the headline lands */}
          <div className="w-full max-w-[1092px] animate-rise [--rise-blur:0px] [--rise-distance:18px] [animation-delay:250ms] [animation-duration:650ms]">
            <Composer workflows={workflows} library={uploads} />
          </div>
        </div>
        <ProjectGrid projects={projects} />
      </div>
    </AppShell>
  );
}
