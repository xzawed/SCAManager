#!/usr/bin/env bash
# P4-Gate 검증 스크립트 — 프로덕션 DB 에 저장된 Analysis 의 이슈 목록에서
# 특정 tool (cppcheck / slither) 히트를 확인한다.
#
# 사용법:
#   export DATABASE_URL="postgresql://..."   # Railway Variables 의 DATABASE_URL
#   bash docs/samples/p4-gate/verify_tool_hits.sh <analysis_id> [tool]
#
# 예:
#   bash docs/samples/p4-gate/verify_tool_hits.sh 42 cppcheck
#   bash docs/samples/p4-gate/verify_tool_hits.sh 43 slither
#
# 종료 코드:
#   0 — 이슈 발견 (통과)
#   1 — 이슈 없음 / 분석 미완료 (실패)
#   2 — 인자 오류 / 환경변수 미설정

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <analysis_id> [tool]" >&2
  exit 2
fi

ANALYSIS_ID="$1"
TOOL="${2:-}"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL not set. Copy from Railway Variables." >&2
  exit 2
fi

# DATABASE_URL 호환성 — postgres:// → postgresql://
DB_URL="${DATABASE_URL/postgres:\/\//postgresql:\/\/}"

python3 - "$ANALYSIS_ID" "$TOOL" "$DB_URL" <<'PY'
import sys
from sqlalchemy import create_engine, text

analysis_id = int(sys.argv[1])
tool_filter = sys.argv[2] or None
db_url = sys.argv[3]

engine = create_engine(db_url)
with engine.connect() as conn:
    row = conn.execute(
        text("SELECT result FROM analyses WHERE id = :id"),
        {"id": analysis_id},
    ).first()

if row is None:
    print(f"NOT FOUND: analysis id={analysis_id}")
    sys.exit(1)

result = row[0] or {}
issues = result.get("issues") or []
if tool_filter:
    issues = [i for i in issues if i.get("tool") == tool_filter]

print(f"analysis_id={analysis_id} tool={tool_filter or '(any)'} count={len(issues)}")
for i in issues[:10]:
    print(f"  [{i.get('tool')}/{i.get('severity')}] line={i.get('line')} "
          f"category={i.get('category')} — {i.get('message')}")

sys.exit(0 if issues else 1)
PY
