# Architecture

## Goal

Produce auditable NBA draft predictions quickly under a 24-hour limit, while showing enough AWS-native engineering depth to score well on code quality.

## Local runtime

```text
CSV/Portal data
  -> loaders
  -> sequential draft predictor
  -> predictions.csv
  -> trace.json
  -> dashboard/API/answer card
```

The first version is deterministic so every answer can be reproduced and defended during the roadshow.

## AWS target shape

```text
S3 raw data bucket
  -> Lambda prediction function
  -> API Gateway /predictions
  -> DynamoDB prediction runs table
  -> CloudWatch logs
  -> optional Bedrock reasoner for narrative explanations
```

The current `infra/template.yaml` starts with a Lambda + API Gateway surface. Add S3/DynamoDB once the event Portal data schema is known.

## Why this architecture fits the scoring rubric

- Serverless API demonstrates elastic, low-maintenance cloud design.
- SAM template gives infrastructure as code.
- CLI and tests keep the model reproducible locally.
- Trace JSON gives explainability and auditability.
- Dashboard gives a clear roadshow artifact.
- No secrets are committed; `.env.example` documents configuration.

## Data model

- `prospects.csv`: prospect traits, production indicators, consensus rank.
- `draft_order.csv`: pick number and team.
- `team_needs.csv`: team-position need weights.
- `mock_signals.csv`: team-prospect external signal strength with source labels.

## Next extensions

- Add source-specific weights for mock-draft sources.
- Add injury/age/risk flags.
- Add team transaction context and roster depth features.
- Add Monte Carlo runs for pick probability distribution.
- Add Bedrock-generated concise explanation after deterministic scoring.
