"""Part 1 contract tests: Pydantic validators, SQLite constraints, and a
drift check between schemas.py and frontend/src/services/types.ts.

Run from backend/:  pytest tests/test_contract.py
"""
import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from app.models import schemas
from app.models.database import init_schema
from app.models.schemas import (
    ALLOWED_TAGS,
    CrowdComponents,
    CrowdResult,
    Homestay,
    ItineraryRequest,
    RecommendationRequest,
    crowd_level_for,
)

TOMORROW = date.today() + timedelta(days=1)


def rec_body(**over):
    body = {"start_date": TOMORROW.isoformat(), "days": 2, "interests": ["nature"]}
    body.update(over)
    return body


# ---- Pydantic validators ----------------------------------------------------


def test_valid_request_passes_and_defaults():
    r = RecommendationRequest(**rec_body())
    assert r.region == "Uttarakhand" and r.avoid_crowds is True


@pytest.mark.parametrize(
    "over",
    [
        {"start_date": (date.today() - timedelta(days=1)).isoformat()},  # past
        {"days": 0},
        {"days": 8},
        {"interests": ["beaches"]},  # not in ALLOWED_TAGS
        {"interests": ["nature"] * 9},  # more than 8
        {"budget_per_night_max": -1},
        {"max_drive_hours": 13},
        {"surprise_field": 1},  # extra="forbid"
    ],
)
def test_bad_recommendation_requests_rejected(over):
    with pytest.raises(ValidationError):
        RecommendationRequest(**rec_body(**over))


def test_interests_are_normalised_and_deduplicated():
    r = RecommendationRequest(**rec_body(interests=["Nature", " nature ", "VILLAGE"]))
    assert r.interests == ["nature", "village"]


def test_today_is_allowed():
    RecommendationRequest(**rec_body(start_date=date.today().isoformat()))


def test_itinerary_request_rules():
    base = {"start_date": TOMORROW.isoformat(), "days": 2, "destination_ids": [1, 2]}
    assert ItineraryRequest(**base).use_ai is False  # LLM is opt-in
    for bad in ({"destination_ids": []}, {"destination_ids": [1, 1]},
                {"destination_ids": [1, 2, 3, 4]}, {"destination_ids": [0]}):
        with pytest.raises(ValidationError):
            ItineraryRequest(**{**base, **bad})


def test_crowd_level_boundaries():
    cases = {0: "Quiet", 34: "Quiet", 35: "Moderate", 59: "Moderate",
             60: "Busy", 79: "Busy", 80: "Very busy", 100: "Very busy"}
    for score, level in cases.items():
        assert crowd_level_for(score) == level


def test_crowd_result_rejects_label_that_contradicts_score():
    comps = CrowdComponents(baseline_popularity=50, date_demand=50,
                            event_pressure=50, weather_visit_tendency=50)
    ok = CrowdResult(score=50, level="Moderate", components=comps, reviewed_at=date.today())
    assert ok.mode == "curated_rule_estimate"
    with pytest.raises(ValidationError):
        CrowdResult(score=50, level="Quiet", components=comps, reviewed_at=date.today())
    with pytest.raises(ValidationError):
        CrowdResult(score=101, level="Very busy", components=comps, reviewed_at=date.today())


def test_homestay_rules():
    base = dict(id=1, destination_id=1, name="Example", source_label="team_curated",
                reviewed_at=date.today())
    assert Homestay(**base).price_min is None  # unknown price stays None
    with pytest.raises(ValidationError):
        Homestay(**base, price_min=3000, price_max=2000)
    with pytest.raises(ValidationError):
        Homestay(**base, booking_url="http://insecure.example")
    Homestay(**base, booking_url="https://ok.example")


# ---- SQLite constraints -------------------------------------------------------


@pytest.fixture()
def db():
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    yield conn
    conn.close()


def add_dest(conn, id_, name, pop=40, **over):
    row = dict(id=id_, name=name, baseline_popularity=pop,
               source_label="team_curated", reviewed_at="2026-10-12")
    row.update(over)
    cols = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    conn.execute(f"INSERT INTO destinations ({cols}) VALUES ({marks})", list(row.values()))


def test_foreign_keys_are_enforced(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO homestays (destination_id, name, source_label, reviewed_at) "
                   "VALUES (99, 'x', 's', '2026-10-12')")


@pytest.mark.parametrize("over", [
    {"baseline_popularity": 101},
    {"baseline_popularity": -1},
    {"source_label": ""},
    {"reviewed_at": "12/10/2026"},
    {"tags_json": "not json"},
    {"tags_json": "{}"},  # JSON but not an array
    {"readiness_source_label": "x"},  # source without date
])
def test_destination_checks(db, over):
    with pytest.raises(sqlite3.IntegrityError):
        add_dest(db, 1, "A", **over)


def test_duplicate_destination_names_blocked_case_insensitively(db):
    add_dest(db, 1, "Example Place")
    with pytest.raises(sqlite3.IntegrityError):
        add_dest(db, 2, "example place")


def test_alternative_link_rules(db):
    add_dest(db, 1, "A")
    add_dest(db, 2, "B")
    ins = ("INSERT INTO alternative_links (source_destination_id, alternative_destination_id, "
           "source_label, reviewed_at) VALUES (?, ?, 's', '2026-10-12')")
    db.execute(ins, (1, 2))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(ins, (1, 2))  # duplicate pair
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(ins, (1, 1))  # source == alternative


def test_homestay_rules_in_sql(db):
    add_dest(db, 1, "A")
    ins = ("INSERT INTO homestays (destination_id, name, price_min, price_max, public_contact, "
           "booking_url, publish_contact, source_label, reviewed_at) "
           "VALUES (1, 'H', ?, ?, ?, ?, ?, 's', '2026-10-12')")
    db.execute(ins, (None, None, None, None, 0))  # all unknowns are fine
    for bad in [(3000, 2000, None, None, 0),            # min > max
                (1000, 2000, "+91-000", None, 0),       # contact without consent
                (1000, 2000, None, "http://x.example", 0)]:  # not https
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(ins, bad)


def test_event_and_report_rules(db):
    add_dest(db, 1, "A")
    with pytest.raises(sqlite3.IntegrityError):  # end before start
        db.execute("INSERT INTO local_events (name, start_date, end_date, source_label, reviewed_at) "
                   "VALUES ('e', '2026-11-10', '2026-11-09', 's', '2026-10-12')")
    with pytest.raises(sqlite3.IntegrityError):  # unsupported report type
        db.execute("INSERT INTO local_reports (destination_id, report_type, summary, source_label, "
                   "observed_at, reviewed_at) VALUES (1, 'rumour', 'x', 's', '2026-10-01', '2026-10-02')")
    with pytest.raises(sqlite3.IntegrityError):  # expires before observed
        db.execute("INSERT INTO local_reports (destination_id, report_type, summary, source_label, "
                   "observed_at, reviewed_at, expires_at) "
                   "VALUES (1, 'access', 'x', 's', '2026-10-05', '2026-10-06', '2026-10-01')")


def test_init_schema_reset_is_rerunnable(db):
    add_dest(db, 1, "A")
    init_schema(db, reset=True)
    assert db.execute("SELECT COUNT(*) FROM destinations").fetchone()[0] == 0


# ---- Contract drift: schemas.py vs types.ts -------------------------------------

TYPES_TS = Path(__file__).resolve().parents[2] / "frontend/src/services/types.ts"


def ts_interfaces() -> dict[str, set[str]]:
    src = TYPES_TS.read_text()
    out: dict[str, set[str]] = {}
    for m in re.finditer(r"export interface (\w+) \{(.*?)^\}", src, re.S | re.M):
        fields = set(re.findall(r"^\s{2}(\w+)\??:", m.group(2), re.M))
        out[m.group(1)] = fields
    return out


def test_every_response_model_matches_typescript():
    ts = ts_interfaces()
    checked = 0
    for name, cls in vars(schemas).items():
        if not (isinstance(cls, type) and issubclass(cls, BaseModel) and cls is not BaseModel):
            continue
        if name.startswith("_"):
            continue
        assert name in ts, f"{name} is in schemas.py but missing from types.ts"
        assert set(cls.model_fields) == ts[name], (
            f"{name}: schemas.py has {sorted(set(cls.model_fields) ^ ts[name])} different from types.ts"
        )
        checked += 1
    assert checked == 18  # update when a model is added


def test_allowed_tags_match_typescript():
    src = TYPES_TS.read_text()
    block = re.search(r"ALLOWED_TAGS = \[(.*?)\]", src, re.S).group(1)
    assert tuple(re.findall(r'"(\w+)"', block)) == ALLOWED_TAGS
