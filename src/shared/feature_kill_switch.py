"""feature_kill_switch — 환경변수 기반 기능 비활성화 helper.

Cycle 78 NEW-P0-2 — 5+1 cross-verify 결과: Phase 4 후보 5종 진입 시 모두 kill-switch
신설 의무 → 사용처 ≥3 임계 도달 = helper 추출 결정 시점 (정책 16 4번 원칙).
Cycle 78 NEW-P0-2 — 5+1 cross-verify result: Phase 4 areas all need kill-switch
on entry → usage count ≥3 threshold reached = helper extraction trigger
(Policy 16 principle #4).

기존 사용처 (Phase 9 패턴 — `<FEATURE>_DISABLED=1`):
- `SECURITY_AUTO_PROCESS_DISABLED` (Cycle 73 #244 — security_scan_service / dashboard_service)
- `SCAMANAGER_SELF_ANALYSIS_DISABLED` (Phase 9 — webhook/providers/github.py)

Cycle 78~82 신규 사용처 후보 (영역 진입 시):
- `TELEGRAM_INTERACTIVE_DISABLED` (Cycle 78 PR 4)
- `SAAS_MULTITENANT_DISABLED` (Cycle 79)
- `OPERATIONS_DASHBOARD_DISABLED` (Cycle 80)
- `MOBILE_PWA_DISABLED` (Cycle 81)
- `SECURITY_CLASSIFY_DISABLED` (Cycle 82)

사용 패턴:
    from src.shared.feature_kill_switch import is_disabled
    if is_disabled("SECURITY_AUTO_PROCESS"):
        return  # skip
"""
from __future__ import annotations

import os

_TRUTHY_VALUES = ("1", "true", "yes")


def is_disabled(feature: str) -> bool:
    """환경변수 `<FEATURE>_DISABLED` 가 truthy 일 때 True 반환.

    Return True when env var `<FEATURE>_DISABLED` is set to truthy value.

    Truthy values: "1", "true", "yes" (case-insensitive). 미설정 또는 공백 = False.
    Truthy values: "1", "true", "yes" (case-insensitive). Unset or blank = False.
    """
    env_name = f"{feature}_DISABLED"
    raw = os.environ.get(env_name, "")
    return raw.strip().lower() in _TRUTHY_VALUES
