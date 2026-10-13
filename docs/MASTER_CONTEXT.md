# Master Context (paste first in every new AI chat)

PROJECT: PahadPath - Uttarakhand-first trip planner that suggests quieter
alternatives to crowded destinations, builds a short itinerary, and saves it
for offline use. One-day hackathon MVP.

STACK: Frontend: React + Vite + TypeScript, PWA (service worker + IndexedDB via
the idb library). Backend: Python 3.11+, FastAPI, Pydantic v2, SQLite (sqlite3),
pytest. LLM: optional, called server-side only.

STRUCTURE:
```
backend/app/models/{schemas.py,database.py}
backend/app/data/{seed_demo_data.py,date_demand.py}
backend/app/services/   (crowd_score, similarity, itinerary)   <- to build
backend/app/api/        (trips, destinations, homestays)       <- to build
backend/tests/
frontend/src/{services/types.ts,mocks/,pages/,components/,offline/}
docs/
```

NON-NEGOTIABLE RULES
1. Backend owns all scoring. The frontend only displays results.
2. Crowd score is deterministic: round(0.35*baseline_popularity +
   0.30*date_demand + 0.20*event_pressure + 0.15*weather_visit_tendency),
   clamped 0-100. Missing inputs default to 50 and add a note.
3. Ranking: rank_score = 0.45*interest_fit + 0.35*quietness_fit +
   0.10*travel_fit + 0.10*homestay_fit.
4. Labels: 0-34 Quiet, 35-59 Moderate, 60-79 Busy, 80-100 Very busy, always
   shown as "(estimated)". Every score carries data_mode="curated_rule_estimate"
   and reviewed_at.
5. The LLM only writes text. Every destination_id and homestay_id it returns is
   validated against the database. Never invent prices, contacts, availability,
   travel times or closures. Fall back to a template itinerary
   (generation_mode="template") if the LLM is missing or invalid.
6. Secrets live only in backend .env. No API keys in frontend code.
7. Small typed functions, comments only where logic is non-obvious. No new
   dependencies without asking.
8. Trip readiness is a planning aid, never a safety guarantee. Missing or stale
   facts become "needs_confirmation".

CONTRACT: field names live in backend/app/models/schemas.py and
frontend/src/services/types.ts. Change both in the same commit.

OUTPUT FORMAT: Give complete files (not fragments), each under its file path as
a header, then 3 lines on how to run and test it.
