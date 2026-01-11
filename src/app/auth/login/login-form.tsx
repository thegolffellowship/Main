'use client';

/**
 * =============================================================================
 * LOGIN FORM COMPONENT
 * =============================================================================
 * Client component that handles the login form logic.
 *
 * TWO LOGIN OPTIONS:
 * 1. Magic Link - Enter email, receive link, click to login
 * 2. Password - Enter email + password (if they have one)
 *
 * We default to magic link because it's easier for users.
 * =============================================================================
 */

import { useState } from 'react';
import { createClient } from '@/lib/supabase/client';
import { useRouter } from 'next/navigation';

interface LoginFormProps {
  redirectTo?: string;
}

export function LoginForm({ redirectTo }: LoginFormProps) {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [magicLinkSent, setMagicLinkSent] = useState(false);

  // Login with magic link
  async function handleMagicLink(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      const supabase = createClient();
      const { error } = await supabase.auth.signInWithOtp({
        email,
        options: {
          emailRedirectTo: `${window.location.origin}/auth/callback${
            redirectTo ? `?redirect=${redirectTo}` : ''
          }`,
        },
      });

      if (error) throw error;

      setMagicLinkSent(true);
    } catch (err: any) {
      setError(err.message || 'Failed to send magic link');
    } finally {
      setIsLoading(false);
    }
  }

  // Login with password
  async function handlePasswordLogin(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      const supabase = createClient();
      const { error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (error) throw error;

      // Redirect after successful login
      router.push(redirectTo || '/dashboard');
      router.refresh();
    } catch (err: any) {
      setError(err.message || 'Invalid email or password');
    } finally {
      setIsLoading(false);
    }
  }

  // Show success message after magic link sent
  if (magicLinkSent) {
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
              d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
            />
          </svg>
        </div>
        <h3 className="text-lg font-semibold text-neutral-900 mb-2">
          Check your email
        </h3>
        <p className="text-neutral-600 mb-4">
          We sent a login link to <strong>{email}</strong>
        </p>
        <p className="text-sm text-neutral-500">
          Click the link in the email to sign in. The link expires in 1 hour.
        </p>
        <button
          onClick={() => setMagicLinkSent(false)}
          className="mt-4 text-sm text-primary-600 hover:text-primary-500"
        >
          Use a different email
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={showPassword ? handlePasswordLogin : handleMagicLink}>
      {/* Error message */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Email field */}
      <div className="mb-4">
        <label htmlFor="email" className="label">
          Email address
        </label>
        <input
          id="email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          autoComplete="email"
          className="input"
          placeholder="you@example.com"
        />
      </div>

      {/* Password field (only shown if toggled) */}
      {showPassword && (
        <div className="mb-4">
          <label htmlFor="password" className="label">
            Password
          </label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
            className="input"
            placeholder="Enter your password"
          />
        </div>
      )}

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
            {showPassword ? 'Signing in...' : 'Sending link...'}
          </span>
        ) : showPassword ? (
          'Sign in'
        ) : (
          'Send magic link'
        )}
      </button>

      {/* Toggle between magic link and password */}
      <div className="mt-4 text-center">
        <button
          type="button"
          onClick={() => setShowPassword(!showPassword)}
          className="text-sm text-neutral-600 hover:text-neutral-900"
        >
          {showPassword
            ? 'Use magic link instead'
            : 'Sign in with password instead'}
        </button>
      </div>
    </form>
  );
}
