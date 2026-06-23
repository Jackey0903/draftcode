# AWS Tool Innovation: Three Cloud-Native Patterns

## Positioning

Our AWS innovation is not "use more AWS services." It is using AWS managed services as a decision-control system for a high-uncertainty NBA draft problem.

The three patterns are:

1. **Evidence Ledger**: every prediction is tied to versioned data and a run record.
2. **Scenario Swarm**: many draft scenarios can run in parallel without managing servers.
3. **Explanation Firewall**: generative AI explains grounded evidence, but cannot silently overwrite the model answer.

Together, these make DraftCode replayable, auditable, elastic, and safe.

## Pattern 1: Evidence Ledger

### Problem

Most hackathon AI apps produce an answer but cannot prove where it came from. For this contest, that is risky because the rule requires the Agent to generate the answer, and the roadshow must explain why.

### AWS tool use

- **S3** stores raw official files, normalized tables, prediction outputs, trace JSON, and report artifacts under run-specific prefixes.
- **S3 versioning** keeps historical inputs available when the team reruns predictions after new information arrives.
- **DynamoDB** stores the run ledger: `run_id`, created time, model version, input snapshot, confidence summary, answer-card version, and status.
- **CloudWatch/X-Ray** ties runtime logs and traces to the same `run_id`.

### Innovation

The architecture treats every model run like a financial audit trail:

```text
input snapshot -> model run -> prediction output -> answer card -> explanation
```

That means a judge can ask "why this pick?" and we can answer from the trace, not from memory.

### Why this is reasonable

S3 is the right place for immutable files and large artifacts. DynamoDB is the right place for small, fast run metadata. We do not put everything into one database just to simplify the diagram.

## Pattern 2: Scenario Swarm

### Problem

The NBA draft is not a single deterministic ranking. One surprise pick changes every later pick and also changes milestone answers.

### AWS tool use

- **Step Functions** orchestrates the run as explicit states: ingest, validate, simulate, persist, explain.
- **Step Functions Distributed Map** runs Monte Carlo shards in parallel: each shard samples different source weights, team needs, and position scarcity assumptions.
- **Lambda container image** runs each scenario with the same packaged code and dependencies.
- **Reserved concurrency** caps spend and protects the account during live reruns.

### Innovation

Instead of building one mock draft, DraftCode can run a swarm of plausible drafts:

```text
scenario 001: high team-need weight
scenario 002: high mock-market weight
scenario 003: high combine-translation weight
...
aggregate: pick probability + milestone probability
```

The final answer is the mode/expected value of many scenarios, and low-confidence picks become the review queue.

### Why this is reasonable

This is exactly where serverless orchestration is useful: bursty, parallel, short-lived compute. A fixed EC2 instance would be idle most of the time and would make scaling/cost control less elegant.

## Pattern 3: Explanation Firewall

### Problem

LLMs are persuasive but can hallucinate. In this contest, a hallucinated explanation is worse than no explanation because it can hide bad reasoning.

### AWS tool use

- **Amazon Bedrock** generates concise judge-facing narratives only after the deterministic model produces trace JSON.
- **Bedrock Knowledge Bases** is the target pattern for grounding unstructured mock-draft/news/scouting notes from S3.
- **Bedrock Guardrails** is the safety boundary for generated text.
- **The deterministic trace remains the source of truth** for final picks and milestone answers.

### Innovation

We do not ask the model "who will be drafted?" directly. We ask:

```text
Given this trace, these component scores, and these source snippets,
write a short explanation of why the Agent selected this player.
```

That makes AI an explanation layer, not an uncontrolled decision maker.

### Why this is reasonable

Bedrock is used where it adds value: summarizing evidence and making the roadshow understandable. It is not used where structured scoring is more reliable.

## Tool-to-product mapping

| AWS tool | Ordinary use | Our differentiated use |
| --- | --- | --- |
| S3 | Store files | Versioned evidence ledger for every prediction run |
| Lambda | Run an API handler | Containerized scenario worker for reproducible data science |
| Step Functions | Chain functions | Draft-simulation control plane and Scenario Swarm orchestrator |
| Distributed Map | Batch parallelism | Monte Carlo draft universe generator |
| DynamoDB | Store app records | Run ledger and answer-card audit index |
| Bedrock | Chatbot | Grounded explanation layer behind a deterministic trace |
| Bedrock Guardrails | Safety filter | Explanation firewall preventing unsupported claims |
| CloudWatch/X-Ray | Debug logs | Run-level observability for judge/debug replay |
| SAM | Deployment template | Scored IaC artifact proving the architecture is not hand-built |

## Roadshow wording

> Our AWS innovation is that the cloud is the control plane for uncertainty. S3 and DynamoDB form an evidence ledger, Step Functions and Lambda containers let us run a swarm of draft scenarios without servers, and Bedrock sits behind an explanation firewall so it explains the trace instead of inventing picks. That is why the system is replayable, auditable, elastic, and cost-controlled.

## Implementation status

Implemented in this repo:

- S3 encrypted/versioned bucket.
- DynamoDB run ledger.
- Lambda container image.
- API Gateway endpoint.
- Step Functions single-run workflow.
- Step Functions Distributed Map Scenario Swarm workflow.
- X-Ray tracing and CloudWatch logs.
- SAM IaC.

Designed as next extension:

- Bedrock Knowledge Base over scouting/news/mock sources.
- Bedrock Guardrails for explanation generation.

## Sources

- AWS Lambda container images: https://docs.aws.amazon.com/lambda/latest/dg/images-create.html
- AWS Step Functions: https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html
- Step Functions Distributed Map: https://docs.aws.amazon.com/step-functions/latest/dg/state-map-distributed.html
- Amazon Bedrock Knowledge Bases: https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html
- Amazon Bedrock Guardrails: https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html
