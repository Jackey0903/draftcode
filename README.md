# DraftCode

NBA draft prediction agent for the AWS DraftCode hackathon at AWS Summit Shanghai 2026.

## Current readiness

Last checked: 2026-06-23 Shanghai time.

| Area | Status | Notes |
| --- | --- | --- |
| GitHub | Ready | `Jackey0903/draftcode` is `PRIVATE`; `main` is pushed. |
| Local environment | Ready | Python 3.11, uv, Docker, AWS CLI, SAM CLI, GitHub CLI, Node/npm, and Kiro CLI are installed. |
| AWS CLI | Ready, with caveat | `aws sts get-caller-identity` works. Current CLI identity is root; replace with IAM/SSO after the hackathon. |
| Core agent scaffold | Ready | CLI, deterministic predictor, trace output, sample data, tests, API, Lambda handler, and HTML report exist. |
| AWS architecture | Ready as blueprint | SAM validates S3, DynamoDB, API Gateway, Step Functions, Lambda container image, tracing, and Bedrock permissions. |
| AWS tool innovation | Ready for roadshow | Evidence Ledger, Scenario Swarm, and Explanation Firewall are documented. |
| Data science innovation | Implemented (local) | Milestone-Aware Draft Twin Monte Carlo engine on **real 2026 data**: per-pick probability distributions, true confidence, **all 7 milestones (Q1-Q7)** with P10-P90 bands, and **Hungarian assignment** for a no-duplicate 30-pick board. |
| Official event data | Local only | Official Excel/CSV/video files present locally (copied into `data/raw/official/`, gitignored) but intentionally not committed. |
| Final scoring pipeline | Implemented (local) | Official normalizer (`ingest`), Q1-Q7 calculators, Hungarian-assigned 30-pick board, and answer-card writer (`answer`) all shipped; `outputs/answer_card.xlsx` generates end-to-end. |
| Cloud deployment | Optional/in progress | `sam validate` passes; first `sam build` may need Lambda base-image pre-pull on stable network. |

Immediate next build priorities:

1. ✅ Normalize official files into `data/processed/` tables — `draftcode ingest` / `make ingest`.
2. ✅ Q1-Q7 milestone calculators from the official answer template — computed inside the Monte Carlo engine on real combine fields.
3. ✅ Generate the final answer workbook — `draftcode answer` / `make answer` writes `outputs/answer_card.xlsx` (30-pick board + Q1-Q7).
4. ✅ Monte Carlo scenario simulation with Hungarian assignment — `draftcode simulate` / `make simulate`.
5. Next: enrich production signals (combine shooting), team needs + mock signals, divergence reasoning (talent vs ESPN), then deploy the SAM stack.

## Quick start

```bash
make install
make test
make predict
make simulate
make validate-sample
make report
```

The sample run writes:

- `outputs/predictions.csv`
- `outputs/trace.json`
- `outputs/twin.json` (Monte Carlo Draft Twin: per-pick distributions + milestone answers)
- `outputs/report.html`

Sample data under `data/sample/` is synthetic and only verifies the pipeline. Replace it with Team Portal and public NBA data during the competition.

## Environment

```bash
scripts/check_env.sh
make sam-validate
```

Required manual logins:

- `gh auth login`
- `aws configure sso` or `aws configure`
- Start Docker Desktop before SAM local builds.

AWS deployment helpers:

```bash
make sam-pull-base
make sam-build
```

## Project map

- `src/draftcode/`: prediction agent, CLI, API, dashboard, Lambda handler, Monte Carlo Draft Twin (`simulate.py`), official-data normalizer (`official.py`), answer-card writer (`answer.py`).
- `data/raw/official/`: official 2026 source workbooks (gitignored); `data/processed/`: normalized tables from `ingest`.
- `data/sample/`: synthetic smoke-test CSVs.
- `data/reference/`: small verified reference anchors from training notes.
- `infra/template.yaml`: AWS SAM serverless API template.
- `docs/competition_analysis.md`: contest analysis and hard constraints.
- `docs/prep_checklist.md`: account, tooling, and submission checklist.
- `docs/race_day_runbook.md`: 24-hour execution plan.
- `docs/nba_model_strategy.md`: data science strategy for NBA draft prediction.
- `docs/architecture.md`: AWS serverless architecture and roadshow talk track.
- `docs/aws_scorecard.md`: mapping from AWS scoring language to concrete implementation.
- `docs/innovation_strategy.md`: Milestone-Aware Draft Twin concept and build priorities.
- `docs/aws_tool_innovation.md`: AWS tool-level innovation patterns.

## Competition commands

```bash
# 1) Normalize official 2026 workbooks -> data/processed/
draftcode ingest --source data/raw/official --out data/processed
# 2) Monte Carlo Draft Twin: distributions + Q1-Q7 milestones + Hungarian board
draftcode simulate --data-dir data/processed --output outputs/twin.json --draws 1000 --seed 42
# 3) Write the submittable answer card (30-pick board + 7 milestones)
draftcode answer --data-dir data/processed --template data/raw/official/answer_card_template.xlsx --out outputs/answer_card.xlsx --draws 1000 --seed 42 --team-id Team01
```
