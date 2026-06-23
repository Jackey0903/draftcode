PYTHON ?= python3.11
VENV ?= .venv
UV ?= uv

.PHONY: venv install install-full install-quality test lint predict validate-sample report dashboard api aws-check sam-validate sam-pull-base sam-build clean

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

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache outputs/*.csv outputs/*.json
