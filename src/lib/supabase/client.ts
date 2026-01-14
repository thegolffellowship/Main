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
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        get(name: string) {
          // Get cookie value using browser's document.cookie
          const value = `; ${document.cookie}`;
          const parts = value.split(`; ${name}=`);
          if (parts.length === 2) return parts.pop()?.split(';').shift();
          return null;
        },
        set(name: string, value: string, options: any) {
          // Set cookie using browser's document.cookie
          let cookie = `${name}=${value}`;
          if (options?.maxAge) cookie += `; max-age=${options.maxAge}`;
          if (options?.path) cookie += `; path=${options.path}`;
          if (options?.domain) cookie += `; domain=${options.domain}`;
          if (options?.sameSite) cookie += `; samesite=${options.sameSite}`;
          if (options?.secure) cookie += '; secure';
          document.cookie = cookie;
        },
        remove(name: string, options: any) {
          // Remove cookie by setting expiry to past
          let cookie = `${name}=; max-age=0`;
          if (options?.path) cookie += `; path=${options.path}`;
          if (options?.domain) cookie += `; domain=${options.domain}`;
          document.cookie = cookie;
        },
      },
    }
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
