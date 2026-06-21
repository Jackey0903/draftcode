# Technical steering

Use Python 3.11 for local stability.

Core commands:

- `make install`
- `make test`
- `make predict`
- `make validate-sample`
- `make sam-validate`

Prefer deterministic, testable model logic before adding Bedrock or dashboard features. AWS work should favor serverless, infrastructure as code, least-privilege IAM, logs, and no committed secrets.
