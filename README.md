# DraftCode

NBA draft prediction agent for the AWS DraftCode hackathon at AWS Summit Shanghai 2026.

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

## Competition commands

```bash
draftcode predict --data-dir data/processed --output outputs/predictions.csv --trace outputs/trace.json
draftcode validate-output --predictions outputs/predictions.csv --expected-picks 30
draftcode render-report --predictions outputs/predictions.csv --output outputs/report.html
```
