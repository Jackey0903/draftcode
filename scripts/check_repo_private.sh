#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-Jackey0903/draftcode}"

if ! command -v gh >/dev/null 2>&1; then
  echo "missing gh CLI"
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "GitHub CLI is not authenticated. Run: gh auth login"
  exit 1
fi

visibility="$(gh repo view "$REPO" --json visibility --jq .visibility)"
echo "$REPO visibility: $visibility"

if [[ "$visibility" != "PRIVATE" ]]; then
  echo "Repository must be PRIVATE for the hackathon."
  echo "Run: gh repo edit $REPO --visibility private"
  exit 1
fi
