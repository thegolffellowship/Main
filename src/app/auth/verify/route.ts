/**
 * =============================================================================
 * AUTH CALLBACK ROUTE (Server-Side)
 * =============================================================================
 * Handles authentication callbacks from Supabase magic links.
 *
 * WHY SERVER-SIDE?
 * - PKCE verifiers are stored in HTTP-only cookies by middleware
 * - Server routes can access these cookies (client components cannot)
 * - Works even when email is clicked from mobile email apps
 *
 * FLOW:
 * 1. User clicks magic link from email
 * 2. Supabase redirects to this route with 'code' parameter
 * 3. Server reads PKCE verifier from HTTP-only cookies
 * 4. Exchanges code for session using verifier
 * 5. Redirects to dashboard
 * =============================================================================
 */

import { createServerClient } from '@supabase/ssr';
import { cookies } from 'next/headers';
import { NextRequest, NextResponse } from 'next/server';
import type { CookieOptions } from '@supabase/ssr';

// CRITICAL: Force this route to be dynamic (not cached)
export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(request: NextRequest) {
  const requestUrl = new URL(request.url);
  const code = requestUrl.searchParams.get('code');
  const next = requestUrl.searchParams.get('redirect') || '/dashboard';

  console.log('[AUTH CALLBACK] Received request', {
    code: code ? 'present' : 'missing',
    next
  });

  if (!code) {
    console.error('[AUTH CALLBACK] No code parameter found');
    return NextResponse.redirect(
      new URL('/auth/sign-in?message=Invalid+authentication+link', requestUrl.origin)
    );
  }

  const cookieStore = await cookies();
  const response = NextResponse.redirect(new URL(next, requestUrl.origin));

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet: { name: string; value: string; options: CookieOptions }[]) {
          cookiesToSet.forEach(({ name, value, options }) => {
            response.cookies.set(name, value, options);
          });
        },
      },
    }
  );

  console.log('[AUTH CALLBACK] Exchanging code for session...');

  const { error } = await supabase.auth.exchangeCodeForSession(code);

  if (error) {
    console.error('[AUTH CALLBACK] Code exchange error:', error.message);
    return NextResponse.redirect(
      new URL(`/auth/sign-in?message=${encodeURIComponent(error.message)}`, requestUrl.origin)
    );
  }

  console.log('[AUTH CALLBACK] Session created successfully, redirecting to:', next);

  // Set cache control headers
  response.headers.set('Cache-Control', 'no-store, no-cache, must-revalidate');

  return response;
}
