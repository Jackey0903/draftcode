PYTHON ?= python3.11
VENV ?= .venv
UV ?= uv
STACK_NAME ?= draftcode
AWS_REGION ?= us-east-1
DATA_S3_PREFIX ?= processed
DRAFTCODE_DRAWS ?= 1000
DRAFTCODE_SEED ?= 42
S3_BUCKET ?=

.PHONY: venv install install-full install-quality test lint predict simulate ingest answer upload-data validate-sample report dashboard api aws-check sam-validate sam-pull-base sam-build sam-deploy clean

venv:
	test -x $(VENV)/bin/python || $(UV) venv --python $(PYTHON) $(VENV)

install: venv
	$(UV) pip install -e ".[dev]"

install-full: venv
	$(UV) pip install -e ".[dev,app,aws]"

install-quality: venv
	$(UV) pip install -e ".[quality]"

test:
	$(VENV)/bin/pytest -q

lint:
	$(VENV)/bin/ruff check src tests

predict:
	$(VENV)/bin/draftcode predict --data-dir data/sample --output outputs/predictions.csv --trace outputs/trace.json

simulate:
	$(VENV)/bin/draftcode simulate --data-dir data/sample --output outputs/twin.json --draws 1000 --seed 42

ingest:
	$(VENV)/bin/draftcode ingest --source data/raw/official --out data/processed

answer:
	$(VENV)/bin/draftcode answer --data-dir data/processed --template data/raw/official/answer_card_template.xlsx --out outputs/answer_card.xlsx --draws 1000 --seed 42 --team-id Team01

upload-data:
	test -n "$(S3_BUCKET)" || (echo "S3_BUCKET is required, e.g. make upload-data S3_BUCKET=<bucket> DATA_S3_PREFIX=processed" >&2; exit 1)
	$(VENV)/bin/draftcode upload-data --source data/processed --bucket "$(S3_BUCKET)" --prefix "$(DATA_S3_PREFIX)"

validate-sample:
	$(VENV)/bin/draftcode validate-output --predictions outputs/predictions.csv --expected-picks 10

report:
	$(VENV)/bin/draftcode render-report --predictions outputs/predictions.csv --output outputs/report.html

dashboard:
	$(VENV)/bin/streamlit run src/draftcode/dashboard.py -- --predictions outputs/predictions.csv

api:
	$(VENV)/bin/uvicorn draftcode.api:app --reload --app-dir src

aws-check:
	scripts/check_env.sh

sam-validate:
	SAM_CLI_TELEMETRY=0 sam validate --template-file infra/template.yaml --region us-east-1

sam-pull-base:
	docker pull public.ecr.aws/lambda/python:3.12

sam-build:
	SAM_CLI_TELEMETRY=0 sam build --template-file infra/template.yaml

sam-deploy: sam-build
	SAM_CLI_TELEMETRY=0 sam deploy --template-file .aws-sam/build/template.yaml --stack-name "$(STACK_NAME)" --region "$(AWS_REGION)" --capabilities CAPABILITY_IAM --resolve-image-repos --parameter-overrides DraftDataS3Prefix="$(DATA_S3_PREFIX)" DraftCodeDraws="$(DRAFTCODE_DRAWS)" DraftCodeSeed="$(DRAFTCODE_SEED)"

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache outputs/*.csv outputs/*.json
