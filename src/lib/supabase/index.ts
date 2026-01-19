/**
 * =============================================================================
 * SUPABASE EXPORTS
 * =============================================================================
 * Import Supabase utilities from '@/lib/supabase'
 * =============================================================================
 */

export { createClient, getClient } from './client';
export { createServerSupabaseClient, createAdminClient } from './server';
export { updateSession } from './middleware';
