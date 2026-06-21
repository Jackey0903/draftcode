#!/usr/bin/env bash
set -euo pipefail

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is required: https://brew.sh"
  exit 1
fi

brew install python@3.11 uv awscli aws-sam-cli gh

echo
echo "Next manual steps:"
echo "1. Start Docker Desktop before SAM local builds."
echo "2. Run: gh auth login"
echo "3. Run: aws configure sso  # or aws configure, depending on the AWS account issued for the contest"
echo "4. Run: make install && make test && make predict"
