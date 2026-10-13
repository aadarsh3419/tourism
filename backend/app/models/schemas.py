"""PahadPath API contract (Pydantic v2).

This file is the single source of truth for field names. If a field changes,
change frontend/src/services/types.ts in the same commit.

Design notes
- Request models use extra="forbid": unknown fields are a 422, not ignored.
- Record/response models use extra="ignore" so a repository dict with an
  internal column (for example `enabled`) never breaks serialization.
- Dates are real `date` objects; they serialize to "YYYY-MM-DD" in JSON.
"""
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

# Interest tags the UI offers and the backend accepts. Keep in sync with types.ts.
ALLOWED_TAGS: tuple[str, ...] = (
    "nature",
    "village",
    "local_food",
    "temples",
    "trekking",
    "quiet",
)

MAX_INTERESTS = 8
MAX_DAYS = 7
MAX_PLAN_DESTINATIONS = 3  # the Results page lets the user pick up to 3

DataMode = Literal["curated_rule_estimate"]
CrowdLevel = Literal["Quiet", "Moderate", "Busy", "Very busy"]
GenerationMode = Literal["llm_validated", "template"]
TimeBlock = Literal["morning", "afternoon", "evening"]
ReadinessStatus = Literal["ready_to_plan", "needs_confirmation", "restriction_reported"]
ReportType = Literal["access", "transport", "crowd_observation", "service", "weather_note"]
VerificationStatus = Literal["unverified", "reviewed", "rejected"]


def crowd_level_for(score: int) -> CrowdLevel:
    """Single definition of the label bands: 0-34, 35-59, 60-79, 80-100."""
    if score <= 34:
        return "Quiet"
    if score <= 59:
        return "Moderate"
    if score <= 79:
        return "Busy"
    return "Very busy"


def _validate_tags(tags: list[str]) -> list[str]:
    """Lower-case, de-duplicate (keeping order) and check against ALLOWED_TAGS."""
    cleaned: list[str] = []
    for tag in tags:
        t = tag.strip().lower()
        if t not in ALLOWED_TAGS:
            raise ValueError(f"unknown interest tag: {t!r}. Allowed: {', '.join(ALLOWED_TAGS)}")
        if t not in cleaned:
            cleaned.append(t)
    return cleaned


def _not_in_past(value: date) -> date:
    if value < date.today():
        raise ValueError("start_date must not be in the past")
    return value


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class _Record(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------


class ErrorDetail(_Record):
    code: str = Field(max_length=64)
    message: str = Field(max_length=500)
    request_id: str | None = None


class ErrorResponse(_Record):
    """Wire format of every error: {"detail": {"code": "...", "message": "..."}}"""

    detail: ErrorDetail


# --------------------------------------------------------------------------
# Catalogue records
# --------------------------------------------------------------------------


class Destination(_Record):
    id: int
    name: str
    district: str | None = None
    region: str = "Uttarakhand"
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    best_months: list[int] = Field(default_factory=list)  # 1-12
    baseline_popularity: int = Field(ge=0, le=100)
    # Readiness inputs. Blank means "unknown", never "fine".
    access_notes: str = ""
    last_mile_notes: str = ""
    connectivity_notes: str = ""
    readiness_source_label: str | None = None
    readiness_reviewed_at: date | None = None
    source_label: str
    reviewed_at: date
    alternative_ids: list[int] = Field(default_factory=list)

    @field_validator("best_months")
    @classmethod
    def _months(cls, v: list[int]) -> list[int]:
        if any(m < 1 or m > 12 for m in v):
            raise ValueError("best_months must contain month numbers 1-12")
        return v


class Homestay(_Record):
    id: int
    destination_id: int
    name: str
    village: str = ""
    # None means "not provided". The UI shows "Price on request".
    price_min: int | None = Field(default=None, ge=0)
    price_max: int | None = Field(default=None, ge=0)
    currency: str = "INR"
    # Repository must return None unless the host agreed to publish (publish_contact=1).
    public_contact: str | None = None
    booking_url: str | None = None
    amenities: list[str] = Field(default_factory=list)
    source_label: str
    reviewed_at: date

    @model_validator(mode="after")
    def _price_range(self) -> "Homestay":
        if (
            self.price_min is not None
            and self.price_max is not None
            and self.price_min > self.price_max
        ):
            raise ValueError("price_min must be <= price_max")
        return self

    @field_validator("booking_url")
    @classmethod
    def _https_only(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith("https://"):
            raise ValueError("booking_url must start with https://")
        return v


# --------------------------------------------------------------------------
# Crowd estimate, readiness, LocalPulse
# --------------------------------------------------------------------------


class CrowdComponents(_Record):
    baseline_popularity: int = Field(ge=0, le=100)
    date_demand: int = Field(ge=0, le=100)
    event_pressure: int = Field(ge=0, le=100)
    weather_visit_tendency: int = Field(ge=0, le=100)


class CrowdResult(_Record):
    score: int = Field(ge=0, le=100)
    level: CrowdLevel
    mode: DataMode = "curated_rule_estimate"
    components: CrowdComponents
    notes: list[str] = Field(default_factory=list)
    reviewed_at: date

    @model_validator(mode="after")
    def _level_matches_score(self) -> "CrowdResult":
        if self.level != crowd_level_for(self.score):
            raise ValueError(f"level {self.level!r} does not match score {self.score}")
        return self


class LocalPulseReport(_Record):
    id: int
    report_type: ReportType
    summary: str
    source_label: str
    source_url: str | None = None
    observed_at: date
    reviewed_at: date
    expires_at: date | None = None
    verification_status: VerificationStatus
    # Derived by the service from expires_at; never stored.
    is_stale: bool = False


class TripReadinessResult(_Record):
    """A planning aid, not a safety certificate."""

    status: ReadinessStatus
    reasons: list[str] = Field(default_factory=list)
    reviewed_at: date | None = None
    evidence: list[LocalPulseReport] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Recommendations
# --------------------------------------------------------------------------


class RecommendationRequest(_Request):
    region: str = Field(default="Uttarakhand", min_length=1, max_length=60)
    start_destination_id: int | None = Field(default=None, ge=1)
    start_date: date
    days: int = Field(ge=1, le=MAX_DAYS)
    interests: list[str] = Field(default_factory=list, max_length=MAX_INTERESTS)
    budget_per_night_max: int | None = Field(default=None, ge=0, le=1_000_000)
    avoid_crowds: bool = True
    max_drive_hours: float | None = Field(default=None, ge=0, le=12)

    @field_validator("start_date")
    @classmethod
    def _date_ok(cls, v: date) -> date:
        return _not_in_past(v)

    @field_validator("interests")
    @classmethod
    def _interests_ok(cls, v: list[str]) -> list[str]:
        return _validate_tags(v)


class ScoreComponents(_Record):
    interest_fit: float = Field(ge=0, le=100)
    quietness_fit: float = Field(ge=0, le=100)
    travel_fit: float = Field(ge=0, le=100)
    homestay_fit: float = Field(ge=0, le=100)


class Recommendation(_Record):
    destination_id: int
    name: str
    rank_score: float = Field(ge=0, le=100)
    crowd: CrowdResult
    score_components: ScoreComponents
    shared_tags: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(min_length=1)  # FR-02: every result has a reason
    reviewed_at: date
    readiness: TripReadinessResult


class RecommendationResponse(_Record):
    request_id: str
    data_mode: DataMode = "curated_rule_estimate"
    start_crowd: CrowdResult | None = None  # estimate for the crowded starting place
    recommendations: list[Recommendation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Itineraries
# --------------------------------------------------------------------------


class ItineraryRequest(_Request):
    start_date: date
    days: int = Field(ge=1, le=MAX_DAYS)
    destination_ids: list[int] = Field(min_length=1, max_length=MAX_PLAN_DESTINATIONS)
    interests: list[str] = Field(default_factory=list, max_length=MAX_INTERESTS)
    budget_per_night_max: int | None = Field(default=None, ge=0, le=1_000_000)
    use_ai: bool = False

    @field_validator("start_date")
    @classmethod
    def _date_ok(cls, v: date) -> date:
        return _not_in_past(v)

    @field_validator("interests")
    @classmethod
    def _interests_ok(cls, v: list[str]) -> list[str]:
        return _validate_tags(v)

    @field_validator("destination_ids")
    @classmethod
    def _ids_ok(cls, v: list[int]) -> list[int]:
        if any(i < 1 for i in v):
            raise ValueError("destination_ids must be positive integers")
        if len(set(v)) != len(v):
            raise ValueError("destination_ids must not contain duplicates")
        return v


class ItineraryItem(_Record):
    time_block: TimeBlock
    destination_id: int
    destination_name: str
    activity_text: str = Field(max_length=300)
    reason: str = Field(max_length=200)
    crowd: CrowdResult


class ItineraryDay(_Record):
    date: date
    items: list[ItineraryItem] = Field(min_length=1, max_length=6)


class ItineraryResponse(_Record):
    request_id: str
    generation_mode: GenerationMode
    data_mode: DataMode = "curated_rule_estimate"
    days: list[ItineraryDay] = Field(min_length=1, max_length=MAX_DAYS)
    homestay_ids: list[int] = Field(default_factory=list)
    # Resolved records, so the app can save everything it needs for offline use.
    destinations: list[Destination] = Field(default_factory=list)
    homestays: list[Homestay] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _homestays_consistent(self) -> "ItineraryResponse":
        if set(self.homestay_ids) != {h.id for h in self.homestays}:
            raise ValueError("homestay_ids must match the ids of the homestays list")
        return self


# --------------------------------------------------------------------------
# Stretch: Hinglish request parser (Part 2.9)
# --------------------------------------------------------------------------


class ParseRequestBody(_Request):
    text: str = Field(min_length=1, max_length=300)


class ParseRequestResponse(_Record):
    days: int | None = Field(default=None, ge=1, le=MAX_DAYS)
    interests: list[str] = Field(default_factory=list, max_length=MAX_INTERESTS)
    budget_per_night_max: int | None = Field(default=None, ge=0, le=1_000_000)
    start_destination_id: int | None = Field(default=None, ge=1)

    @field_validator("interests")
    @classmethod
    def _interests_ok(cls, v: list[str]) -> list[str]:
        return _validate_tags(v)
