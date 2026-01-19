/**
 * =============================================================================
 * ROOT LAYOUT
 * =============================================================================
 * This wraps EVERY page in the application.
 * It provides:
 * - HTML structure
 * - Global fonts
 * - Metadata (title, description)
 * - Global providers (if any)
 * =============================================================================
 */

import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

// Load Inter font from Google Fonts
const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

// Default metadata for the site (can be overridden per page)
export const metadata: Metadata = {
  title: {
    default: 'The Golf Fellowship',
    template: '%s | The Golf Fellowship',
  },
  description:
    'The Done-For-You Golf Social Network. Compete, Connect, Belong.',
  keywords: ['golf', 'golf league', 'golf community', 'San Antonio', 'Austin'],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen bg-neutral-50 font-sans">
        {children}
      </body>
    </html>
  );
}
