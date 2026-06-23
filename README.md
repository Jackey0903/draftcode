# DraftCode

NBA draft prediction agent for the AWS DraftCode hackathon at AWS Summit Shanghai 2026.

## Current readiness

Last checked: 2026-06-23 Shanghai time.

| Area | Status | Notes |
| --- | --- | --- |
| GitHub | Ready | `Jackey0903/draftcode` is `PRIVATE`; `main` is pushed. |
| Local environment | Ready | Python 3.11, uv, Docker, AWS CLI, SAM CLI, GitHub CLI, Node/npm, and Kiro CLI are installed. |
| AWS CLI | Local validation only this round | Authenticate with IAM/SSO before running deploy, upload, or Step Functions commands. |
| Core agent scaffold | Ready | CLI, deterministic predictor, trace output, sample data, tests, API, Lambda handler, and HTML report exist. |
| AWS architecture | Ready as blueprint | SAM validates S3, DynamoDB, API Gateway, Step Functions, Lambda container image, tracing, and Bedrock permissions. |
| AWS tool innovation | Ready for roadshow | Evidence Ledger and Scenario Swarm are implemented in SAM; Explanation Firewall is documented. |
| Data science innovation | Implemented (local) | Milestone-Aware Draft Twin Monte Carlo engine on **real 2026 data**: per-pick probability distributions, true confidence, **all 7 milestones (Q1-Q7)** with P10-P90 bands, and **Hungarian assignment** for a no-duplicate 30-pick board. |
| Official event data | Local only | Official Excel/CSV/video files present locally (copied into `data/raw/official/`, gitignored) but intentionally not committed. |
| Final scoring pipeline | Implemented (local) | Official normalizer (`ingest`), Q1-Q7 calculators, Hungarian-assigned 30-pick board, and answer-card writer (`answer`) all shipped; `outputs/answer_card.xlsx` generates end-to-end. |
| Cloud deployment | Optional/in progress | `sam validate` passes; SAM workflow now invokes `simulate` and can read processed CSVs from S3 when configured. |

Immediate next build priorities:

1. ✅ Normalize official files into `data/processed/` tables — `draftcode ingest` / `make ingest`.
2. ✅ Q1-Q7 milestone calculators from the official answer template — computed inside the Monte Carlo engine on real combine fields.
3. ✅ Generate the final answer workbook — `draftcode answer` / `make answer` writes `outputs/answer_card.xlsx` (30-pick board + Q1-Q7).
4. ✅ Monte Carlo scenario simulation with Hungarian assignment — `draftcode simulate` / `make simulate`.
5. Next: enrich production signals and deploy the SAM stack.

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

## Local gpt-5.5 warroom

Bedrock is not required for the local agent path. DraftCode calls gpt-5.5 through the
local Codex CLI reverse proxy:

```bash
codex exec --skip-git-repo-check --ephemeral -c sandbox_mode="read-only" -o <OUTFILE> "<PROMPT>"
```

`src/draftcode/llm_client.py` wraps that command with standard-library
`subprocess` and returns `None` on timeout, missing Codex, disabled LLM, or any
non-zero exit. Set `DRAFTCODE_LLM_DISABLED=1` to force the deterministic fallback path.

The local war-room pipeline is LLM-once: it writes JSON cache artifacts first, then
the simulator reads the persisted GM deltas from `outputs/llm/gm_preferences.json`
for a deterministic run. `draftcode simulate` reads that path by default through
`--gm-preferences`; if the file is missing or invalid, it prints the disabled
status and falls back to the pure deterministic dossier scorer.

```bash
draftcode warroom --data-dir data/processed --output-dir outputs/llm --draws 1000 --seed 42

# CI/offline smoke path: no external LLM calls
draftcode warroom --data-dir data/processed --output-dir outputs/llm --draws 1000 --seed 42 --offline

# Replay the cached GM preferences without calling an LLM
draftcode simulate --data-dir data/processed --output outputs/twin.json --gm-preferences outputs/llm/gm_preferences.json
```

Artifacts:

- `outputs/llm/gm_preferences.json`: 30 team GM-agent preference deltas.
- `outputs/llm/explanations.json`: pick-by-pick war-room notes.
- `outputs/llm/redteam.json`: board and milestone challenges.

GM preference scoring is intentionally conservative: for each team-prospect edge,
the Monte Carlo engine computes the deterministic dossier `preference_score`, then
adds `0.50 * gm_delta`, where `gm_delta` is clamped to `[-0.08, 0.08]`. The trace
records the raw delta, fixed weight, and weighted score adjustment for audit.

## 创新点1: gpt-5.5 双信号背离

`draftcode ingest` now adjudicates large handbook talent-vs-market splits
(`abs(divergence_gap) >= 8`) through a deterministic cache at
`data/processed/divergence_llm.json`. If gpt-5.5 returns a verdict, ingest blends
the model's existing rule weight with `adjusted_market_weight` by `confidence`,
then writes the verdict, weight, confidence, and reasoning into `prospects.csv`
and `divergence.json`. Use `--no-divergence-llm` for a byte-for-byte deterministic
fallback with the original rule fusion.

Peterson example: 达林·彼得森 is flagged because `talent_rank=14` sits far below
`market_rank=1.5`, so the deterministic rule labels the split `market_hype`. Given
only neutral measurables (the rule verdict is never leaked into the prompt),
gpt-5.5 instead returned `talent_undervalued` — judging the talent rank too
conservative for an efficient, high-usage big guard with credible playmaking — and
raised the market weight (w=0.65, confidence 0.64). His consensus rank moves 5 → 4:
a measured correction, not a full jump to the market's #2, because the prospects
ranked above him score higher on **both** signals.

## Real-time intel agent

The intel agent turns externally fetched news text into draft-order and team-need
updates. Fetching is intentionally outside the engine: WebFetch, crawlers, APIs,
or a manual operator inject text through `--news-text` or `--news-file`.

The flow is capture -> structure -> apply:

1. Capture: external tooling supplies the news excerpt and source label.
2. Structure: gpt-5.5 extracts `picks_moved_2026_round1`, `team_needs_delta`, and
   `affects_our_draft_order` into an `IntelReport`.
3. Apply: DraftCode previews by default, writes `draft_order.csv`/`team_needs.csv`
   only with `--apply`, and always writes `outputs/intel/intel_<seq>.json`.

Validated Giannis case: "Heat acquire Giannis from Bucks; Milwaukee gets the
No. 13 pick in 2026" normalizes to `PickMove(13, "MIA", "MIL")`. Dry-run previews
pick 13 as MIA -> MIL; `--apply` writes `Milwaukee Bucks,MIL`, sets
`via_trade=true`, and preserves `original_team=MIA`.

```bash
draftcode intel --news-text "Heat acquire Giannis from Bucks; Milwaukee gets the No. 13 pick in 2026"
draftcode intel --news-text "Heat acquire Giannis from Bucks; Milwaukee gets the No. 13 pick in 2026" --apply
```

Full architecture notes: `docs/intel_agent.md`.

## Market capture agent

The market agent turns multiple externally fetched mock drafts into consensus
market signals. Fetching remains outside DraftCode: WebFetch, crawlers, APIs, or
manual operators inject plain text files, and the engine only extracts, aggregates,
previews, applies, and audits.

The flow is capture -> extract -> aggregate -> apply:

1. Capture: external tooling saves ESPN/CBS/Ringer/NBA.com mock text.
2. Extract: gpt-5.5 maps English player names to the Chinese `prospects.csv`
   name pool and returns `player -> projected_pick` JSON per source.
3. Aggregate: DraftCode averages each matched player across sources into
   `consensus_pick`, `n_sources`, and source labels.
4. Apply: DraftCode previews by default, writes `prospects.csv.market_rank` and
   rewrites `mock_signals.csv` only with `--apply`, and always writes
   `outputs/market/market_<seq>.json`.

```bash
draftcode market --mock-file ESPN=data/raw/mocks/espn.txt --mock-file CBS=data/raw/mocks/cbs.txt
draftcode market --mock-dir data/raw/mocks --apply
```

If an LLM call fails or returns invalid JSON, that source is skipped. If all
sources fail, the report is empty and `--apply` leaves existing CSV files
untouched.

Full architecture notes: `docs/market_agent.md`.

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

## S3 simulation data flow

The single-Lambda cloud path remains available:

```text
draftcode ingest -> data/processed -> draftcode upload-data -> S3 processed prefix
  -> Step Functions GeneratePrediction -> Lambda downloads four CSVs from S3
  -> simulate -> S3 runs/<run_id>/twin.json + DynamoDB run summary
```

Required processed inputs are `prospects.csv`, `draft_order.csv`, `team_needs.csv`, and `mock_signals.csv`. If `DRAFTCODE_DATA_S3_PREFIX` is empty, or if boto3/AWS access is unavailable locally, Lambda falls back to `DRAFTCODE_DATA_DIR`.

Scenario Swarm uses the same data prefix but fans out Monte Carlo work with Step Functions Distributed Map:

```text
ScenarioSwarmWorkflow
  -> PrepareRun Lambda action=prepare_swarm creates run_id and N shard payloads
  -> Distributed Map action=simulate_shard writes runs/<run_id>/shards/<index>.json
  -> Aggregate Lambda action=aggregate reads all shard JSON, merges raw counts
  -> S3 runs/<run_id>/twin.json + DynamoDB run summary
```

Each shard uses an independent deterministic random stream:
`seed + shard_index * 1000003`. A single shard with `shard_index=0` is byte-for-byte equivalent to the original `run()` output for the same draw count.

Upload processed data after the stack creates the bucket:

```bash
draftcode upload-data --source data/processed --bucket <bucket> --prefix processed
# or
make upload-data S3_BUCKET=<bucket> DATA_S3_PREFIX=processed
```

After AWS authentication, deploy and run in this order:

```bash
make install-full
make ingest
SAM_CLI_TELEMETRY=0 sam validate --template-file infra/template.yaml --region us-east-1
make sam-deploy STACK_NAME=draftcode AWS_REGION=us-east-1 DATA_S3_PREFIX=processed DRAFTCODE_DRAWS=1000 DRAFTCODE_SEED=42
export DRAFTCODE_S3_BUCKET=$(aws cloudformation describe-stacks --stack-name draftcode --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='DraftDataBucketName'].OutputValue" --output text)
make upload-data S3_BUCKET="$DRAFTCODE_S3_BUCKET" DATA_S3_PREFIX=processed
export DRAFTCODE_WORKFLOW_ARN=$(aws cloudformation describe-stacks --stack-name draftcode --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='PredictionWorkflowArn'].OutputValue" --output text)
aws stepfunctions start-execution --state-machine-arn "$DRAFTCODE_WORKFLOW_ARN" --region us-east-1
```

Trigger Scenario Swarm after the same authenticated deploy and data upload:

```bash
export SCENARIO_SWARM_WORKFLOW_ARN=$(aws cloudformation describe-stacks --stack-name draftcode --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='ScenarioSwarmWorkflowArn'].OutputValue" --output text)
aws stepfunctions start-execution \
  --state-machine-arn "$SCENARIO_SWARM_WORKFLOW_ARN" \
  --region us-east-1 \
  --input '{"total_draws":1000,"shard_count":10}'
```

The default swarm configuration is 10 shards with `total_draws // shard_count` draws per shard. With the defaults, that is 10 parallel shards x 100 draws = 1000 aggregated draws.

## Project map

- `src/draftcode/`: prediction agent, CLI, API, dashboard, Lambda handler, Monte Carlo Draft Twin (`simulate.py`), official-data normalizer (`official.py`), answer-card writer (`answer.py`).
- `data/raw/official/`: official 2026 source workbooks (gitignored); `data/processed/`: normalized tables from `ingest`.
- `data/sample/`: synthetic smoke-test CSVs.
- `data/reference/`: small verified reference anchors from training notes.
- `infra/template.yaml`: AWS SAM serverless API template, including the single-run workflow and the Distributed Map Scenario Swarm workflow.
- `docs/competition_analysis.md`: contest analysis and hard constraints.
- `docs/prep_checklist.md`: account, tooling, and submission checklist.
- `docs/race_day_runbook.md`: 24-hour execution plan.
- `docs/nba_model_strategy.md`: data science strategy for NBA draft prediction.
- `docs/architecture.md`: AWS serverless architecture and roadshow talk track.
- `docs/aws_scorecard.md`: mapping from AWS scoring language to concrete implementation.
- `docs/innovation_strategy.md`: Milestone-Aware Draft Twin concept and build priorities.
- `docs/intel_agent.md`: real-time trade intel extraction, application, and audit flow.
- `docs/market_agent.md`: multi-source mock draft market extraction and signal application flow.
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
