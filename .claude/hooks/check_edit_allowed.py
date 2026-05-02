#!/usr/bin/env python3
"""
모바일 환경 보호 Hook — PreToolUse (Edit/Write)

테스트 환경이 없는 환경에서 고위험 파일 수정을 차단합니다.

[보호 대상]
- alembic/versions/  : DB 마이그레이션 (pytest로 검증 불가, 데이터 손실 위험)
- src/templates/     : HTML 템플릿 (렌더링 오류는 pytest 미감지)
- railway.toml       : 프로덕션 배포 설정
- Procfile           : 프로덕션 시작 명령
- alembic.ini        : Alembic 설정

[허용 조건]
- pytest, fastapi, sqlalchemy 가 import 가능한 환경 (make test 실행 가능)

[2026-05-02 fix — Phase 1+2 회고 P0 후속]
기존: subprocess 검증 시 sys.executable 사용 → Claude Code 가 hook 을 시스템
minimal python (/usr/bin/python3, pytest 미설치) 으로 호출 시 항상 차단. 그러나
사용자의 `make test` 는 PATH 의 python (/usr/local/bin/python = pyenv/conda/venv,
pytest 있음) 사용 → 환경 모순.

수정: shutil.which("python") → "python3" → sys.executable fallback. PATH 의 python
(=`make test` 가 사용하는 동일 python) 우선 검증 → false positive 차단 해소.
"""
import sys
import json
import re
import shutil
import subprocess

# stdin에서 hook payload 읽기
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

tool_input = data.get("tool_input", {})
file_path = (tool_input.get("file_path", "") or "").replace("\\", "/")

if not file_path:
    sys.exit(0)

# 보호 대상 패턴
PROTECTED_PATTERNS = [
    (r"alembic/versions/",  "DB 마이그레이션 파일 — 잘못된 수정은 데이터 손실로 이어집니다"),
    (r"src/templates/",     "HTML 템플릿 — 렌더링 오류와 변수명 오류는 pytest로 감지되지 않습니다"),
    (r"railway\.toml$",     "프로덕션 배포 설정 — 오류는 실제 배포 시점에만 드러납니다"),
    (r"(^|/)Procfile$",     "프로덕션 시작 명령 — 오류는 실제 배포 시점에만 드러납니다"),
    (r"alembic\.ini$",      "Alembic 설정 — 경로 오류는 앱 시작 시에만 드러납니다"),
]

matched_reason = None
for pattern, reason in PROTECTED_PATTERNS:
    if re.search(pattern, file_path):
        matched_reason = reason
        break

if matched_reason is None:
    sys.exit(0)  # 보호 대상 아님 → 통과

# 테스트 환경 확인 (pytest, fastapi, sqlalchemy import 가능한지)
# PATH 의 python 우선 (= `make test` 가 사용하는 동일 인터프리터). 시스템 minimal
# python (/usr/bin/python3, pytest 미설치) 으로 hook 이 호출되어도 정상 검증.
# Order: python (PATH) → python3 (PATH) → sys.executable (hook runner 의 python).
PY_CMD = shutil.which("python") or shutil.which("python3") or sys.executable
try:
    result = subprocess.run(
        [PY_CMD, "-c", "import pytest, fastapi, sqlalchemy"],
        capture_output=True,
        timeout=5,
        check=False,
    )
    can_test = result.returncode == 0
except Exception:  # pylint: disable=broad-except
    can_test = False

if can_test:
    sys.exit(0)  # 테스트 환경 OK → 통과

# 테스트 환경 없음 → 차단
output = {
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": (
            f"[모바일 환경 보호] 수정 차단: {file_path}\n\n"
            f"사유: {matched_reason}\n\n"
            "이 파일은 자동화 테스트로 검증이 불가능한 고위험 영역입니다.\n"
            "수정하려면 아래 환경 중 하나에서 작업하세요:\n"
            "  - 로컬 PC: pip install -r requirements.txt → make test\n"
            "  - GitHub Codespaces: Code 버튼 → Codespaces → Create codespace"
        ),
    }
}
print(json.dumps(output, ensure_ascii=True))
sys.exit(0)
