import type { Metadata } from 'next';
import { Studio } from '@/components/studio';
import { generations, projects } from '@/lib/fixtures';

export const metadata: Metadata = {
  title: 'Home · unnoodle'
};

// The hero and the projects show mock data until the API has projects and enough real outputs to show off
const highlights = generations.flatMap(g => g.outputs).filter((asset, i, all) => all.findIndex(a => a.url === asset.url) === i);

export default function HomePage() {
  return <Studio highlights={highlights} projects={projects} />;
}
