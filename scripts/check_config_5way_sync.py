#!/usr/bin/env python3
"""
3-way config 싱크 점검 — RepoConfig ORM ↔ RepoConfigData ↔ RepoConfigUpdate 필드 집합 정합.
3-way config sync checker — field-set parity across the three RepoConfig Python layers.

채널/필드 추가 시 Python 레이어 누락 → NULL 덮어쓰기 운영 버그(api.md 5-way)의 일부를 차단.
Python 3자(ORM·Data·Update)는 AST 견고 비교. 의도적 비대칭 필드는 _ALLOWLIST 제외. stdlib 전용.
🔴 범위 외(수동 검토 의무): settings.html 폼·PRESETS(JS) 2-layer 의 **필드-parity**(필드 이름 semantic
대조)는 HTML/JS 파싱 fragile 로 의도적 미검사(design 2026-06-23). 즉 파일명의 "5way"와 달리 실제
가드 범위는 Python 3-layer 다.
🔴 단, settings.html 폼 컨트롤의 **구조적 멤버십**(orphan = 어느 <form> 에도 안 속하고 form= 없음 →
제출 안 돼 clobber, #1041 form= 데이터손실 유형)은 필드 이름 대조가 불필요해 fragility 를 회피하므로
별도 정적 가드가 커버한다: tests/unit/ui/test_settings_form_membership.py (2026-07-09 회고 후속 ⑤).

Blocks the Python-layer subset of the api.md 5-way NULL-overwrite bug. The settings.html form and
PRESETS (JS) layers' FIELD-PARITY (semantic field-name matching) are intentionally OUT OF SCOPE
(fragile HTML/JS parsing) — manual review required. Three Python layers (ORM, Data, Update) are
compared via AST (reliable). stdlib only.
The settings.html form controls' STRUCTURAL MEMBERSHIP (orphan = belongs to no <form> and lacks form=
→ never submitted → clobber, the #1041 form= data-loss class) needs no field-name matching, so it avoids
the fragility and is covered separately by tests/unit/ui/test_settings_form_membership.py.
"""
import ast
import io
import sys
from pathlib import Path

# Windows cp949 출력 보호 — UTF-8 강제.
# Protect against Windows cp949 console encoding — force UTF-8 output.
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 의도적 비대칭 필드 집합 — ORM·Data·Update 3자 정합 체크 전체에서 제외.
# Intentionally asymmetric fields — exempt from all three-way parity comparisons.
#
# 제외 사유 / Exclusion rationale:
#   id               — DB 자동 PK (사용자 설정 불가)
#                      DB auto-PK, not user-settable
#   created_at       — DB 자동 타임스탬프 (INSERT 기본값)
#                      DB auto-timestamp on INSERT
#   updated_at       — DB 자동 타임스탬프 (UPDATE 기본값)
#                      DB auto-timestamp on UPDATE
#   hook_token       — 내부 Webhook 서명 토큰 (자동 생성, 사용자 미노출)
#                      Internal webhook signing token, auto-generated, not user-exposed
#   railway_webhook_token — 내부 Railway 콜백 토큰 (자동 생성)
#                           Internal Railway callback token, auto-generated
#   railway_api_token     — Fernet 암호화 저장, settings.py에서 ORM 직접 설정
#                           (RepoConfigData 외부 관리 — settings.py:219 주석 참조)
#                           Fernet-encrypted, set directly on ORM in settings.py
#                           (managed outside RepoConfigData — see settings.py:219)
_ALLOWLIST = frozenset({
    "id",
    "created_at",
    "updated_at",
    "hook_token",
    "railway_webhook_token",
    "railway_api_token",
})

# RepoConfigUpdate 비교에서만 추가로 제외하는 필드.
# Fields additionally exempt only from the ORM↔RepoConfigUpdate comparison.
#
# 제외 사유 / Exclusion rationale:
#   repo_full_name — ORM·RepoConfigData 양쪽에 존재하므로 ORM↔Data 검사는 통과 (정상).
#                    RepoConfigUpdate에서만 없음: URL 경로 파라미터로 전달되므로
#                    Update 요청 body에서 의도적으로 제외 (설계 결정).
#                    Present in both ORM and RepoConfigData (ORM↔Data check passes normally).
#                    Absent only from RepoConfigUpdate: passed as a URL path param,
#                    intentionally excluded from the Update request body.
_UPDATE_ONLY_EXEMPT = frozenset({
    "repo_full_name",
})


def _orm_columns(src: str, class_name: str = "RepoConfig") -> set[str]:
    """ORM 클래스의 `field = Column(...)` 필드명 집합을 반환한다.

    Return the set of field names declared as `field = Column(...)` in the given ORM class.
    """
    tree = ast.parse(src)
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for stmt in node.body:
                # `field = Column(...)` 형태인 경우만 수집
                # Collect only statements of the form `field = Column(...)`
                if (
                    isinstance(stmt, ast.Assign)
                    and isinstance(stmt.value, ast.Call)
                    and getattr(stmt.value.func, "id", "") == "Column"
                ):
                    for tgt in stmt.targets:
                        if isinstance(tgt, ast.Name):
                            out.add(tgt.id)
    return out


def _annotated_fields(src: str, class_name: str) -> set[str]:
    """dataclass/Pydantic 클래스의 `field: type` 어노테이션 필드명 집합을 반환한다.

    Return the set of annotated field names (`field: type`) from a dataclass or Pydantic class.
    """
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {
                s.target.id
                for s in node.body
                if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name)
            }
    return set()


def check_sync(project_root: Path) -> tuple[bool, list[str]]:
    """RepoConfig ORM ↔ RepoConfigData ↔ RepoConfigUpdate 3자 필드 집합 정합 검사.

    ORM 필드 집합을 정본으로 삼고, RepoConfigData·RepoConfigUpdate 각각에 대해
    누락(ORM 대비) 및 잉여(ORM 미존재) 필드를 보고한다.
    _ALLOWLIST 에 등재된 필드는 모든 비교에서 제외한다.
    _UPDATE_ONLY_EXEMPT 에 등재된 필드는 ORM↔RepoConfigUpdate 비교에서만 추가 제외한다.
    (ORM↔RepoConfigData 비교에서는 정상 검사됨.)

    The ORM column set is the source of truth. For both RepoConfigData and RepoConfigUpdate,
    report fields that are missing (present in ORM but not in the layer) or surplus (present in
    the layer but not in ORM). Fields in _ALLOWLIST are excluded from all comparisons.
    Fields in _UPDATE_ONLY_EXEMPT are additionally excluded only from the ORM↔Update comparison
    (they are still checked in the ORM↔Data comparison).

    Returns:
        (ok, msgs): ok=True 시 drift 없음 / ok=False 시 msgs 에 위반 내역 포함.
        (ok, msgs): ok=True means no drift; ok=False means msgs lists the violations.
    """
    # ORM 필드 집합 (allowlist 제외)
    # ORM field set (minus allowlist)
    orm_src = (project_root / "src" / "models" / "repo_config.py").read_text(encoding="utf-8")
    orm = _orm_columns(orm_src) - _ALLOWLIST

    # RepoConfigData 필드 집합 (allowlist 제외 — _UPDATE_ONLY_EXEMPT 는 여기서 검사됨)
    # RepoConfigData field set (minus allowlist only — _UPDATE_ONLY_EXEMPT is checked here)
    data_src = (
        project_root / "src" / "config_manager" / "manager.py"
    ).read_text(encoding="utf-8")
    data = _annotated_fields(data_src, "RepoConfigData") - _ALLOWLIST

    # RepoConfigUpdate 필드 집합 (allowlist + Update 전용 면제 모두 제외)
    # RepoConfigUpdate field set (minus both allowlist and Update-only exemptions)
    update_src = (project_root / "src" / "api" / "repos.py").read_text(encoding="utf-8")
    update = _annotated_fields(update_src, "RepoConfigUpdate") - _ALLOWLIST

    # Update 전용 면제 필드는 ORM↔Update 비교의 기준 ORM 집합에서도 제외
    # Remove Update-only exempt fields from the ORM reference set for the Update comparison
    orm_for_update = orm - _UPDATE_ONLY_EXEMPT

    msgs = []
    # ORM 대비 각 레이어의 누락/잉여 필드 보고
    # Report missing/surplus fields for each layer relative to ORM
    for label, layer_fields, orm_ref in (
        ("RepoConfigData", data, orm),
        ("RepoConfigUpdate", update, orm_for_update),
    ):
        missing = orm_ref - layer_fields
        extra = layer_fields - orm_ref
        if missing:
            msgs.append(
                f"❌ {label} 누락(ORM 대비): {sorted(missing)}"
            )
        if extra:
            msgs.append(
                f"❌ {label} 잉여(ORM 미존재): {sorted(extra)}"
            )

    return (not msgs), msgs


def main() -> int:
    """CLI 진입점 — 통과 0 / 위반 1.

    CLI entry point — exit 0 on pass, exit 1 on violation.
    """
    project_root = Path(__file__).resolve().parents[1]
    ok, msgs = check_sync(project_root)
    print("=== 3-way config 싱크 점검 / Config 3-Way Sync Check ===\n")
    if ok:
        print(
            "✅ RepoConfig ORM ↔ RepoConfigData ↔ RepoConfigUpdate "
            "필드 집합 일치"
        )
        return 0
    for m in msgs:
        print(m)
    print(
        "\n해결: 신규 RepoConfig 필드를 ORM/Data/Update "
        "3곳 동기화 (api.md 5-way). 의도적 비대칭은 _ALLOWLIST."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
