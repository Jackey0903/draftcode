# DraftCode AWS Architecture

## One-line design

DraftCode is a serverless, auditable NBA draft intelligence pipeline: data lands in S3, Step Functions orchestrates prediction runs, a containerized Lambda executes the deterministic agent, DynamoDB records every run, and Bedrock is reserved for grounded explanations instead of unverified final decisions.

The product innovation is the **Milestone-Aware Draft Twin**: a probabilistic simulation that predicts both the 30 pick sheet and the 7 milestone questions from the same evidence graph. See `docs/innovation_strategy.md`.

The AWS tool innovation is three cloud-native patterns: **Evidence Ledger**, **Scenario Swarm**, and **Explanation Firewall**. See `docs/aws_tool_innovation.md`.

## Architecture diagram

```mermaid
flowchart LR
    Portal["Team Portal / NBA / public data"] --> Raw["S3 raw zone"]
    Raw --> Processed["S3 processed/features zone"]
    User["Judge / team UI"] --> Api["API Gateway /predictions"]
    Api --> Lambda["Lambda container image<br/>Draft predictor"]
    Processed --> Lambda
    Event["EventBridge or manual trigger"] --> Flow["Step Functions<br/>Prediction workflow"]
    Flow --> Lambda
    Flow -. optional fanout .-> Map["Distributed Map<br/>Monte Carlo scenarios"]
    Map -. parallel invocations .-> Lambda
    Lambda --> Trace["S3 prediction artifacts<br/>CSV + trace JSON + report"]
    Flow --> Runs["DynamoDB run ledger"]
    Lambda -. grounded trace .-> Bedrock["Amazon Bedrock<br/>rationale generator"]
    Bedrock -. guarded output .-> Trace
    Lambda --> Logs["CloudWatch Logs + X-Ray traces"]
    Flow --> Logs
```

## Runtime flow

1. `draftcode ingest` normalizes official workbooks into `data/processed`.
2. `draftcode upload-data` syncs `prospects.csv`, `draft_order.csv`, `team_needs.csv`, and `mock_signals.csv` into an encrypted S3 processed prefix.
3. Step Functions starts either the single-run `PredictionWorkflow` (`action: simulate`) or the parallel `ScenarioSwarmWorkflow` (`prepare_swarm` -> Distributed Map `simulate_shard` -> `aggregate`), retries transient Lambda failures, and traces the workflow with X-Ray.
4. The Lambda container downloads the processed CSVs from S3 when `DRAFTCODE_DATA_S3_PREFIX` is set. If the prefix, boto3, or AWS access is unavailable locally, it falls back to `DRAFTCODE_DATA_DIR`.
5. The Monte Carlo Draft Twin produces the no-duplicate assigned board, per-pick probabilities, and Q1-Q7 milestone answers. In Scenario Swarm mode, each shard first writes mergeable raw counts to `runs/<run_id>/shards/<index>.json`, and the aggregate action merges those counts into one report.
6. Lambda writes `runs/<run_id>/twin.json` to S3 best-effort, and DynamoDB records a compact run summary: run ID, created time, mode, draws, average confidence, and status.
7. Bedrock is used only after scoring to turn trace evidence into short explanations. It is not the source of truth for the picks.
8. CloudWatch and X-Ray provide logs and traceability for every run.

## Local A1 warroom path

Because the current AWS account cannot use Bedrock in the target region, Phase A1
adds a local-only LLM path through the Codex CLI reverse proxy to gpt-5.5. This does
not change the cloud diagram, SAM template, HTTP gateway, or tunneling story.

```text
data/processed + team_dossiers
  -> draftcode warroom
  -> gm_agent via codex exec, cached in outputs/llm/gm_preferences.json
  -> deterministic Monte Carlo simulate reads the cached GM deltas
  -> explanation_agent writes outputs/llm/explanations.json
  -> redteam_agent writes outputs/llm/redteam.json
```

All three agents degrade to deterministic fallbacks when Codex is missing,
disabled with `DRAFTCODE_LLM_DISABLED=1`, times out, or returns invalid JSON. The
offline test path is:

```bash
draftcode warroom --data-dir data/processed --output-dir outputs/llm --offline
```

## Why this is not service stacking

| Need | AWS service | Reason |
| --- | --- | --- |
| No servers, fast demo endpoint | API Gateway + Lambda | Elastic request handling without EC2 maintenance. |
| Data science packaging | Lambda container image + ECR | Containerized build, serverless runtime, reproducible dependencies. |
| Auditable multi-step run | Step Functions | Visual workflow, retries, state, and service integrations. |
| Raw/processed artifact storage | S3 | Cheap, durable, versioned data lake for files and reports. |
| Run ledger and scoring audit | DynamoDB | Pay-per-request metadata store for run IDs, timestamps, and confidence summaries. |
| AI explanation | Amazon Bedrock | Generates judge-facing rationale from deterministic trace. |
| Safety boundary for AI text | Bedrock Guardrails | Keeps generated explanation bounded and reduces unsafe or irrelevant text risk. |
| Observability | CloudWatch + X-Ray | Logs, traces, latency, and failure diagnosis. |
| Repeatable deployment | AWS SAM | Infrastructure as code for the whole serverless stack. |

## AWS tool innovation

| Pattern | AWS tools | What is new about the usage |
| --- | --- | --- |
| Evidence Ledger | S3 + DynamoDB + CloudWatch/X-Ray | Every prediction has a versioned input snapshot, run record, output artifact, and traceable logs. |
| Scenario Swarm | Step Functions + Distributed Map target + Lambda container | The draft becomes many parallel scenarios, not one brittle mock; serverless fanout replaces fixed workers. |
| Explanation Firewall | Bedrock + Knowledge Bases target + Guardrails target | AI explains deterministic evidence; it does not silently create final picks. |

## Security posture

- No secrets in git. Runtime configuration is documented in `.env.example`.
- S3 blocks public access, enables server-side encryption, and versions inputs.
- DynamoDB uses server-side encryption, pay-per-request capacity, and point-in-time recovery.
- Lambda reserved concurrency limits accidental spend and protects downstream services.
- IAM policies are scoped to the data bucket, run table, Lambda invocation, and Bedrock model invocation.
- Bedrock is used behind a deterministic trace, so final picks remain explainable and reproducible.
- Competition note: the current CLI is authenticated as root. This is acceptable only as a short-lived hackathon setup; after the event, remove these credentials and use an IAM user or SSO profile.

## Well-Architected alignment

| Pillar | Design choice |
| --- | --- |
| Operational excellence | SAM template, Make targets, repeatable prediction command, Step Functions visual workflow. |
| Security | Least-privilege direction, S3 public-access block, encryption, no committed credentials, guarded AI explanations. |
| Reliability | Deterministic local fallback, Step Functions retries, versioned S3 data, DynamoDB point-in-time recovery. |
| Performance efficiency | Lambda for short runs; container image for consistent dependency startup; sequential simulator avoids overbuilt ML services. |
| Cost optimization | Serverless pay-per-use, DynamoDB on-demand, S3 lifecycle for intermediate artifacts, reserved concurrency. |
| Sustainability | No idle EC2/GPU instances; compute runs only when the Agent is invoked. |

## Deployment shape in this repo

Implemented now:

- `infra/template.yaml`: SAM template with S3, DynamoDB, containerized Lambda, API Gateway, the single-run Step Functions workflow, and the Distributed Map Scenario Swarm workflow.
- `Dockerfile.lambda`: Lambda container image build.
- `src/draftcode/lambda_handler.py`: supports API Gateway, direct Step Functions invocation, simulate mode, Scenario Swarm shard/aggregate actions, S3 input download, and best-effort S3/DynamoDB output writes.
- `src/draftcode/cli.py`: `upload-data` command for syncing processed CSVs to S3.
- `make sam-validate`, `make upload-data`, and `make sam-deploy`: local validation, data upload, and authenticated deployment helpers.

Next if time allows:

- Add a Bedrock explanation Lambda that reads trace JSON and emits concise pick rationales.
- Add a CloudFront-hosted static report for roadshow fallback.
- Add EventBridge schedule or manual one-click workflow execution.

## Roadshow talk track

> We did not put the model on a fixed VM. DraftCode is a serverless draft intelligence pipeline. S3 keeps every raw and processed input versioned, Step Functions makes the Agent run auditable, and the prediction engine is a containerized Lambda so we get Docker reproducibility without managing EC2. DynamoDB records every run, CloudWatch and X-Ray make failures inspectable, and Bedrock is used only to explain the deterministic trace, not to hallucinate picks. That gives us elasticity, security, cost control, and a clear audit trail from data to answer card.

## Official AWS references

- AWS Lambda supports deploying functions as container images: https://docs.aws.amazon.com/lambda/latest/dg/images-create.html
- AWS Step Functions builds workflows for distributed applications and data or machine-learning pipelines: https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html
- AWS Step Functions can integrate directly with AWS services: https://docs.aws.amazon.com/step-functions/latest/dg/integrate-services.html
- AWS Serverless Applications Lens documents serverless best practices: https://docs.aws.amazon.com/wellarchitected/latest/serverless-applications-lens/welcome.html
- Amazon Bedrock Guardrails provides configurable safety and privacy controls: https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html
