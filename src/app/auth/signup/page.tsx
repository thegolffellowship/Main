/**
 * =============================================================================
 * SIGNUP PAGE
 * =============================================================================
 * New user registration.
 * Creates both an auth account and a member profile.
 * =============================================================================
 */

import Link from 'next/link';
import { SignupForm } from './signup-form';

export const metadata = {
  title: 'Sign Up',
  description: 'Join The Golf Fellowship',
};

export default function SignupPage() {
  return (
    <div className="min-h-screen bg-neutral-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        {/* Logo/Brand */}
        <Link href="/" className="flex justify-center">
          <span className="text-2xl font-bold text-primary-600">
            The Golf Fellowship
          </span>
        </Link>
        <h2 className="mt-6 text-center text-3xl font-bold text-neutral-900">
          Create your account
        </h2>
        <p className="mt-2 text-center text-sm text-neutral-600">
          Already have an account?{' '}
          <Link
            href="/auth/login"
            className="font-medium text-primary-600 hover:text-primary-500"
          >
            Log in
          </Link>
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-4 shadow-sm sm:rounded-xl sm:px-10 border border-neutral-200">
          <SignupForm />
        </div>
      </div>
    </div>
  );
}
