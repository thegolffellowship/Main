/**
 * =============================================================================
 * STRIPE SERVER - Server-Side Operations
 * =============================================================================
 * All Stripe operations that involve your secret key happen here.
 *
 * IMPORTANT: Never import this file in client-side code!
 * The secret key must never be exposed to the browser.
 *
 * WHAT CAN WE DO HERE?
 * - Create customers (when someone signs up)
 * - Create payment intents (start a payment)
 * - Save payment methods (for one-click checkout)
 * - Process refunds
 * - Handle webhooks (Stripe telling us about events)
 * =============================================================================
 */

import Stripe from 'stripe';

/**
 * Server-side Stripe client.
 * Use this for all Stripe API calls from the server.
 */
export const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, {
  apiVersion: '2024-12-18.acacia',
  typescript: true,
});

/**
 * Create a Stripe customer for a new member.
 * We store the customer ID so we can:
 * - Save their payment methods
 * - Look up their payment history
 * - Process refunds easily
 */
export async function createStripeCustomer(params: {
  email: string;
  name: string;
  memberId: string;
}): Promise<Stripe.Customer> {
  return stripe.customers.create({
    email: params.email,
    name: params.name,
    metadata: {
      tgf_member_id: params.memberId,
    },
  });
}

/**
 * Create a payment intent for a one-time payment.
 *
 * WHAT IS A PAYMENT INTENT?
 * It's Stripe's way of tracking a payment from start to finish.
 * 1. You create it (specifying amount)
 * 2. Customer enters card details
 * 3. Stripe confirms the payment
 * 4. You get notified via webhook
 *
 * @param amount - Amount in DOLLARS (we convert to cents for Stripe)
 */
export async function createPaymentIntent(params: {
  amount: number;
  customerId?: string;
  description: string;
  metadata?: Record<string, string>;
}): Promise<Stripe.PaymentIntent> {
  return stripe.paymentIntents.create({
    // Stripe uses cents, not dollars
    amount: Math.round(params.amount * 100),
    currency: 'usd',
    customer: params.customerId,
    description: params.description,
    metadata: params.metadata || {},
    // Enable automatic payment methods for best conversion
    automatic_payment_methods: {
      enabled: true,
    },
  });
}

/**
 * Retrieve a payment intent to check its status.
 */
export async function getPaymentIntent(
  paymentIntentId: string
): Promise<Stripe.PaymentIntent> {
  return stripe.paymentIntents.retrieve(paymentIntentId);
}

/**
 * Create a refund for a payment.
 */
export async function createRefund(params: {
  paymentIntentId: string;
  amount?: number; // If not specified, full refund
  reason?: 'duplicate' | 'fraudulent' | 'requested_by_customer';
}): Promise<Stripe.Refund> {
  return stripe.refunds.create({
    payment_intent: params.paymentIntentId,
    // Convert dollars to cents if amount specified
    amount: params.amount ? Math.round(params.amount * 100) : undefined,
    reason: params.reason || 'requested_by_customer',
  });
}

/**
 * Get a customer's saved payment methods.
 */
export async function getCustomerPaymentMethods(
  customerId: string
): Promise<Stripe.PaymentMethod[]> {
  const paymentMethods = await stripe.paymentMethods.list({
    customer: customerId,
    type: 'card',
  });
  return paymentMethods.data;
}

/**
 * Save a payment method to a customer for future use.
 */
export async function attachPaymentMethod(params: {
  paymentMethodId: string;
  customerId: string;
}): Promise<Stripe.PaymentMethod> {
  return stripe.paymentMethods.attach(params.paymentMethodId, {
    customer: params.customerId,
  });
}

/**
 * Set the default payment method for a customer.
 */
export async function setDefaultPaymentMethod(params: {
  customerId: string;
  paymentMethodId: string;
}): Promise<Stripe.Customer> {
  return stripe.customers.update(params.customerId, {
    invoice_settings: {
      default_payment_method: params.paymentMethodId,
    },
  });
}

/**
 * Create a checkout session for a simple payment flow.
 * This redirects the customer to Stripe's hosted checkout page.
 *
 * WHEN TO USE THIS?
 * - Simple one-time payments
 * - When you don't need a custom payment form
 * - Fastest way to get payments working
 */
export async function createCheckoutSession(params: {
  customerId?: string;
  customerEmail?: string;
  lineItems: Array<{
    name: string;
    description?: string;
    amount: number; // In dollars
    quantity: number;
  }>;
  successUrl: string;
  cancelUrl: string;
  metadata?: Record<string, string>;
}): Promise<Stripe.Checkout.Session> {
  return stripe.checkout.sessions.create({
    customer: params.customerId,
    customer_email: params.customerId ? undefined : params.customerEmail,
    mode: 'payment',
    line_items: params.lineItems.map((item) => ({
      price_data: {
        currency: 'usd',
        unit_amount: Math.round(item.amount * 100),
        product_data: {
          name: item.name,
          description: item.description,
        },
      },
      quantity: item.quantity,
    })),
    success_url: params.successUrl,
    cancel_url: params.cancelUrl,
    metadata: params.metadata || {},
  });
}

/**
 * Verify a webhook signature.
 * This ensures the webhook is actually from Stripe.
 */
export function verifyWebhookSignature(
  payload: string | Buffer,
  signature: string
): Stripe.Event {
  return stripe.webhooks.constructEvent(
    payload,
    signature,
    process.env.STRIPE_WEBHOOK_SECRET!
  );
}
