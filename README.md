# PahadPath

Uttarakhand-first trip planner that suggests quieter alternatives to crowded
destinations, builds a short itinerary, and saves it for offline use.
One-day hackathon MVP.

> **Status: early draft.** The contract, database schema and *draft* seed data
> exist. Services, API routes and the frontend are not built yet.
> Seed data is **not human-verified**; see "Data honesty" below.

## What exists so far

| Path | What it is |
| --- | --- |
| `backend/app/models/schemas.py` | Pydantic v2 API contract (single source of truth for field names) |
| `frontend/src/services/types.ts` | TypeScript mirror of the contract |
| `backend/app/models/database.py` | SQLite schema (5 tables) |
| `backend/app/data/seed_demo_data.py` | Draft seed data (12 places, 11 links, 10 disabled stay placeholders) and a validating loader |
| `backend/app/data/date_demand.py` | Curated month / weekend / holiday demand rules |
| `frontend/src/mocks/sample_responses.json` | Placeholder responses for building the UI before the API exists |
| `docs/MASTER_CONTEXT.md` | Rules to paste at the start of every AI-assistant chat |

## Run the tests and seed the database

```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
pytest                                  # contract, seed and date-demand tests
python -m app.data.seed_demo_data       # creates pahadpath.db
python -m app.data.seed_demo_data --strict   # fails while any TODO_VERIFY remains
```

## Data honesty

- Crowd scores are **curated rule-based estimates**, not live measurements or validated forecasts.
- Every record carries `source_label` and `reviewed_at`. In the current draft,
  `reviewed_at` is a placeholder date: a person has not reviewed these records yet.
- Homestay rows are disabled placeholders. No host names, prices, phone numbers or booking links are invented.
- No LocalPulse reports are seeded, so every destination reads "needs confirmation" for readiness.
- Before any demo, a team member checks each record against official tourism pages
  or local knowledge and removes its `TODO_VERIFY` comment. `--strict` enforces this.
