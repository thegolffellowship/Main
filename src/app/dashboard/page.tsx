/**
 * =============================================================================
 * MEMBER DASHBOARD
 * =============================================================================
 * The main hub for logged-in members.
 * Shows their profile, upcoming events, wallet balance, etc.
 * =============================================================================
 */

import { requireAuth } from '@/lib/auth';
import { createServerSupabaseClient } from '@/lib/supabase/server';
import Link from 'next/link';
import { formatCurrency, formatDate } from '@/lib/utils';

export const metadata = {
  title: 'Dashboard',
};

export default async function DashboardPage() {
  // This redirects to login if not authenticated
  const member = await requireAuth();
  const supabase = await createServerSupabaseClient();

  // Get upcoming registrations
  const { data: upcomingRegistrations } = await supabase
    .from('registrations')
    .select(`
      *,
      event:events(*)
    `)
    .eq('member_id', member.id)
    .is('cancelled_at', null)
    .gte('event.event_date', new Date().toISOString().split('T')[0])
    .order('event.event_date', { ascending: true })
    .limit(5);

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Header */}
      <header className="bg-white border-b border-neutral-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <Link href="/" className="text-xl font-bold text-primary-600">
              The Golf Fellowship
            </Link>
            <div className="flex items-center gap-4">
              <span className="text-neutral-600">
                {member.first_name} {member.last_name}
              </span>
              <form action="/auth/signout" method="post">
                <button type="submit" className="btn-ghost text-sm">
                  Log Out
                </button>
              </form>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Welcome Section */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-neutral-900">
            Welcome back, {member.first_name}!
          </h1>
          <p className="text-neutral-600 mt-1">
            Here&apos;s what&apos;s happening with your TGF account.
          </p>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {/* Membership Status */}
          <div className="card p-6">
            <h3 className="text-sm font-medium text-neutral-500 uppercase tracking-wide">
              Membership
            </h3>
            <div className="mt-2">
              {member.status === 'active_member' ? (
                <>
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-sm font-medium bg-primary-100 text-primary-800">
                    Active Member
                  </span>
                  {member.membership_expires_at && (
                    <p className="text-sm text-neutral-500 mt-2">
                      Expires: {formatDate(member.membership_expires_at, 'short')}
                    </p>
                  )}
                </>
              ) : (
                <>
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-sm font-medium bg-neutral-100 text-neutral-800">
                    {member.status === 'guest' ? 'Guest' : 'Not a Member'}
                  </span>
                  <Link
                    href="/membership"
                    className="block text-sm text-primary-600 hover:text-primary-500 mt-2"
                  >
                    Become a member →
                  </Link>
                </>
              )}
            </div>
          </div>

          {/* Wallet Balance */}
          <div className="card p-6">
            <h3 className="text-sm font-medium text-neutral-500 uppercase tracking-wide">
              Wallet Balance
            </h3>
            <p className="text-3xl font-bold text-neutral-900 mt-2">
              {formatCurrency(member.wallet_balance)}
            </p>
            <Link
              href="/dashboard/wallet"
              className="text-sm text-primary-600 hover:text-primary-500 mt-2 block"
            >
              Add funds →
            </Link>
          </div>

          {/* Events Played */}
          <div className="card p-6">
            <h3 className="text-sm font-medium text-neutral-500 uppercase tracking-wide">
              Events Played
            </h3>
            <p className="text-3xl font-bold text-neutral-900 mt-2">
              {member.events_played_count}
            </p>
            <Link
              href="/dashboard/history"
              className="text-sm text-primary-600 hover:text-primary-500 mt-2 block"
            >
              View history →
            </Link>
          </div>
        </div>

        {/* Upcoming Events */}
        <div className="card">
          <div className="px-6 py-4 border-b border-neutral-200 flex justify-between items-center">
            <h2 className="text-lg font-semibold">Upcoming Events</h2>
            <Link
              href="/events"
              className="text-sm text-primary-600 hover:text-primary-500"
            >
              Browse all events →
            </Link>
          </div>
          <div className="divide-y divide-neutral-200">
            {upcomingRegistrations && upcomingRegistrations.length > 0 ? (
              upcomingRegistrations.map((reg: any) => (
                <div key={reg.id} className="px-6 py-4 flex justify-between items-center">
                  <div>
                    <h3 className="font-medium text-neutral-900">
                      {reg.event?.title}
                    </h3>
                    <p className="text-sm text-neutral-500">
                      {reg.event?.event_date && formatDate(reg.event.event_date, 'full')} • {reg.event?.course_name}
                    </p>
                  </div>
                  <div className="text-right">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        reg.payment_status === 'paid'
                          ? 'bg-primary-100 text-primary-800'
                          : 'bg-yellow-100 text-yellow-800'
                      }`}
                    >
                      {reg.payment_status === 'paid' ? 'Paid' : 'Pending'}
                    </span>
                  </div>
                </div>
              ))
            ) : (
              <div className="px-6 py-12 text-center">
                <p className="text-neutral-500 mb-4">
                  You don&apos;t have any upcoming events.
                </p>
                <Link href="/events" className="btn-primary">
                  Find an Event
                </Link>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
