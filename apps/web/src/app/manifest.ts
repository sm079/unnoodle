import type { MetadataRoute } from 'next';

// Lets the app be added to a home screen and open without the browser's bars
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'unnoodle',
    short_name: 'unnoodle',
    description: 'AI pictures and videos from one prompt box, without the wiring.',
    start_url: '/generate',
    display: 'standalone',
    background_color: '#131416',
    theme_color: '#131416',
    icons: [
      { src: '/icon.svg', sizes: 'any', type: 'image/svg+xml' },
      { src: '/apple-icon', sizes: '180x180', type: 'image/png' }
    ]
  };
}
