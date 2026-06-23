# NBA Draft Milestone Agent DB

Deterministic FastAPI + PostgreSQL system for NBA draft milestone answers.

The API stores normalized player, combine, and draft-board data, builds dated
snapshots, and computes all seven milestone answers from snapshot tables with
SQL. No answer depends on LLM reasoning.

## Run with Docker

```bash
docker compose up --build
```

The API starts on `http://localhost:8000`.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
export DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/nbadraft"
alembic upgrade head
uvicorn app.main:app --reload
```

## Load Excel Data

```bash
python -m app.etl data.xlsx \
  --snapshot-date 2026-06-01 \
  --source "manual-import" \
  --board-type projected
```

The loader accepts common column names such as `name`, `player`, `position`,
`country`, `school`, `pick`, `rank`, `height`, `wingspan`, `weight`,
`vertical`, `sprint`, `hand_length`, and `hand_width`.

## Compute Answers

```bash
curl -X POST http://localhost:8000/milestone/compute \
  -H "Content-Type: application/json" \
  -d '{"snapshot_date":"2026-06-01","mode":"projected"}'
```

## Snapshot Debug

```bash
curl "http://localhost:8000/snapshot/2026-06-01?mode=projected"
```

## Milestone Questions

- Q1: picks 4-14 with wingspan minus height at least 5 inches.
- Q2: top 3 max vertical players who are in the first round.
- Q3: centers in the first round.
- Q4: first center pick from 4-30.
- Q5: international players in the first round.
- Q6: school with the most first-round players.
- Q7: top 5 hand-length players who are in the first round.
