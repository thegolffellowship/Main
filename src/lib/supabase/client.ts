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
          const cookies = document.cookie.split(';');
          for (const cookie of cookies) {
            const [cookieName, cookieValue] = cookie.trim().split('=');
            if (cookieName === name) {
              const value = decodeURIComponent(cookieValue);
              console.log(`🍪 GET cookie "${name}":`, value ? 'FOUND' : 'EMPTY');
              return value;
            }
          }
          console.log(`🍪 GET cookie "${name}": NOT FOUND`);
          console.log(`🍪 All cookies:`, document.cookie);
          return null;
        },
        set(name: string, value: string, options: any) {
          console.log(`🍪 SET cookie "${name}"`, { options });

          let cookieString = `${name}=${encodeURIComponent(value)}`;

          if (options?.maxAge) {
            cookieString += `; max-age=${options.maxAge}`;
          }

          // Always set path to root
          cookieString += `; path=/`;

          if (options?.domain) {
            cookieString += `; domain=${options.domain}`;
          }

          // CRITICAL: Use 'none' for cross-site navigation from email links
          // samesite=lax doesn't work when clicking links from email clients
          cookieString += `; samesite=none`;

          // samesite=none requires secure flag
          cookieString += `; secure`;

          console.log(`🍪 Cookie string:`, cookieString);
          document.cookie = cookieString;
        },
        remove(name: string, options: any) {
          console.log(`🍪 REMOVE cookie "${name}"`);
          this.set(name, '', { ...options, maxAge: 0 });
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
