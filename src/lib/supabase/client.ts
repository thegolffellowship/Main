/**
 * =============================================================================
 * SUPABASE CLIENT - Browser/Client-Side
 * =============================================================================
 * Use this when you need to access Supabase from React components.
 *
 * WHAT IS SUPABASE?
 * Think of Supabase as your "backend in a box." It provides:
 * - Database (PostgreSQL) - where all your data lives
 * - Authentication - login/logout/user management
 * - Storage - file uploads (profile photos, etc.)
 * - Real-time - live updates when data changes
 *
 * This file creates a "client" that knows how to talk to your Supabase project.
 * =============================================================================
 */

import { createBrowserClient } from '@supabase/ssr';

/**
 * Creates a Supabase client for use in the browser.
 * Call this in React components or client-side code.
 *
 * Example:
 * ```
 * const supabase = createClient();
 * const { data, error } = await supabase.from('events').select('*');
 * ```
 */
export function createClient() {
  // @supabase/ssr v0.8.0+ handles cookies automatically in the browser
  // No need to manually configure cookie handlers
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
}

/**
 * Singleton client for simple use cases.
 * This reuses the same client instance.
 */
let browserClient: ReturnType<typeof createClient> | null = null;

export function getClient() {
  if (!browserClient) {
    browserClient = createClient();
  }
  return browserClient;
}
