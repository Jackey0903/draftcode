# Preparation checklist

## Must finish before 2026-06-23 09:00 Shanghai time

- Confirm Team Portal login works and save the URL in a password manager.
- Confirm Kiro IDE login works.
- Confirm Summit registration and ID for venue entry.
- Confirm AWS Global account can sign in and has billing/free credits available.
- Confirm the AWS Global account is a new account registered with a supported dual-currency credit card, per training notes.
- Confirm GitHub repo is Private and organizer access is granted.
- Confirm local repo can push to GitHub.
- Start Docker Desktop once and verify `docker info` works.
- Install/verify CLI tools: `python3.11`, `uv`, `aws`, `sam`, `gh`, `kiro`, `node`, `npm`.
- Run `make install`, `make test`, and `make predict`.

## Local commands

```bash
scripts/check_env.sh
make install
make test
make predict
make validate-sample
make report
make install-quality
make install-full
make dashboard
```

## AWS commands

```bash
aws configure sso
aws configure set region us-east-1
aws sts get-caller-identity
sam validate --template-file infra/template.yaml
sam build --template-file infra/template.yaml
```

Use the region assigned or recommended by the event. If no region is specified, default to `us-east-1` for Bedrock availability and broad service support.

## GitHub commands

```bash
gh auth login
gh repo view Jackey0903/draftcode --json name,visibility,url
gh repo edit Jackey0903/draftcode --visibility private
scripts/check_repo_private.sh
git push
```

## Submission self-check

- `outputs/predictions.csv` exists and contains all required first-round picks.
- `outputs/trace.json` exists and shows the Agent decision path.
- `draftcode validate-output --predictions outputs/predictions.csv --expected-picks 30` passes.
- Final answer card is copied from generated output, not hand-filled from memory.
- Repo has final code pushed before 2026-06-24 07:30 Shanghai time.
- PPT and demo video are uploaded before the deadline.
- Browser refresh confirms the submission status is submitted.
