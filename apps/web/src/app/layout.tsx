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
  description: 'Hand-picked ComfyUI workflows behind one prompt box.',
  // Chrome on Android leaves text at its default size whatever the phone's text size setting is, unless the page opts
  // in to scaling the root font size by it. Sizes in the app are in rem, so the layout grows along with the text.
  other: { 'text-scale': 'scale' }
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  // Draw under the home indicator and the rounded corners; the edges that need it pad by env(safe-area-inset-*)
  viewportFit: 'cover',
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
