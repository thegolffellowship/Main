/**
 * =============================================================================
 * TGF PLATFORM - DATABASE TYPES
 * =============================================================================
 * These TypeScript types match our database schema exactly.
 * They help catch errors before code runs.
 *
 * Think of types as "contracts" - they define what shape data should have.
 * =============================================================================
 */

// =============================================================================
// ENUMS (Dropdown options)
// =============================================================================

/**
 * Member Status - What kind of user is this?
 * - active_member: Currently has paid membership
 * - expired_member: Was a member, membership lapsed
 * - former_member: Explicitly left/cancelled
 * - guest: Has played but never been a member
 * - prospect: Signed up but never played or joined
 */
export type MemberStatus =
  | 'active_member'
  | 'expired_member'
  | 'former_member'
  | 'guest'
  | 'prospect';

/**
 * Payment Status - Where is the payment?
 */
export type PaymentStatus =
  | 'pending'
  | 'paid'
  | 'partially_paid'
  | 'refunded'
  | 'partially_refunded'
  | 'comped';

/**
 * Event Status - What stage is the event in?
 */
export type EventStatus =
  | 'draft'
  | 'published'
  | 'registration_closed'
  | 'in_progress'
  | 'completed'
  | 'cancelled';

/**
 * Transaction Type - What kind of money movement?
 */
export type TransactionType =
  | 'membership_purchase'
  | 'membership_renewal'
  | 'event_registration'
  | 'wallet_deposit'
  | 'wallet_payment'
  | 'wallet_credit'
  | 'refund'
  | 'adjustment';

/**
 * Player Type - How is this person playing?
 */
export type PlayerType = 'member' | 'guest' | 'first_timer';

/**
 * Payment Method - How did they pay?
 */
export type PaymentMethod =
  | 'stripe'
  | 'wallet'
  | 'cash'
  | 'venmo'
  | 'check'
  | 'comp';

// =============================================================================
// CORE TYPES (Main tables)
// =============================================================================

/**
 * Chapter - A TGF location (San Antonio, Austin, etc.)
 */
export interface Chapter {
  id: string;
  name: string;
  code: string;
  city: string;
  state: string;
  description: string | null;
  is_active: boolean;
  display_order: number;
  settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

/**
 * Membership Type - A membership product (Annual, Founding, etc.)
 */
export interface MembershipType {
  id: string;
  name: string;
  description: string | null;
  price: number;
  duration_months: number;
  is_active: boolean;
  is_publicly_available: boolean;
  allowed_chapter_ids: string[] | null;
  benefits: {
    all_chapters?: boolean;
    net_games?: boolean;
    season_contests?: boolean;
    guest_events_per_year?: number;
    merchandise_discount?: number;
  };
  display_order: number;
  created_at: string;
  updated_at: string;
}

/**
 * Member - A person in the system (member, guest, prospect)
 */
export interface Member {
  id: string;
  auth_user_id: string | null;
  email: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  ghin_number: string | null;
  home_chapter_id: string | null;
  status: MemberStatus;
  current_membership_id: string | null;
  membership_expires_at: string | null;
  wallet_balance: number;
  stripe_customer_id: string | null;
  first_event_date: string | null;
  events_played_count: number;
  email_notifications: boolean;
  sms_notifications: boolean;
  is_admin: boolean;
  is_chapter_manager: boolean;
  managed_chapter_ids: string[];
  notes: string | null;
  created_at: string;
  updated_at: string;
  last_login_at: string | null;
}

/**
 * Member Membership - A membership purchase/period
 */
export interface MemberMembership {
  id: string;
  member_id: string;
  membership_type_id: string;
  starts_at: string;
  expires_at: string;
  amount_paid: number;
  transaction_id: string | null;
  is_active: boolean;
  cancelled_at: string | null;
  cancellation_reason: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * Game - A contest type (NET Skins, CTP, etc.)
 */
export interface Game {
  id: string;
  name: string;
  short_name: string | null;
  description: string | null;
  default_price: number;
  requires_membership: boolean;
  requires_ghin: boolean;
  scoring_type: string | null;
  is_active: boolean;
  display_order: number;
  created_at: string;
  updated_at: string;
}

/**
 * Event - A golf event
 */
export interface Event {
  id: string;
  chapter_id: string;
  title: string;
  description: string | null;
  event_type: string;
  course_name: string;
  course_address: string | null;
  course_phone: string | null;
  course_website: string | null;
  course_notes: string | null;
  event_date: string;
  start_time: string;
  check_in_time: string | null;
  max_players: number | null;
  min_players: number;
  registration_opens_at: string | null;
  registration_closes_at: string | null;
  base_price: number;
  member_price: number | null;
  guest_surcharge: number;
  first_timer_discount: number;
  tax_rate: number;
  status: EventStatus;
  waitlist_enabled: boolean;
  settings: Record<string, unknown>;
  results_published_at: string | null;
  results_data: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  published_at: string | null;
  created_by_id: string | null;
  updated_by_id: string | null;
}

/**
 * Event Game - A game offered at a specific event
 */
export interface EventGame {
  id: string;
  event_id: string;
  game_id: string;
  price_override: number | null;
  is_mandatory: boolean;
  display_order: number;
  results: Record<string, unknown> | null;
  created_at: string;
}

/**
 * Registration - A player signed up for an event
 */
export interface Registration {
  id: string;
  event_id: string;
  member_id: string;
  player_type: PlayerType;
  subtotal: number;
  tax_amount: number;
  total_amount: number;
  amount_paid: number;
  payment_status: PaymentStatus;
  payment_method: PaymentMethod | null;
  stripe_payment_intent_id: string | null;
  wallet_amount_used: number;
  is_waitlisted: boolean;
  waitlist_position: number | null;
  waitlist_promoted_at: string | null;
  checked_in_at: string | null;
  checked_in_by_id: string | null;
  cancelled_at: string | null;
  cancellation_reason: string | null;
  refund_amount: number | null;
  player_notes: string | null;
  manager_notes: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * Registration Game - A game selected by a player
 */
export interface RegistrationGame {
  id: string;
  registration_id: string;
  event_game_id: string;
  price_at_registration: number;
  created_at: string;
}

/**
 * Transaction - A financial record
 */
export interface Transaction {
  id: string;
  member_id: string | null;
  type: TransactionType;
  amount: number;
  description: string;
  registration_id: string | null;
  membership_id: string | null;
  stripe_payment_intent_id: string | null;
  stripe_charge_id: string | null;
  stripe_refund_id: string | null;
  idempotency_key: string | null;
  status: string;
  metadata: Record<string, unknown>;
  created_at: string;
  processed_at: string | null;
}

/**
 * Wallet Transaction - A wallet balance change
 */
export interface WalletTransaction {
  id: string;
  member_id: string;
  amount: number;
  balance_before: number;
  balance_after: number;
  description: string;
  transaction_id: string | null;
  registration_id: string | null;
  created_by_id: string | null;
  created_at: string;
}

/**
 * Feature Flag - A toggleable feature
 */
export interface FeatureFlag {
  id: string;
  key: string;
  name: string;
  description: string | null;
  enabled: boolean;
  enabled_for_member_ids: string[];
  enabled_for_chapter_ids: string[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

// =============================================================================
// COMPOSITE TYPES (Joined data from multiple tables)
// =============================================================================

/**
 * Event with Chapter info - Common pattern for event listings
 */
export interface EventWithChapter extends Event {
  chapter: Chapter;
}

/**
 * Event with Games - Event details page
 */
export interface EventWithGames extends Event {
  chapter: Chapter;
  event_games: (EventGame & { game: Game })[];
}

/**
 * Registration with details - For roster view
 */
export interface RegistrationWithDetails extends Registration {
  member: Pick<Member, 'id' | 'first_name' | 'last_name' | 'email' | 'phone' | 'ghin_number'>;
  registration_games: (RegistrationGame & { event_game: EventGame & { game: Game } })[];
}

/**
 * Member with active membership - Common dashboard view
 */
export interface MemberWithMembership extends Member {
  current_membership: (MemberMembership & { membership_type: MembershipType }) | null;
  home_chapter: Chapter | null;
}

// =============================================================================
// FORM INPUT TYPES (For creating/updating records)
// =============================================================================

/**
 * Create a new member
 */
export interface CreateMemberInput {
  email: string;
  first_name: string;
  last_name: string;
  phone?: string;
  ghin_number?: string;
  home_chapter_id?: string;
}

/**
 * Create an event
 */
export interface CreateEventInput {
  chapter_id: string;
  title: string;
  description?: string;
  event_type: string;
  course_name: string;
  course_address?: string;
  course_phone?: string;
  course_website?: string;
  course_notes?: string;
  event_date: string;
  start_time: string;
  check_in_time?: string;
  max_players?: number;
  min_players?: number;
  registration_opens_at?: string;
  registration_closes_at?: string;
  base_price: number;
  member_price?: number;
  guest_surcharge?: number;
  first_timer_discount?: number;
  tax_rate?: number;
  waitlist_enabled?: boolean;
  game_ids?: string[];
}

/**
 * Register for an event
 */
export interface CreateRegistrationInput {
  event_id: string;
  member_id: string;
  selected_game_ids: string[];
  use_wallet_balance?: boolean;
  player_notes?: string;
}

/**
 * Add funds to wallet
 */
export interface WalletDepositInput {
  member_id: string;
  amount: number;
}

/**
 * Credit wallet (manager action)
 */
export interface WalletCreditInput {
  member_id: string;
  amount: number;
  description: string;
}
