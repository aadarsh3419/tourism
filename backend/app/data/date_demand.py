"""Date demand rules: how busy Uttarakhand tends to be on a given date.

*** DRAFT: values are rough curated judgements, not measurements. ***
Every number and holiday date below must be checked by a person; the
TODO_VERIFY comments mark what is still unchecked.

date_demand(date) -> (score 0-100, notes) feeds the date_demand component of
the crowd estimate. Pure function: no I/O.
"""
from datetime import date

# Month -> season demand (0-100) for Uttarakhand as a whole.
MONTH_DEMAND: dict[int, int] = {
    1: 40,   # TODO_VERIFY
    2: 35,   # TODO_VERIFY
    3: 50,   # TODO_VERIFY
    4: 70,   # TODO_VERIFY
    5: 95,   # TODO_VERIFY peak summer season
    6: 90,   # TODO_VERIFY
    7: 40,   # TODO_VERIFY monsoon
    8: 35,   # TODO_VERIFY monsoon
    9: 45,   # TODO_VERIFY
    10: 70,  # TODO_VERIFY festival season
    11: 55,  # TODO_VERIFY
    12: 65,  # TODO_VERIFY winter holidays
}

WEEKEND_UPLIFT = 10   # added on Saturday and Sunday  # TODO_VERIFY
HOLIDAY_UPLIFT = 15   # added on a holiday or long-weekend day  # TODO_VERIFY

# Public holidays and long weekends, Oct-Dec 2026. Inclusive date ranges.
HOLIDAYS: list[tuple[date, date, str]] = [
    (date(2026, 10, 2), date(2026, 10, 4), "Gandhi Jayanti long weekend"),  # TODO_VERIFY
    (date(2026, 10, 20), date(2026, 10, 20), "Dussehra"),  # TODO_VERIFY
    (date(2026, 11, 8), date(2026, 11, 8), "Diwali"),  # TODO_VERIFY
    (date(2026, 11, 24), date(2026, 11, 24), "Guru Nanak Jayanti"),  # TODO_VERIFY
    (date(2026, 12, 25), date(2026, 12, 27), "Christmas long weekend"),  # TODO_VERIFY
    (date(2026, 12, 31), date(2026, 12, 31), "New Year's Eve"),  # TODO_VERIFY
]


def date_demand(d: date) -> tuple[int, list[str]]:
    """Return (score, notes) for a travel date. Score is clamped to 0-100."""
    score = MONTH_DEMAND[d.month]
    notes = [f"Season demand for {d.strftime('%B')} is a curated estimate ({score})"]

    if d.weekday() >= 5:  # Saturday or Sunday
        score += WEEKEND_UPLIFT
        notes.append(f"Weekend uplift (+{WEEKEND_UPLIFT})")

    for start, end, name in HOLIDAYS:
        if start <= d <= end:
            score += HOLIDAY_UPLIFT
            notes.append(f"Holiday or long weekend: {name} (+{HOLIDAY_UPLIFT})")
            break

    if not (date(2026, 10, 1) <= d <= date(2026, 12, 31)):
        notes.append("Holiday calendar covers Oct-Dec 2026 only")

    return max(0, min(100, score)), notes
