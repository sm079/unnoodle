import type { Metadata } from 'next';
import { Studio } from '@/components/studio';
import { generations } from '@/lib/fixtures';

export const metadata: Metadata = {
  title: 'Home · unnoodle'
};

// The hero shows mock data until there are enough real outputs to show off
const highlights = generations.flatMap(g => g.outputs).filter((asset, i, all) => all.findIndex(a => a.url === asset.url) === i);

export default function HomePage() {
  return <Studio highlights={highlights} />;
}
