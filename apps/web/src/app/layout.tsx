import type { Metadata, Viewport } from 'next';
import { Archivo, Geist, Geist_Mono } from 'next/font/google';
import { MotionProvider } from '@/components/motion-provider';
import { cn } from '@/lib/utils';
import './globals.css';

const geist = Geist({ subsets: ['latin'], variable: '--font-sans' });
const geistMono = Geist_Mono({ subsets: ['latin'], variable: '--font-mono' });
// Headlines and the generate button use a narrowed width
const archivo = Archivo({ subsets: ['latin'], axes: ['wdth'], variable: '--font-display' });

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
    <html lang="en" className={cn('dark', geist.variable, geistMono.variable, archivo.variable)}>
      <body className="antialiased">
        <MotionProvider>{children}</MotionProvider>
      </body>
    </html>
  );
}
