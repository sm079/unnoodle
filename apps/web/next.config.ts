import type { NextConfig } from 'next';

// Read when the server starts (and baked in by next build)
const apiUrl = process.env.API_URL ?? 'http://127.0.0.1:8000';

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  experimental: {
    // Next forwards at most this much of a proxied request body (10 MB by default), and the API would then wait for
    // the rest until the proxy times out. Above the API's 50 MB upload limit, so it can refuse bigger files itself.
    proxyClientMaxBodySize: '60mb'
  },
  turbopack: {
    rules: {
      '*.css': {
        loaders: ['@tailwindcss/turbopack'],
        as: '*.css'
      }
    }
  },
  // The browser only ever talks to this app, which passes API calls and stored media through. A phone then needs
  // one address, and there's no cross-origin setup.
  rewrites: async () => [
    { source: '/api/:path*', destination: `${apiUrl}/:path*` },
    { source: '/media/:path*', destination: `${apiUrl}/media/:path*` }
  ]
};

export default nextConfig;
