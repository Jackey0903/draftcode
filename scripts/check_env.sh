#!/usr/bin/env bash
set -euo pipefail

check() {
  local name="$1"
  local cmd="$2"
  if command -v "$cmd" >/dev/null 2>&1; then
    printf "ok      %-14s %s\n" "$name" "$($cmd --version 2>&1 | head -n 1)"
  else
    printf "missing %-14s install required\n" "$name"
  fi
}

echo "DraftCode local environment check"
echo "---------------------------------"
check "python3.11" "python3.11"
check "uv" "uv"
check "node" "node"
check "npm" "npm"
check "docker" "docker"
check "aws" "aws"
check "sam" "sam"
check "gh" "gh"
check "kiro" "kiro"

echo
if docker info >/dev/null 2>&1; then
  echo "ok      docker-daemon  running"
else
  echo "missing docker-daemon  start Docker Desktop before SAM local builds"
fi

echo
if command -v aws >/dev/null 2>&1; then
  aws configure list
else
  echo "aws configure list skipped"
fi
