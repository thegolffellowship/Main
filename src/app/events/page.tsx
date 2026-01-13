/**
 * =============================================================================
 * EVENTS LIST PAGE
 * =============================================================================
 * Public page showing all upcoming events.
 * Visitors can browse without logging in.
 * =============================================================================
 */

import { createServerSupabaseClient } from '@/lib/supabase/server';
import Link from 'next/link';
import { formatDate, formatTime, formatCurrency } from '@/lib/utils';
import type { EventWithChapter } from '@/types';

export const metadata = {
  title: 'Events',
  description: 'Browse upcoming Golf Fellowship events in San Antonio and Austin',
};

export default async function EventsPage({
  searchParams,
}: {
  searchParams: { chapter?: string };
}) {
  const supabase = await createServerSupabaseClient();

  // Build query
  let query = supabase
    .from('events')
    .select(`
      *,
      chapter:chapters(*)
    `)
    .in('status', ['published', 'registration_closed'])
    .gte('event_date', new Date().toISOString().split('T')[0])
    .order('event_date', { ascending: true });

  // Filter by chapter if specified
  if (searchParams.chapter) {
    const { data: chapter } = await supabase
      .from('chapters')
      .select('id')
      .eq('code', searchParams.chapter.toUpperCase())
      .single();

    if (chapter) {
      query = query.eq('chapter_id', chapter.id);
    }
  }

  const { data: events, error } = await query;

  // Get chapters for filter
  const { data: chapters } = await supabase
    .from('chapters')
    .select('*')
    .eq('is_active', true)
    .order('display_order');

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
              <Link href="/auth/login" className="btn-secondary">
                Log In
              </Link>
              <Link href="/auth/signup" className="btn-primary">
                Join Now
              </Link>
            </div>
          </div>
        </div>
      </header>

      {/* Page Header */}
      <div className="bg-primary-700 text-white py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h1 className="text-3xl font-bold">Upcoming Events</h1>
          <p className="mt-2 text-primary-100">
            Find your next round and register in minutes.
          </p>
        </div>
      </div>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Chapter Filter */}
        <div className="mb-8 flex flex-wrap gap-2">
          <Link
            href="/events"
            className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
              !searchParams.chapter
                ? 'bg-primary-600 text-white'
                : 'bg-white text-neutral-700 hover:bg-neutral-100 border border-neutral-200'
            }`}
          >
            All Chapters
          </Link>
          {chapters?.map((chapter) => (
            <Link
              key={chapter.id}
              href={`/events?chapter=${chapter.code}`}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                searchParams.chapter?.toUpperCase() === chapter.code
                  ? 'bg-primary-600 text-white'
                  : 'bg-white text-neutral-700 hover:bg-neutral-100 border border-neutral-200'
              }`}
            >
              {chapter.name}
            </Link>
          ))}
        </div>

        {/* Events Grid */}
        {events && events.length > 0 ? (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {events.map((event: any) => (
              <Link
                key={event.id}
                href={`/events/${event.id}`}
                className="card hover:shadow-md transition-shadow"
              >
                {/* Event Header */}
                <div className="p-6">
                  {/* Chapter Badge */}
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary-100 text-primary-800 mb-3">
                    {event.chapter?.name}
                  </span>

                  {/* Title */}
                  <h3 className="text-lg font-semibold text-neutral-900 mb-2">
                    {event.title}
                  </h3>

                  {/* Course */}
                  <p className="text-neutral-600 mb-4">{event.course_name}</p>

                  {/* Date & Time */}
                  <div className="flex items-center text-sm text-neutral-500 mb-2">
                    <svg
                      className="w-4 h-4 mr-2"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                      />
                    </svg>
                    {formatDate(event.event_date, 'full')}
                  </div>
                  <div className="flex items-center text-sm text-neutral-500 mb-4">
                    <svg
                      className="w-4 h-4 mr-2"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                    {formatTime(event.start_time)}
                  </div>

                  {/* Pricing */}
                  <div className="flex justify-between items-center pt-4 border-t border-neutral-100">
                    <div>
                      <span className="text-sm text-neutral-500">From</span>
                      <p className="font-semibold text-neutral-900">
                        {event.member_price !== null
                          ? formatCurrency(event.member_price)
                          : 'Free for members'}
                      </p>
                    </div>
                    <span className="text-primary-600 font-medium text-sm">
                      View Details →
                    </span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className="text-center py-12">
            <p className="text-neutral-500 mb-4">
              No upcoming events found.
            </p>
            <p className="text-sm text-neutral-400">
              Check back soon or{' '}
              <Link href="/" className="text-primary-600 hover:text-primary-500">
                sign up for updates
              </Link>
              .
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
