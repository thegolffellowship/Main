/**
 * =============================================================================
 * AUTH CALLBACK ROUTE
 * =============================================================================
 * This handles the redirect after a user clicks a magic link.
 *
 * FLOW:
 * 1. User clicks magic link in email
 * 2. Link contains a code from Supabase
 * 3. This route exchanges the code for a session
 * 4. User is redirected to dashboard (or wherever they were going)
 * =============================================================================
 */

import { createServerSupabaseClient } from '@/lib/supabase/server';
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export async function GET(request: NextRequest) {
  const requestUrl = new URL(request.url);
  const code = requestUrl.searchParams.get('code');
  const redirectTo = requestUrl.searchParams.get('redirect');

  if (code) {
    const supabase = await createServerSupabaseClient();

    // Exchange the code for a session
    const { error } = await supabase.auth.exchangeCodeForSession(code);

    if (!error) {
      // Successfully logged in! Redirect to dashboard or specified page
      const destination = redirectTo || '/dashboard';
      return NextResponse.redirect(new URL(destination, requestUrl.origin));
    }
  }

  // If something went wrong, redirect to login with error message
  return NextResponse.redirect(
    new URL('/auth/login?message=There was an error logging in. Please try again.', requestUrl.origin)
  );
}
