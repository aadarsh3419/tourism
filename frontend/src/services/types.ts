/**
 * PahadPath API contract (TypeScript mirror of backend/app/models/schemas.py).
 * If a field changes, change schemas.py in the same commit.
 *
 * Dates are "YYYY-MM-DD" strings. Optional backend fields (`X | None`) are
 * `X | null` here because FastAPI serializes None as null.
 */

export const ALLOWED_TAGS = [
  "nature",
  "village",
  "local_food",
  "temples",
  "trekking",
  "quiet",
] as const;
export type InterestTag = (typeof ALLOWED_TAGS)[number];

export const MAX_INTERESTS = 8;
export const MAX_DAYS = 7;
export const MAX_PLAN_DESTINATIONS = 3;

export type DataMode = "curated_rule_estimate";
export type CrowdLevel = "Quiet" | "Moderate" | "Busy" | "Very busy";
export type GenerationMode = "llm_validated" | "template";
export type TimeBlock = "morning" | "afternoon" | "evening";
export type ReadinessStatus =
  | "ready_to_plan"
  | "needs_confirmation"
  | "restriction_reported";
export type ReportType =
  | "access"
  | "transport"
  | "crowd_observation"
  | "service"
  | "weather_note";
export type VerificationStatus = "unverified" | "reviewed" | "rejected";

// ---- Errors ---------------------------------------------------------------

export interface ErrorDetail {
  code: string;
  message: string;
  request_id?: string | null;
}

export interface ErrorResponse {
  detail: ErrorDetail;
}

// ---- Catalogue records ----------------------------------------------------

export interface Destination {
  id: number;
  name: string;
  district: string | null;
  region: string;
  latitude: number | null;
  longitude: number | null;
  description: string;
  tags: string[];
  best_months: number[]; // 1-12
  baseline_popularity: number; // 0-100
  access_notes: string;
  last_mile_notes: string;
  connectivity_notes: string;
  readiness_source_label: string | null;
  readiness_reviewed_at: string | null;
  source_label: string;
  reviewed_at: string;
  alternative_ids: number[];
}

export interface Homestay {
  id: number;
  destination_id: number;
  name: string;
  village: string;
  price_min: number | null; // null => show "Price on request"
  price_max: number | null;
  currency: string;
  public_contact: string | null; // show only if present
  booking_url: string | null; // https:// only; show only if present
  amenities: string[];
  source_label: string;
  reviewed_at: string;
}

// ---- Crowd estimate, readiness, LocalPulse --------------------------------

export interface CrowdComponents {
  baseline_popularity: number;
  date_demand: number;
  event_pressure: number;
  weather_visit_tendency: number;
}

export interface CrowdResult {
  score: number; // 0-100
  level: CrowdLevel; // always display as "<level> (estimated)"
  mode: DataMode;
  components: CrowdComponents;
  notes: string[];
  reviewed_at: string;
}

export interface LocalPulseReport {
  id: number;
  report_type: ReportType;
  summary: string;
  source_label: string;
  source_url: string | null;
  observed_at: string;
  reviewed_at: string;
  expires_at: string | null;
  verification_status: VerificationStatus;
  is_stale: boolean;
}

export interface TripReadinessResult {
  status: ReadinessStatus; // a planning aid, not a safety certificate
  reasons: string[];
  reviewed_at: string | null;
  evidence: LocalPulseReport[];
}

// ---- Recommendations ------------------------------------------------------

export interface RecommendationRequest {
  region: string;
  start_destination_id?: number | null;
  start_date: string;
  days: number; // 1-7
  interests: InterestTag[]; // max 8
  budget_per_night_max?: number | null;
  avoid_crowds: boolean;
  max_drive_hours?: number | null;
}

export interface ScoreComponents {
  interest_fit: number;
  quietness_fit: number;
  travel_fit: number;
  homestay_fit: number;
}

export interface Recommendation {
  destination_id: number;
  name: string;
  rank_score: number;
  crowd: CrowdResult;
  score_components: ScoreComponents;
  shared_tags: string[];
  reasons: string[]; // at least one
  reviewed_at: string;
  readiness: TripReadinessResult;
}

export interface RecommendationResponse {
  request_id: string;
  data_mode: DataMode;
  start_crowd: CrowdResult | null;
  recommendations: Recommendation[];
  warnings: string[];
}

// ---- Itineraries ----------------------------------------------------------

export interface ItineraryRequest {
  start_date: string;
  days: number; // 1-7
  destination_ids: number[]; // 1-3, unique
  interests: InterestTag[];
  budget_per_night_max?: number | null;
  use_ai: boolean;
}

export interface ItineraryItem {
  time_block: TimeBlock;
  destination_id: number;
  destination_name: string;
  activity_text: string;
  reason: string;
  crowd: CrowdResult;
}

export interface ItineraryDay {
  date: string;
  items: ItineraryItem[];
}

export interface ItineraryResponse {
  request_id: string;
  generation_mode: GenerationMode;
  data_mode: DataMode;
  days: ItineraryDay[];
  homestay_ids: number[];
  destinations: Destination[]; // resolved records, saved for offline use
  homestays: Homestay[];
  warnings: string[];
}

// ---- Stretch: Hinglish parser ---------------------------------------------

export interface ParseRequestBody {
  text: string; // max 300 chars
}

export interface ParseRequestResponse {
  days: number | null;
  interests: InterestTag[];
  budget_per_night_max: number | null;
  start_destination_id: number | null;
}
