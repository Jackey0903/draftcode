# AWS scoring scorecard

Use this table when preparing the code-quality explanation and roadshow.

| Rubric signal | What we show | File or command |
| --- | --- | --- |
| Serverless over EC2 | API Gateway, Lambda, Step Functions, S3, DynamoDB; no always-on VM. | `infra/template.yaml` |
| Containerization | Prediction runtime packaged as a Lambda container image. | `Dockerfile.lambda` |
| Infrastructure as code | Full stack described in SAM. | `make sam-validate` |
| Security | S3 public access block, encryption, no committed secrets, scoped IAM policies, reserved concurrency. | `infra/template.yaml`, `.env.example` |
| Reliability | Deterministic local fallback, Step Functions retries, S3 versioning, DynamoDB PITR. | `infra/template.yaml`, `make test` |
| Observability | CloudWatch default logs plus X-Ray tracing on Lambda and state machine. | `infra/template.yaml` |
| Cost control | Pay-per-use serverless, DynamoDB on-demand, S3 lifecycle, concurrency cap. | `infra/template.yaml` |
| AI responsibility | Bedrock explains deterministic traces instead of inventing predictions. | `docs/architecture.md` |
| Data science insight | Milestone-aware Draft Twin optimizes both pick accuracy and the 28-point milestone section. | `docs/innovation_strategy.md` |
| Agent auditability | Every pick has component scores and top alternatives. | `outputs/trace.json`, `src/draftcode/model.py` |
| Submission safety | Output validator blocks missing or duplicate picks. | `draftcode validate-output` |

## Judge-facing claim

DraftCode uses AWS where the cloud changes the system quality: orchestration, auditability, elasticity, security, and operational visibility. The local deterministic model remains portable, but the production path is serverless and replayable.
