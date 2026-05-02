#!/usr/bin/env bash
# 정책 10 — GitHub API 로 PR 직접 생성 (gh CLI 부재 환경)
# Usage: ./create_pr.sh <branch> <title> <body_file>
# 환경변수: GITHUB_TOKEN 필수
set -euo pipefail

BRANCH="${1:?branch name required}"
TITLE="${2:?title required}"
BODY_FILE="${3:?body file path required}"

OWNER="xzawed"
REPO="SCAManager"
BASE="main"

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "ERROR: GITHUB_TOKEN env var missing" >&2
  exit 1
fi

# body 를 JSON-safe 로 인코딩
BODY_JSON=$(jq -Rs . < "$BODY_FILE")
TITLE_JSON=$(echo -n "$TITLE" | jq -Rs .)

PAYLOAD=$(cat <<EOF
{
  "title": $TITLE_JSON,
  "body": $BODY_JSON,
  "head": "$BRANCH",
  "base": "$BASE"
}
EOF
)

RESPONSE=$(curl -sS -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "Content-Type: application/json" \
  "https://api.github.com/repos/$OWNER/$REPO/pulls" \
  -d "$PAYLOAD")

PR_URL=$(echo "$RESPONSE" | jq -r '.html_url // empty')
PR_NUM=$(echo "$RESPONSE" | jq -r '.number // empty')

if [[ -z "$PR_URL" ]]; then
  echo "ERROR: PR creation failed" >&2
  echo "$RESPONSE" | jq . >&2
  exit 2
fi

echo "✅ PR #$PR_NUM created: $PR_URL"
