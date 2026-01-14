/**
 * =============================================================================
 * NEXT.JS MIDDLEWARE
 * =============================================================================
 * This runs BEFORE every page request. It:
 * 1. Refreshes the user's session if needed
 * 2. Protects certain routes from unauthorized access
 *
 * PROTECTED ROUTES:
 * - /dashboard/* - Requires login
 * - /manager/*   - Requires chapter manager role
 * - /admin/*     - Requires admin role
 *
 * PUBLIC ROUTES:
 * - /            - Home page
 * - /events/*    - Event listings and details
 * - /auth/*      - Login, signup, etc.
 * =============================================================================
 */

import { NextResponse, type NextRequest } from 'next/server';
import { updateSession } from '@/lib/supabase/middleware';

export async function middleware(request: NextRequest) {
  const { supabaseResponse, user } = await updateSession(request);

  const pathname = request.nextUrl.pathname;

  // Routes that require authentication
  const protectedRoutes = ['/dashboard', '/manager', '/admin'];
  const isProtectedRoute = protectedRoutes.some((route) =>
    pathname.startsWith(route)
  );

  // If accessing protected route without login, redirect to sign-in
  if (isProtectedRoute && !user) {
    const loginUrl = new URL('/auth/sign-in', request.url);
    loginUrl.searchParams.set('redirect', pathname);
    loginUrl.searchParams.set('message', 'Please log in to continue');
    return NextResponse.redirect(loginUrl);
  }

  // If logged in and trying to access auth pages (except verify callback), redirect to dashboard
  if (user && pathname.startsWith('/auth/') && !pathname.startsWith('/auth/verify')) {
    return NextResponse.redirect(new URL('/dashboard', request.url));
  }

  return supabaseResponse;
}

// Configure which routes the middleware runs on
export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public folder files (images, etc.)
     */
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
};
