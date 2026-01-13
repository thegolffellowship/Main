/**
 * =============================================================================
 * STRIPE CLIENT - Browser/Client-Side
 * =============================================================================
 * Use this for Stripe Elements and checkout in the browser.
 *
 * WHAT IS STRIPE?
 * Stripe is a payment processing service. It handles:
 * - Credit card payments
 * - Saved payment methods
 * - Subscriptions (if we add them later)
 * - Refunds
 *
 * KEY CONCEPT: Stripe has TWO parts:
 * 1. Client-side (this file) - Shows payment forms, collects card info
 * 2. Server-side (server.ts) - Actually charges cards, creates customers
 *
 * Card numbers NEVER touch your server - Stripe handles that securely.
 * =============================================================================
 */

import { loadStripe, type Stripe } from '@stripe/stripe-js';

/**
 * Stripe Promise - loads the Stripe library once.
 * This is used by Stripe Elements components.
 */
let stripePromise: Promise<Stripe | null> | null = null;

export function getStripe(): Promise<Stripe | null> {
  if (!stripePromise) {
    stripePromise = loadStripe(
      process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY!
    );
  }
  return stripePromise;
}
