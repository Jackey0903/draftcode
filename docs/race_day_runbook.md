# Race-day runbook

## 2026-06-23 08:00 to 09:00

- Download official milestone questions and Portal data immediately.
- If milestone questions are not visible at 08:00, check again at 21:00 because the training notes and guide use different wording.
- Put raw files under `data/raw/`.
- Convert them into the four normalized CSVs under `data/processed/`.
- Run a smoke test with `draftcode predict --data-dir data/processed`.
- Commit and push the data adapters and first working prediction trace.

## 2026-06-23 09:00 to 13:00

- Build ingestion for every allowed data source.
- Produce a baseline full first-round prediction.
- Add validation that the answer card has every required field.
- Keep a running `outputs/trace.json` for explainability.

## 2026-06-23 13:00 to 18:00

- Improve feature weights using historical draft backtesting if historical data is available.
- Add mock-draft/source confidence weighting.
- Build dashboard views for pick table, confidence, and top alternatives.
- Keep pushing every significant working state.

## 2026-06-23 18:00 to 23:00

- Freeze a strong baseline.
- Add AWS/SAM demo path only after local prediction is stable.
- Draft roadshow PPT around prediction logic, not feature count.
- Record a sub-60-second demo video.

## 2026-06-24 00:00 to 06:30

- Re-run model with latest allowed public information.
- Generate final `predictions.csv` and `trace.json`.
- Fill answer card from generated output.
- Prepare fallback screenshots in case Wi-Fi or deployment fails.

## 2026-06-24 06:30 to 08:00

- Submit early. Target 2026-06-24 07:30 latest internal cutoff.
- Push final GitHub code before submission; the training notes say code push is part of the 08:00 cutoff package.
- Verify submitted status in the Portal.
- Do not keep changing the answer after the final verified submission unless there is a clear, high-confidence data correction.

## Roadshow script shape

1. Problem: predicting team-player matches under uncertain draft dynamics.
2. Agent: data ingestion, scoring, sequential simulation, trace.
3. Evidence: board rank, slot fit, team need, market/mock signals.
4. AWS: serverless deployable API, IaC, logs, security posture.
5. Result: show final picks and one or two high-impact decision traces.
