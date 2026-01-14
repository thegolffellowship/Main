/**
 * =============================================================================
 * AUTH CALLBACK ROUTE
 * =============================================================================
 * This handles authentication callbacks from Supabase.
 *
 * HANDLES TWO FLOWS:
 *
 * 1. OTP Flow (Magic Links, Email Confirmation, Password Reset):
 *    - User clicks link in email
 *    - Link contains token_hash and type parameters
 *    - We verify the OTP with Supabase
 *    - User is logged in and redirected
 *
 * 2. OAuth/PKCE Flow:
 *    - User authenticates with OAuth provider (Google, etc.)
 *    - Link contains code parameter
 *    - We exchange code for session
 *    - User is logged in and redirected
 * =============================================================================
 */

// CRITICAL: Force this route to be dynamic (not cached)
export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

import { createServerSupabaseClient } from '@/lib/supabase/server';
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export async function GET(request: NextRequest) {
  const requestUrl = new URL(request.url);
  const tokenHash = requestUrl.searchParams.get('token_hash');
  const type = requestUrl.searchParams.get('type');
  const code = requestUrl.searchParams.get('code');
  const redirectTo = requestUrl.searchParams.get('redirect');

  // Debug logging - Build timestamp: 2026-01-14 21:00
  console.log('[AUTH CALLBACK] Params:', { tokenHash: !!tokenHash, type, code: !!code });

  const supabase = await createServerSupabaseClient();

  // Handle OTP/Magic Link flow (email confirmation, magic links, password reset)
  if (tokenHash && type) {
    const { error } = await supabase.auth.verifyOtp({
      token_hash: tokenHash,
      type: type as any,
    });

    if (!error) {
      // Successfully verified! Redirect to dashboard or specified page
      const destination = redirectTo || '/dashboard';
      const response = NextResponse.redirect(new URL(destination, requestUrl.origin));
      response.headers.set('Cache-Control', 'no-store, no-cache, must-revalidate');
      return response;
    }

    console.error('OTP verification error:', error);
    return NextResponse.redirect(
      new URL(`/auth/login?message=${encodeURIComponent(error.message)}`, requestUrl.origin)
    );
  }

  // Handle OAuth/PKCE flow
  if (code) {
    const { error } = await supabase.auth.exchangeCodeForSession(code);

    if (!error) {
      // Successfully logged in! Redirect to dashboard or specified page
      const destination = redirectTo || '/dashboard';
      const response = NextResponse.redirect(new URL(destination, requestUrl.origin));
      response.headers.set('Cache-Control', 'no-store, no-cache, must-revalidate');
      return response;
    }

    console.error('Code exchange error:', error);
    return NextResponse.redirect(
      new URL(`/auth/login?message=${encodeURIComponent(error.message)}`, requestUrl.origin)
    );
  }

  // If no valid parameters, redirect to login
  return NextResponse.redirect(
    new URL('/auth/login?message=Invalid authentication link. Please request a new one.', requestUrl.origin)
  );
}
