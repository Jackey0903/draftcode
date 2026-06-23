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
| Data science innovation | Ready for roadshow | Milestone-Aware Draft Twin is documented as the main insight. |
| Official event data | Local only | Official Excel/CSV/video files are present locally but intentionally not committed. |
| Final scoring pipeline | In progress | Need official data normalizer, Q1-Q7 milestone calculators, answer-card writer, and final 30-pick run. |
| Cloud deployment | Optional/in progress | `sam validate` passes; first `sam build` may need Lambda base-image pre-pull on stable network. |

Immediate next build priorities:

1. Normalize official files into `data/processed/` tables.
2. Implement Q1-Q7 milestone calculators from the official answer template.
3. Generate the final answer workbook from agent outputs.
4. Add Monte Carlo scenario simulation if time allows.
5. Deploy the SAM stack only after the local scoring pipeline is correct.

## Quick start

```bash
make install
make test
make predict
make validate-sample
make report
```

The sample run writes:

- `outputs/predictions.csv`
- `outputs/trace.json`
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

- `src/draftcode/`: prediction agent, CLI, API, dashboard, Lambda handler.
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
draftcode predict --data-dir data/processed --output outputs/predictions.csv --trace outputs/trace.json
draftcode validate-output --predictions outputs/predictions.csv --expected-picks 30
draftcode render-report --predictions outputs/predictions.csv --output outputs/report.html
```
