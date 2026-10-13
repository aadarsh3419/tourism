"""Tests for the seed data, its validating loader, and date_demand()."""
import copy
import sqlite3
from datetime import date

import pytest

from app.data import seed_demo_data as seed
from app.data.date_demand import HOLIDAYS, MONTH_DEMAND, date_demand
from app.models.schemas import ALLOWED_TAGS, Destination, Homestay


def test_seed_data_is_valid():
    assert seed.validate(seed.DESTINATIONS, seed.LINKS, seed.HOMESTAYS) == []


def test_seed_shape_matches_the_plan():
    assert len(seed.DESTINATIONS) == 12
    assert len(seed.HOMESTAYS) == 10
    hubs = {ln["source_destination_id"] for ln in seed.LINKS}
    assert hubs == {1, 2, 3}  # 3 crowded hubs
    alternatives = {ln["alternative_destination_id"] for ln in seed.LINKS}
    assert len(alternatives) == 9 and alternatives.isdisjoint(hubs)


def test_no_invented_private_data():
    for h in seed.HOMESTAYS:
        assert h["price_min"] is None and h["price_max"] is None
        assert h["public_contact"] is None and h["booking_url"] is None
        assert h["enabled"] == 0  # placeholders never reach the UI
    for d in seed.DESTINATIONS:
        assert d["best_months"] == []  # unknown, not guessed
        assert d["readiness_source_label"] is None  # no readiness claims


def test_records_fit_the_pydantic_contract():
    for d in seed.DESTINATIONS:
        Destination(**{k: v for k, v in d.items() if k != "enabled"})
    for h in seed.HOMESTAYS:
        Homestay(**{k: v for k, v in h.items() if k not in ("enabled", "publish_contact")})


def test_every_destination_has_allowed_tags():
    for d in seed.DESTINATIONS:
        assert d["tags"] and set(d["tags"]) <= set(ALLOWED_TAGS)


def test_every_interest_tag_has_at_least_one_alternative():
    alt_ids = {ln["alternative_destination_id"] for ln in seed.LINKS}
    covered = {t for d in seed.DESTINATIONS if d["id"] in alt_ids for t in d["tags"]}
    assert covered == set(ALLOWED_TAGS)


def test_validator_catches_each_kind_of_bad_data():
    def broken(mutate):
        d, ln, h = (copy.deepcopy(x) for x in (seed.DESTINATIONS, seed.LINKS, seed.HOMESTAYS))
        mutate(d, ln, h)
        return seed.validate(d, ln, h)

    assert broken(lambda d, l, h: d[1].update(name=d[0]["name"].upper()))  # duplicate name
    assert broken(lambda d, l, h: d[0].update(baseline_popularity=101))
    assert broken(lambda d, l, h: d[0].update(tags=["beaches"]))
    assert broken(lambda d, l, h: d[0].update(latitude=95))
    assert broken(lambda d, l, h: d[0].update(reviewed_at=""))
    assert broken(lambda d, l, h: l[0].update(alternative_destination_id=999))  # dangling FK
    assert broken(lambda d, l, h: l[0].update(alternative_destination_id=l[0]["source_destination_id"]))
    assert broken(lambda d, l, h: l.append(copy.deepcopy(l[0])))  # duplicate pair
    assert broken(lambda d, l, h: h[0].update(price_min=3000, price_max=2000))
    assert broken(lambda d, l, h: h[0].update(public_contact="+91-0", publish_contact=0))
    assert broken(lambda d, l, h: h[0].update(booking_url="http://x.example"))
    assert broken(lambda d, l, h: h[0].update(destination_id=999))


def test_loader_creates_a_consistent_database_and_is_rerunnable(tmp_path):
    db = tmp_path / "t.db"
    assert seed.main(["--db", str(db)]) == 0
    assert seed.main(["--db", str(db)]) == 0  # drop and recreate
    conn = sqlite3.connect(db)
    counts = [conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("destinations", "alternative_links", "homestays", "local_reports", "local_events")]
    assert counts == [12, 11, 10, 0, 0]
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    conn.close()


def test_strict_mode_fails_while_todo_verify_remains(tmp_path):
    assert seed.count_todo_verify() > 0
    assert seed.main(["--db", str(tmp_path / "s.db"), "--strict"]) == 1


# ---- date_demand ------------------------------------------------------------


def test_date_demand_is_bounded_for_every_day_of_a_year():
    d = date(2026, 1, 1)
    while d.year == 2026:
        score, notes = date_demand(d)
        assert 0 <= score <= 100 and notes
        d = date.fromordinal(d.toordinal() + 1)


def test_weekend_adds_uplift_and_weekday_does_not():
    assert date_demand(date(2026, 11, 14))[0] > date_demand(date(2026, 11, 11))[0]  # Sat vs Wed
    assert date_demand(date(2026, 11, 11))[0] == MONTH_DEMAND[11]


def test_holiday_adds_uplift_and_a_note():
    plain = MONTH_DEMAND[10]
    score, notes = date_demand(date(2026, 10, 20))  # Dussehra, a Tuesday
    assert score == plain + 15
    assert any("Dussehra" in n for n in notes)


def test_score_is_clamped_at_100():
    # May is 95; a weekend adds 10, so it must clamp.
    assert date_demand(date(2026, 5, 16))[0] == 100


def test_outside_calendar_range_is_noted():
    assert any("Oct-Dec 2026" in n for n in date_demand(date(2027, 3, 3))[1])


def test_holiday_ranges_are_well_formed():
    for start, end, name in HOLIDAYS:
        assert start <= end and name
