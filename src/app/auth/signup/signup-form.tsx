'use client';

/**
 * =============================================================================
 * SIGNUP FORM COMPONENT
 * =============================================================================
 * Handles new user registration.
 *
 * PROCESS:
 * 1. Collect email, name, phone
 * 2. Create auth account (with magic link or password)
 * 3. Create member profile in database
 * 4. Redirect to confirmation page
 * =============================================================================
 */

import { useState } from 'react';
import { createClient } from '@/lib/supabase/client';
import { useRouter } from 'next/navigation';

export function SignupForm() {
  const router = useRouter();
  const [formData, setFormData] = useState({
    firstName: '',
    lastName: '',
    email: '',
    phone: '',
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    setFormData((prev) => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      const supabase = createClient();

      // Sign up with magic link (no password required)
      const { data: authData, error: authError } = await supabase.auth.signInWithOtp({
        email: formData.email,
        options: {
          emailRedirectTo: `${window.location.origin}/auth/callback`,
          data: {
            first_name: formData.firstName,
            last_name: formData.lastName,
          },
        },
      });

      if (authError) throw authError;

      // Create member profile
      // Note: In production, this should be done in a database trigger or server action
      // to ensure it always happens after auth signup
      const { error: memberError } = await supabase.from('members').insert({
        email: formData.email.toLowerCase().trim(),
        first_name: formData.firstName.trim(),
        last_name: formData.lastName.trim(),
        phone: formData.phone.trim() || null,
        status: 'prospect',
      });

      // Member might already exist (returning guest), so we ignore duplicate errors
      if (memberError && !memberError.message.includes('duplicate')) {
        console.error('Member creation error:', memberError);
      }

      setSuccess(true);
    } catch (err: any) {
      setError(err.message || 'Failed to create account');
    } finally {
      setIsLoading(false);
    }
  }

  // Show success message
  if (success) {
    return (
      <div className="text-center py-4">
        <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg
            className="w-8 h-8 text-primary-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
        </div>
        <h3 className="text-lg font-semibold text-neutral-900 mb-2">
          Check your email
        </h3>
        <p className="text-neutral-600 mb-4">
          We sent a confirmation link to <strong>{formData.email}</strong>
        </p>
        <p className="text-sm text-neutral-500">
          Click the link in the email to complete your signup.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit}>
      {/* Error message */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Name fields */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <label htmlFor="firstName" className="label">
            First name
          </label>
          <input
            id="firstName"
            name="firstName"
            type="text"
            value={formData.firstName}
            onChange={handleChange}
            required
            autoComplete="given-name"
            className="input"
            placeholder="John"
          />
        </div>
        <div>
          <label htmlFor="lastName" className="label">
            Last name
          </label>
          <input
            id="lastName"
            name="lastName"
            type="text"
            value={formData.lastName}
            onChange={handleChange}
            required
            autoComplete="family-name"
            className="input"
            placeholder="Doe"
          />
        </div>
      </div>

      {/* Email field */}
      <div className="mb-4">
        <label htmlFor="email" className="label">
          Email address
        </label>
        <input
          id="email"
          name="email"
          type="email"
          value={formData.email}
          onChange={handleChange}
          required
          autoComplete="email"
          className="input"
          placeholder="you@example.com"
        />
      </div>

      {/* Phone field (optional) */}
      <div className="mb-6">
        <label htmlFor="phone" className="label">
          Phone number{' '}
          <span className="text-neutral-400 font-normal">(optional)</span>
        </label>
        <input
          id="phone"
          name="phone"
          type="tel"
          value={formData.phone}
          onChange={handleChange}
          autoComplete="tel"
          className="input"
          placeholder="(210) 555-0123"
        />
      </div>

      {/* Submit button */}
      <button
        type="submit"
        disabled={isLoading}
        className="btn-primary w-full"
      >
        {isLoading ? (
          <span className="flex items-center justify-center gap-2">
            <svg
              className="animate-spin h-5 w-5"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            Creating account...
          </span>
        ) : (
          'Create account'
        )}
      </button>

      {/* Terms */}
      <p className="mt-4 text-xs text-neutral-500 text-center">
        By signing up, you agree to our Terms of Service and Privacy Policy.
      </p>
    </form>
  );
}
