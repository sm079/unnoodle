import type { Metadata, Viewport } from 'next';
import { Geist } from 'next/font/google';
import { cn } from '@/lib/utils';
import './globals.css';

const geist = Geist({ subsets: ['latin'], variable: '--font-sans' });

export const metadata: Metadata = {
  title: 'unnoodle',
  description: 'Hand-picked ComfyUI workflows behind one prompt box.'
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  // Shrink the layout when the on-screen keyboard opens, so the docked composer stays visible
  interactiveWidget: 'resizes-content'
};

export default function RootLayout({ children }: LayoutProps<'/'>) {
  return (
    <html lang="en" className={cn('dark', geist.variable)}>
      <body className="antialiased">{children}</body>
    </html>
  );
}
