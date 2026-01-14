'use client';

/**
 * =============================================================================
 * AUTH VERIFICATION PAGE - Client Component
 * =============================================================================
 * This client component handles the auth callback from magic links.
 *
 * WHY CLIENT-SIDE?
 * - The PKCE code verifier is stored in browser cookies
 * - Browser client can access its own stored verifier
 * - Avoids server/client cookie synchronization issues
 *
 * FLOW:
 * 1. User clicks magic link from email
 * 2. Supabase redirects to this page with token_hash/code in URL
 * 3. Browser client reads its stored PKCE verifier
 * 4. Verifies the token and creates session
 * 5. Redirects to dashboard
 * =============================================================================
 */

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { createClient } from '@/lib/supabase/client';

function AuthVerifyContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [isVerifying, setIsVerifying] = useState(true);

  useEffect(() => {
    const handleCallback = async () => {
      try {
        const supabase = createClient();

        // Check if we have a token_hash (OTP flow)
        const tokenHash = searchParams.get('token_hash');
        const type = searchParams.get('type');

        if (tokenHash && type) {
          // Verify the OTP token
          const { error: verifyError } = await supabase.auth.verifyOtp({
            token_hash: tokenHash,
            type: type as any,
          });

          if (verifyError) {
            console.error('OTP verification error:', verifyError);
            setError(verifyError.message);
            setIsVerifying(false);
            return;
          }
        }

        // Check for session (works for both OTP and PKCE flows)
        const { data: { session }, error: sessionError } = await supabase.auth.getSession();

        if (sessionError) {
          console.error('Session error:', sessionError);
          setError(sessionError.message);
          setIsVerifying(false);
          return;
        }

        if (session) {
          // Success! Redirect to intended destination or dashboard
          const redirectTo = searchParams.get('redirect') || '/dashboard';
          router.push(redirectTo);
          router.refresh();
        } else {
          // Check URL hash for tokens (implicit flow)
          const hashParams = new URLSearchParams(window.location.hash.substring(1));
          const accessToken = hashParams.get('access_token');

          if (accessToken) {
            // Session should be set automatically, just redirect
            const redirectTo = searchParams.get('redirect') || '/dashboard';
            router.push(redirectTo);
            router.refresh();
          } else {
            setError('No valid session found. Please try logging in again.');
            setIsVerifying(false);
          }
        }
      } catch (err: any) {
        console.error('Verification error:', err);
        setError(err.message || 'An unexpected error occurred');
        setIsVerifying(false);
      }
    };

    handleCallback();
  }, [router, searchParams]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-neutral-50">
        <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-8">
          <div className="text-center">
            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg
                className="w-8 h-8 text-red-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
            </div>
            <h2 className="text-xl font-semibold text-neutral-900 mb-2">
              Verification Failed
            </h2>
            <p className="text-neutral-600 mb-6">{error}</p>
            <a
              href="/auth/sign-in"
              className="btn-primary inline-block"
            >
              Back to Sign In
            </a>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-neutral-50">
      <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-8">
        <div className="text-center">
          <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg
              className="animate-spin h-8 w-8 text-primary-600"
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
          </div>
          <h2 className="text-xl font-semibold text-neutral-900 mb-2">
            Verifying your login...
          </h2>
          <p className="text-neutral-600">
            Please wait while we confirm your identity.
          </p>
        </div>
      </div>
    </div>
  );
}

export default function AuthVerifyPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-neutral-50">
        <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-8">
          <div className="text-center">
            <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg
                className="animate-spin h-8 w-8 text-primary-600"
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
            </div>
            <h2 className="text-xl font-semibold text-neutral-900 mb-2">
              Loading...
            </h2>
          </div>
        </div>
      </div>
    }>
      <AuthVerifyContent />
    </Suspense>
  );
}
