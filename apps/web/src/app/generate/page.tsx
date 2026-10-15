import type { Metadata } from 'next';
import { Studio } from '@/components/studio';

export const metadata: Metadata = {
  title: 'Home · unnoodle'
};

export default function HomePage() {
  return <Studio />;
}
