/**
 * =============================================================================
 * UTILITY FUNCTIONS
 * =============================================================================
 * Common helper functions used throughout the app.
 * =============================================================================
 */

import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Combines CSS class names intelligently.
 * Handles Tailwind CSS conflicts properly.
 *
 * Example:
 * cn('bg-red-500', 'bg-blue-500') → 'bg-blue-500' (blue wins)
 * cn('p-4', isLarge && 'p-8') → 'p-8' if isLarge is true
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format a number as currency (USD).
 *
 * Example:
 * formatCurrency(45.5) → "$45.50"
 * formatCurrency(1000) → "$1,000.00"
 */
export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount);
}

/**
 * Format a date for display.
 *
 * Example:
 * formatDate('2025-03-15') → "Saturday, March 15, 2025"
 * formatDate('2025-03-15', 'short') → "Mar 15, 2025"
 */
export function formatDate(
  date: string | Date,
  format: 'full' | 'short' | 'medium' = 'medium'
): string {
  const d = typeof date === 'string' ? new Date(date) : date;

  const options: Intl.DateTimeFormatOptions = {
    full: { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' },
    medium: { year: 'numeric', month: 'long', day: 'numeric' },
    short: { year: 'numeric', month: 'short', day: 'numeric' },
  }[format];

  return new Intl.DateTimeFormat('en-US', options).format(d);
}

/**
 * Format a time for display.
 *
 * Example:
 * formatTime('14:30:00') → "2:30 PM"
 * formatTime('09:00:00') → "9:00 AM"
 */
export function formatTime(time: string): string {
  // Time format from database is "HH:MM:SS"
  const [hours, minutes] = time.split(':').map(Number);
  const date = new Date();
  date.setHours(hours, minutes);

  return new Intl.DateTimeFormat('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  }).format(date);
}

/**
 * Get a full name from first and last name.
 */
export function getFullName(firstName: string, lastName: string): string {
  return `${firstName} ${lastName}`.trim();
}

/**
 * Generate a unique ID (for client-side use).
 * For database IDs, always let Supabase generate them.
 */
export function generateId(): string {
  return crypto.randomUUID();
}

/**
 * Delay execution (useful for testing loading states).
 */
export function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Safely parse JSON without throwing.
 */
export function safeJsonParse<T>(json: string, fallback: T): T {
  try {
    return JSON.parse(json) as T;
  } catch {
    return fallback;
  }
}

/**
 * Check if a membership is expired.
 */
export function isMembershipExpired(expiresAt: string | null): boolean {
  if (!expiresAt) return true;
  return new Date(expiresAt) < new Date();
}

/**
 * Calculate days until a date.
 */
export function daysUntil(date: string | Date): number {
  const target = typeof date === 'string' ? new Date(date) : date;
  const now = new Date();
  const diffTime = target.getTime() - now.getTime();
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
}

/**
 * Truncate text with ellipsis.
 */
export function truncate(text: string, length: number): string {
  if (text.length <= length) return text;
  return text.slice(0, length).trim() + '...';
}
