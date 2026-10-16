import type { Metadata } from 'next';
import { Studio } from '@/components/studio';
import { DemoProvider } from '@/lib/demo';

export const metadata: Metadata = {
  title: 'Demo · unnoodle'
};

/** The studio on a copy of the demo project, open to anyone, without the API (lib/demo.tsx). */
export default function DemoPage() {
  return (
    <DemoProvider>
      <Studio />
    </DemoProvider>
  );
}
