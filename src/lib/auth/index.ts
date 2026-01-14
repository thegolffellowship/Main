/**
 * =============================================================================
 * AUTHENTICATION UTILITIES
 * =============================================================================
 * Helper functions for user authentication and authorization.
 *
 * HOW AUTHENTICATION WORKS:
 * 1. User enters email (and optionally password)
 * 2. Supabase handles login (magic link or password)
 * 3. User gets a "session" (proof they're logged in)
 * 4. Every request includes this session automatically
 * 5. Server can check who the user is
 * =============================================================================
 */

import { createServerSupabaseClient } from '@/lib/supabase/server';
import { redirect } from 'next/navigation';
import type { Member } from '@/types';

/**
 * Get the current logged-in user's auth info.
 * Returns null if not logged in.
 */
export async function getAuthUser() {
  const supabase = await createServerSupabaseClient();
  const {
    data: { user },
    error,
  } = await supabase.auth.getUser();

  if (error || !user) {
    return null;
  }

  return user;
}

/**
 * Get the current logged-in member with their full profile.
 * Returns null if not logged in or member record not found.
 */
export async function getCurrentMember(): Promise<Member | null> {
  const supabase = await createServerSupabaseClient();

  // First get the auth user
  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser();

  if (authError || !user) {
    return null;
  }

  // Then get their member profile
  const { data: member, error: memberError } = await supabase
    .from('members')
    .select('*')
    .eq('auth_user_id', user.id)
    .single();

  if (memberError || !member) {
    return null;
  }

  return member as Member;
}

/**
 * Require authentication for a page.
 * Redirects to login if not authenticated.
 *
 * Usage in a Server Component:
 * ```
 * export default async function DashboardPage() {
 *   const member = await requireAuth();
 *   // If we get here, user is definitely logged in
 *   return <div>Welcome, {member.first_name}!</div>;
 * }
 * ```
 */
export async function requireAuth(): Promise<Member> {
  const member = await getCurrentMember();

  if (!member) {
    redirect('/auth/sign-in?message=Please log in to continue');
  }

  return member;
}

/**
 * Require the user to be an admin.
 * Redirects to home if not an admin.
 */
export async function requireAdmin(): Promise<Member> {
  const member = await requireAuth();

  if (!member.is_admin) {
    redirect('/?message=You do not have permission to access this page');
  }

  return member;
}

/**
 * Require the user to be a chapter manager.
 * Optionally require them to manage a specific chapter.
 */
export async function requireChapterManager(
  chapterId?: string
): Promise<Member> {
  const member = await requireAuth();

  // Admins can access everything
  if (member.is_admin) {
    return member;
  }

  if (!member.is_chapter_manager) {
    redirect('/?message=You do not have permission to access this page');
  }

  // If specific chapter required, check they manage it
  if (chapterId && !member.managed_chapter_ids.includes(chapterId)) {
    redirect('/?message=You do not have permission to manage this chapter');
  }

  return member;
}

/**
 * Check if the current user has an active membership.
 */
export async function hasActiveMembership(): Promise<boolean> {
  const member = await getCurrentMember();

  if (!member) return false;
  if (member.status !== 'active_member') return false;
  if (!member.membership_expires_at) return false;

  return new Date(member.membership_expires_at) > new Date();
}

/**
 * Check if email belongs to an existing member.
 * Used during registration to detect returning users.
 */
export async function checkEmailExists(email: string): Promise<{
  exists: boolean;
  member?: Member;
}> {
  const supabase = await createServerSupabaseClient();

  const { data: member, error } = await supabase
    .from('members')
    .select('*')
    .eq('email', email.toLowerCase().trim())
    .single();

  if (error || !member) {
    return { exists: false };
  }

  return { exists: true, member: member as Member };
}
