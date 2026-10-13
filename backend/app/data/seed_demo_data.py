"""Demo seed data for PahadPath, plus a validating loader.

*** DRAFT: NOT YET HUMAN-VERIFIED ***
Everything below was drafted from general knowledge. A team member must check
each record against official tourism pages or local knowledge and then delete
the matching TODO_VERIFY comment. Run with --strict to fail while any remain.

Rules followed
- source_label is "team_curated"; reviewed_at is the draft date and is only a
  placeholder until a person has actually reviewed the record.
- No host names, phone numbers, prices or booking links are invented. The
  homestay rows are disabled placeholders (enabled=0) so they never reach the UI.
- No LocalPulse reports or events are seeded: nothing has been observed yet.
  Every destination therefore resolves to "needs_confirmation" for readiness.
- best_months is left empty (unknown) rather than guessed.
- baseline_popularity is a rough 0-100 judgement, not a measurement.

Run (from backend/):  python -m app.data.seed_demo_data [--db PATH] [--strict]
"""
import argparse
import os
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path

from app.models.database import init_schema
from app.models.schemas import ALLOWED_TAGS

SOURCE = "team_curated"
DRAFT_DATE = "2026-10-13"  # placeholder review date; update when a person reviews


def _dest(id_, name, district, lat, lon, description, tags, popularity):
    return {
        "id": id_, "name": name, "region": "Uttarakhand", "district": district,
        "latitude": lat, "longitude": lon, "description": description,
        "tags": tags, "best_months": [], "baseline_popularity": popularity,
        "access_notes": "", "last_mile_notes": "", "connectivity_notes": "",
        "readiness_source_label": None, "readiness_reviewed_at": None,
        "source_label": SOURCE, "reviewed_at": DRAFT_DATE, "enabled": 1,
    }


# Coordinates are approximate (2 decimals) and must be checked on a map.
DESTINATIONS = [
    # ---- 3 crowded hubs ----
    _dest(1, "Nainital", "Nainital", 29.39, 79.45,  # TODO_VERIFY coords, popularity, tags
          "Lake town in the Kumaon hills; a long-established hill-station hub.",
          ["nature", "local_food"], 90),
    _dest(2, "Mussoorie", "Dehradun", 30.46, 78.07,  # TODO_VERIFY coords, popularity, tags
          "Hill station in the Garhwal foothills, popular for short trips.",
          ["nature", "local_food"], 92),
    _dest(3, "Rishikesh", None, 30.09, 78.27,  # TODO_VERIFY district (spans several), coords, popularity, tags
          "Town on the Ganga in the foothills, known for temples and river activities.",
          ["temples", "trekking", "nature", "local_food"], 88),
    # ---- 9 quieter alternatives ----
    _dest(4, "Mukteshwar", "Nainital", 29.47, 79.65,  # TODO_VERIFY coords, popularity, tags
          "Hill village in Kumaon with a temple and orchards.",
          ["nature", "temples", "local_food", "quiet"], 45),
    _dest(5, "Sattal", "Nainital", 29.34, 79.56,  # TODO_VERIFY coords, popularity, tags
          "A cluster of small freshwater lakes in forested hills near Nainital.",
          ["nature", "quiet"], 38),
    _dest(6, "Ramgarh", "Nainital", 29.42, 79.57,  # TODO_VERIFY coords, popularity, tags
          "Orchard belt in Kumaon with village stays and wide valley views.",
          ["nature", "village", "local_food", "quiet"], 30),
    _dest(7, "Binsar", "Almora", 29.70, 79.76,  # TODO_VERIFY coords, popularity, tags
          "Forested hill area with a wildlife sanctuary and Himalayan views.",
          ["nature", "trekking", "quiet"], 28),
    _dest(8, "Chakrata", "Dehradun", 30.70, 77.87,  # TODO_VERIFY coords, popularity, tags
          "Hill town in western Garhwal with forest walks and few crowds.",
          ["nature", "trekking", "quiet"], 22),
    _dest(9, "Dhanaulti", "Tehri Garhwal", 30.41, 78.25,  # TODO_VERIFY coords, popularity, tags
          "Quiet hill stop among pine and deodar forest, near Mussoorie.",
          ["nature", "quiet"], 42),
    _dest(10, "Lansdowne", "Pauri Garhwal", 29.84, 78.68,  # TODO_VERIFY coords, popularity, tags
           "Small hill town with calm forest roads and a nearby temple.",
           ["nature", "temples", "quiet"], 40),
    _dest(11, "Kanatal", "Tehri Garhwal", 30.41, 78.32,  # TODO_VERIFY coords, popularity, tags
           "Small hill settlement on the Mussoorie-Chamba road, suited to short stays.",
           ["nature", "village", "quiet"], 35),
    _dest(12, "Devprayag", "Tehri Garhwal", 30.15, 78.60,  # TODO_VERIFY coords, popularity, tags
           "Town at the meeting of the Alaknanda and Bhagirathi rivers, where the Ganga is named.",
           ["temples", "village"], 25),
]

# (hub_id, alternative_id). match_tags are computed from shared tags below.
LINK_PAIRS = [
    (1, 4), (1, 5), (1, 6), (1, 7),        # Nainital   -> Kumaon alternatives  # TODO_VERIFY links
    (2, 8), (2, 9), (2, 10), (2, 11),      # Mussoorie  -> Garhwal alternatives  # TODO_VERIFY links
    (3, 12), (3, 10), (3, 11),             # Rishikesh  -> nearby alternatives   # TODO_VERIFY links
]


def _links(dests=DESTINATIONS, pairs=LINK_PAIRS):
    tags = {d["id"]: set(d["tags"]) for d in dests}
    return [
        {
            "source_destination_id": a, "alternative_destination_id": b,
            "match_tags": sorted(tags[a] & tags[b]), "reviewer_notes": "",
            "source_label": SOURCE, "reviewed_at": DRAFT_DATE, "enabled": 1,
        }
        for a, b in pairs
    ]


# Disabled placeholders: a person must add the real name, price range and source
# for each, then set enabled=1. Do not invent any of these fields.
HOMESTAY_DESTINATION_IDS = [4, 4, 5, 6, 7, 8, 9, 10, 11, 12]  # TODO_VERIFY real stays


def _homestays(dest_ids=HOMESTAY_DESTINATION_IDS):
    return [
        {
            "id": i + 1, "destination_id": d,
            "name": f"[Placeholder stay {i + 1}: add verified name]", "village": "",
            "price_min": None, "price_max": None, "currency": "INR",
            "public_contact": None, "booking_url": None, "amenities": [],
            "source_label": SOURCE, "reviewed_at": DRAFT_DATE,
            "publish_contact": 0, "enabled": 0,
        }
        for i, d in enumerate(dest_ids)
    ]


LINKS = _links()
HOMESTAYS = _homestays()


# --------------------------------------------------------------------------
# Validation (pure, so it can be tested)
# --------------------------------------------------------------------------


def _is_iso_date(value) -> bool:
    try:
        date.fromisoformat(value)
        return isinstance(value, str)
    except (TypeError, ValueError):
        return False


def validate(dests, links, homestays) -> list[str]:
    """Return a list of human-readable problems (empty list = valid)."""
    errors: list[str] = []
    ids = [d["id"] for d in dests]
    if len(set(ids)) != len(ids):
        errors.append("duplicate destination ids")
    names = [d["name"].strip().lower() for d in dests]
    if len(set(names)) != len(names):
        errors.append("duplicate destination names")

    for d in dests:
        who = f"destination {d['id']} ({d['name']})"
        if not 0 <= d["baseline_popularity"] <= 100:
            errors.append(f"{who}: baseline_popularity must be 0-100")
        bad = [t for t in d["tags"] if t not in ALLOWED_TAGS]
        if bad:
            errors.append(f"{who}: unknown tags {bad}")
        lat, lon = d["latitude"], d["longitude"]
        if lat is not None and not -90 <= lat <= 90:
            errors.append(f"{who}: latitude out of range")
        if lon is not None and not -180 <= lon <= 180:
            errors.append(f"{who}: longitude out of range")
        if not d["source_label"].strip():
            errors.append(f"{who}: source_label missing")
        if not _is_iso_date(d["reviewed_at"]):
            errors.append(f"{who}: reviewed_at missing or not YYYY-MM-DD")

    id_set = set(ids)
    seen_pairs = set()
    for ln in links:
        a, b = ln["source_destination_id"], ln["alternative_destination_id"]
        who = f"link {a}->{b}"
        if a not in id_set or b not in id_set:
            errors.append(f"{who}: references an unknown destination")
        if a == b:
            errors.append(f"{who}: source equals alternative")
        if (a, b) in seen_pairs:
            errors.append(f"{who}: duplicate pair")
        seen_pairs.add((a, b))
        if not _is_iso_date(ln["reviewed_at"]):
            errors.append(f"{who}: reviewed_at missing or not YYYY-MM-DD")

    for h in homestays:
        who = f"homestay {h['id']}"
        if h["destination_id"] not in id_set:
            errors.append(f"{who}: unknown destination_id {h['destination_id']}")
        lo, hi = h["price_min"], h["price_max"]
        if lo is not None and hi is not None and lo > hi:
            errors.append(f"{who}: price_min > price_max")
        if h["public_contact"] and not h["publish_contact"]:
            errors.append(f"{who}: contact present without publish consent")
        if h["booking_url"] and not h["booking_url"].startswith("https://"):
            errors.append(f"{who}: booking_url must be https://")
        if not _is_iso_date(h["reviewed_at"]):
            errors.append(f"{who}: reviewed_at missing or not YYYY-MM-DD")
    return errors


def count_todo_verify() -> int:
    """Count unresolved TODO_VERIFY comments in the seed and date-demand files."""
    pattern = re.compile(r"#\s*TODO_VERIFY")
    total = 0
    for path in (Path(__file__), Path(__file__).with_name("date_demand.py")):
        if path.exists():
            total += len(pattern.findall(path.read_text(encoding="utf-8")))
    return total


# --------------------------------------------------------------------------
# Loader
# --------------------------------------------------------------------------


def load(conn: sqlite3.Connection) -> None:
    """Drop and recreate all tables, then insert the seed records."""
    import json

    init_schema(conn, reset=True)
    for d in DESTINATIONS:
        conn.execute(
            "INSERT INTO destinations (id, name, district, region, latitude, longitude, description,"
            " tags_json, best_months_json, baseline_popularity, access_notes, last_mile_notes,"
            " connectivity_notes, readiness_source_label, readiness_reviewed_at, source_label,"
            " reviewed_at, enabled) VALUES (:id, :name, :district, :region, :latitude, :longitude,"
            " :description, :tags_json, :best_months_json, :baseline_popularity, :access_notes,"
            " :last_mile_notes, :connectivity_notes, :readiness_source_label,"
            " :readiness_reviewed_at, :source_label, :reviewed_at, :enabled)",
            {**d, "tags_json": json.dumps(d["tags"]), "best_months_json": json.dumps(d["best_months"])},
        )
    for ln in LINKS:
        conn.execute(
            "INSERT INTO alternative_links (source_destination_id, alternative_destination_id,"
            " match_tags_json, reviewer_notes, source_label, reviewed_at, enabled) VALUES"
            " (:source_destination_id, :alternative_destination_id, :match_tags_json,"
            " :reviewer_notes, :source_label, :reviewed_at, :enabled)",
            {**ln, "match_tags_json": json.dumps(ln["match_tags"])},
        )
    for h in HOMESTAYS:
        conn.execute(
            "INSERT INTO homestays (id, destination_id, name, village, price_min, price_max,"
            " currency, public_contact, booking_url, amenities_json, source_label, reviewed_at,"
            " publish_contact, enabled) VALUES (:id, :destination_id, :name, :village, :price_min,"
            " :price_max, :currency, :public_contact, :booking_url, :amenities_json, :source_label,"
            " :reviewed_at, :publish_contact, :enabled)",
            {**h, "amenities_json": json.dumps(h["amenities"])},
        )
    conn.commit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create and seed the PahadPath SQLite database.")
    parser.add_argument("--db", default=os.environ.get("DB_PATH", "pahadpath.db"))
    parser.add_argument("--strict", action="store_true",
                        help="exit non-zero while any TODO_VERIFY comment remains (use before the demo)")
    args = parser.parse_args(argv)

    errors = validate(DESTINATIONS, LINKS, HOMESTAYS)
    if errors:
        print("SEED VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1

    conn = sqlite3.connect(args.db)
    try:
        load(conn)
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            print(f"FOREIGN KEY CHECK FAILED: {violations}")
            return 1
    finally:
        conn.close()

    todo = count_todo_verify()
    print(f"Seeded {args.db}")
    print(f"  destinations:      {len(DESTINATIONS)}")
    print(f"  alternative links: {len(LINKS)}")
    print(f"  homestays:         {len(HOMESTAYS)} (all disabled placeholders)")
    print(f"  TODO_VERIFY left:  {todo}")
    if todo:
        print("  WARNING: draft data. A person must verify it before the demo.")
        if args.strict:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
