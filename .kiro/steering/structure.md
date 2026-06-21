# Structure steering

- `src/draftcode/model.py`: scoring and sequential draft simulation.
- `src/draftcode/io.py`: CSV loading and output writing.
- `src/draftcode/pipeline.py`: end-to-end prediction run.
- `src/draftcode/cli.py`: competition commands.
- `infra/template.yaml`: AWS SAM serverless template.
- `docs/`: competition analysis, preparation checklist, architecture, and runbook.
- `data/sample/`: synthetic smoke-test data only.

Keep real Portal/raw data out of git unless the rules explicitly allow committing it.
