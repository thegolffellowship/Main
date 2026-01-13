/**
 * =============================================================================
 * STRIPE EXPORTS
 * =============================================================================
 * Import Stripe utilities from '@/lib/stripe'
 *
 * Client-side: import { getStripe } from '@/lib/stripe'
 * Server-side: import { stripe, createPaymentIntent } from '@/lib/stripe'
 * =============================================================================
 */

export { getStripe } from './client';
export {
  stripe,
  createStripeCustomer,
  createPaymentIntent,
  getPaymentIntent,
  createRefund,
  getCustomerPaymentMethods,
  attachPaymentMethod,
  setDefaultPaymentMethod,
  createCheckoutSession,
  verifyWebhookSignature,
} from './server';
