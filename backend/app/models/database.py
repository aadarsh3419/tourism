"""SQLite schema for PahadPath.

Part 1.2 only defines the schema. Part 2.1 adds get_connection() and the
DestinationRepository to this same file.

Conventions
- All dates are ISO text (YYYY-MM-DD); CHECKs reject anything else.
- tags / best_months / amenities are JSON arrays stored as text.
- Every record carries a non-empty source_label and a reviewed_at date.
- Unknown facts are NULL or empty, never guessed.
"""
import sqlite3

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS destinations (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK (length(trim(name)) > 0),
  district TEXT,
  region TEXT NOT NULL DEFAULT 'Uttarakhand',
  latitude REAL CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
  longitude REAL CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
  description TEXT NOT NULL DEFAULT '',
  tags_json TEXT NOT NULL DEFAULT '[]'
    CHECK (json_valid(tags_json) AND json_type(tags_json) = 'array'),
  best_months_json TEXT NOT NULL DEFAULT '[]'
    CHECK (json_valid(best_months_json) AND json_type(best_months_json) = 'array'),
  baseline_popularity INTEGER NOT NULL CHECK (baseline_popularity BETWEEN 0 AND 100),
  access_notes TEXT NOT NULL DEFAULT '',
  last_mile_notes TEXT NOT NULL DEFAULT '',
  connectivity_notes TEXT NOT NULL DEFAULT '',
  readiness_source_label TEXT,
  readiness_reviewed_at TEXT CHECK (readiness_reviewed_at IS NULL OR date(readiness_reviewed_at) IS readiness_reviewed_at),
  source_label TEXT NOT NULL CHECK (length(trim(source_label)) > 0),
  reviewed_at TEXT NOT NULL CHECK (date(reviewed_at) IS reviewed_at),
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  -- readiness source and date are set together or not at all
  CHECK ((readiness_source_label IS NULL) = (readiness_reviewed_at IS NULL))
);

CREATE TABLE IF NOT EXISTS alternative_links (
  id INTEGER PRIMARY KEY,
  source_destination_id INTEGER NOT NULL REFERENCES destinations(id),
  alternative_destination_id INTEGER NOT NULL REFERENCES destinations(id),
  match_tags_json TEXT NOT NULL DEFAULT '[]'
    CHECK (json_valid(match_tags_json) AND json_type(match_tags_json) = 'array'),
  reviewer_notes TEXT NOT NULL DEFAULT '',
  source_label TEXT NOT NULL CHECK (length(trim(source_label)) > 0),
  reviewed_at TEXT NOT NULL CHECK (date(reviewed_at) IS reviewed_at),
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  CHECK (source_destination_id <> alternative_destination_id),
  UNIQUE (source_destination_id, alternative_destination_id)
);

CREATE TABLE IF NOT EXISTS homestays (
  id INTEGER PRIMARY KEY,
  destination_id INTEGER NOT NULL REFERENCES destinations(id),
  name TEXT NOT NULL CHECK (length(trim(name)) > 0),
  village TEXT NOT NULL DEFAULT '',
  price_min INTEGER CHECK (price_min IS NULL OR price_min >= 0),
  price_max INTEGER CHECK (price_max IS NULL OR price_max >= 0),
  currency TEXT NOT NULL DEFAULT 'INR',
  public_contact TEXT,
  booking_url TEXT CHECK (booking_url IS NULL OR booking_url LIKE 'https://%'),
  amenities_json TEXT NOT NULL DEFAULT '[]'
    CHECK (json_valid(amenities_json) AND json_type(amenities_json) = 'array'),
  source_label TEXT NOT NULL CHECK (length(trim(source_label)) > 0),
  reviewed_at TEXT NOT NULL CHECK (date(reviewed_at) IS reviewed_at),
  publish_contact INTEGER NOT NULL DEFAULT 0 CHECK (publish_contact IN (0, 1)),
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  CHECK (price_min IS NULL OR price_max IS NULL OR price_min <= price_max),
  -- a contact may only be stored if the host agreed to publish it
  CHECK (publish_contact = 1 OR public_contact IS NULL)
);

CREATE TABLE IF NOT EXISTS local_events (
  id INTEGER PRIMARY KEY,
  destination_id INTEGER REFERENCES destinations(id),  -- NULL = region-wide event
  name TEXT NOT NULL CHECK (length(trim(name)) > 0),
  start_date TEXT NOT NULL CHECK (date(start_date) IS start_date),
  end_date TEXT NOT NULL CHECK (date(end_date) IS end_date),
  demand_boost INTEGER NOT NULL DEFAULT 0 CHECK (demand_boost BETWEEN 0 AND 100),
  source_label TEXT NOT NULL CHECK (length(trim(source_label)) > 0),
  source_url TEXT,
  reviewed_at TEXT NOT NULL CHECK (date(reviewed_at) IS reviewed_at),
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  CHECK (end_date >= start_date)
);

CREATE TABLE IF NOT EXISTS local_reports (
  id INTEGER PRIMARY KEY,
  destination_id INTEGER NOT NULL REFERENCES destinations(id),
  report_type TEXT NOT NULL
    CHECK (report_type IN ('access', 'transport', 'crowd_observation', 'service', 'weather_note')),
  summary TEXT NOT NULL CHECK (length(trim(summary)) > 0),
  source_label TEXT NOT NULL CHECK (length(trim(source_label)) > 0),
  source_url TEXT,
  observed_at TEXT NOT NULL CHECK (date(observed_at) IS observed_at),
  reviewed_at TEXT NOT NULL CHECK (date(reviewed_at) IS reviewed_at),
  expires_at TEXT CHECK (expires_at IS NULL OR date(expires_at) IS expires_at),
  verification_status TEXT NOT NULL DEFAULT 'reviewed'
    CHECK (verification_status IN ('unverified', 'reviewed', 'rejected')),
  CHECK (expires_at IS NULL OR expires_at >= observed_at)
);

-- Indexes: every foreign key plus the common filters
CREATE INDEX IF NOT EXISTS idx_destinations_region_enabled ON destinations(region, enabled);
CREATE INDEX IF NOT EXISTS idx_alt_source ON alternative_links(source_destination_id, enabled);
CREATE INDEX IF NOT EXISTS idx_alt_target ON alternative_links(alternative_destination_id);
CREATE INDEX IF NOT EXISTS idx_homestays_destination ON homestays(destination_id, enabled);
CREATE INDEX IF NOT EXISTS idx_events_destination ON local_events(destination_id);
CREATE INDEX IF NOT EXISTS idx_events_dates ON local_events(start_date, end_date, enabled);
CREATE INDEX IF NOT EXISTS idx_reports_destination ON local_reports(destination_id, reviewed_at);
CREATE INDEX IF NOT EXISTS idx_reports_expiry ON local_reports(expires_at, verification_status);
"""

# Child tables first, so foreign keys never block the drops.
DROP_SQL = """
DROP TABLE IF EXISTS local_reports;
DROP TABLE IF EXISTS local_events;
DROP TABLE IF EXISTS homestays;
DROP TABLE IF EXISTS alternative_links;
DROP TABLE IF EXISTS destinations;
"""


def init_schema(conn: sqlite3.Connection, *, reset: bool = False) -> None:
    """Create all tables. With reset=True, drop and recreate (used by the seed loader)."""
    conn.execute("PRAGMA foreign_keys = ON")
    if reset:
        conn.executescript(DROP_SQL)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
