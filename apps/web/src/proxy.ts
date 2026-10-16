import { NextResponse, type NextRequest } from 'next/server';

// Set by the API when someone signs in (apps/api/app/accounts.py)
const SESSION_COOKIE = 'unnoodle_session';

/**
 * Sends someone who isn't signed in to sign in before the app loads, rather than after its first call to the API.
 * Only whether there is a cookie is checked here: the API decides whether it's still good, and a call it refuses
 * sends the person to sign in too (lib/api.ts).
 */
export function proxy(request: NextRequest) {
  if (request.cookies.has(SESSION_COOKIE)) return NextResponse.next();
  const url = new URL('/sign-in', request.url);
  url.searchParams.set('next', request.nextUrl.pathname + request.nextUrl.search);
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ['/generate/:path*']
};
