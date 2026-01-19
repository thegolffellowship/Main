/**
 * =============================================================================
 * SUPABASE CLIENT - Server-Side
 * =============================================================================
 * Use this when you need to access Supabase from:
 * - API routes
 * - Server Components
 * - Server Actions
 *
 * Server-side access is more secure because:
 * - Can use the "service role" key for admin operations
 * - User's session cookies are properly handled
 * - Sensitive operations happen on the server, not in the browser
 * =============================================================================
 */

import { createServerClient, type CookieOptions } from '@supabase/ssr';
import { cookies } from 'next/headers';

/**
 * Creates a Supabase client for use in Server Components and Route Handlers.
 * This automatically handles the user's session via cookies.
 *
 * Example in a Server Component:
 * ```
 * const supabase = await createServerSupabaseClient();
 * const { data: { user } } = await supabase.auth.getUser();
 * ```
 */
export async function createServerSupabaseClient() {
  const cookieStore = await cookies();

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet: { name: string; value: string; options: CookieOptions }[]) {
          try {
            cookiesToSet.forEach(({ name, value, options }) => {
              cookieStore.set(name, value, options);
            });
          } catch (error) {
            // This can happen when called from a Server Component
            // The `setAll` method was called from a Server Component.
            // This can be ignored if you have middleware refreshing sessions.
          }
        },
      },
    }
  );
}

/**
 * Creates a Supabase client with ADMIN privileges.
 * USE WITH CAUTION - this bypasses all Row Level Security!
 *
 * Only use this for:
 * - Admin operations that need full access
 * - Background jobs
 * - Webhook handlers
 *
 * Example:
 * ```
 * const supabase = createAdminClient();
 * // This can read/write ANY data, bypassing security rules
 * await supabase.from('members').update({ is_admin: true }).eq('id', someId);
 * ```
 */
export function createAdminClient() {
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,
    {
      cookies: {
        getAll() {
          return [];
        },
        setAll() {},
      },
      auth: {
        autoRefreshToken: false,
        persistSession: false,
      },
    }
  );
}
