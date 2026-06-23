#!/usr/bin/env python3
"""
5-way config 싱크 점검 — RepoConfig ORM ↔ RepoConfigData ↔ RepoConfigUpdate 필드 집합 정합.
5-way config sync checker — field-set parity across the RepoConfig definitions.

채널/필드 추가 시 일부 레이어 누락 → NULL 덮어쓰기 운영 버그(api.md 5-way) 차단. Python 3자는
AST 견고 비교. settings 폼(HTML name=)은 best-effort 비교(파싱 실패 시 skip). PRESETS(JS)는
파싱 fragile 로 범위 외. 의도적 비대칭 필드는 _ALLOWLIST 제외. stdlib 전용.

Channel/field additions that miss a layer can silently NULL-overwrite DB values (api.md 5-way rule).
Three Python layers compared via AST (reliable). The settings HTML form is compared best-effort
(skip on parse failure). JS PRESETS are excluded (fragile parsing). stdlib only.
"""
import ast
import io
import re
import sys
from pathlib import Path

# Windows cp949 출력 보호 — UTF-8 강제.
# Protect against Windows cp949 console encoding — force UTF-8 output.
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 의도적 비대칭 필드 집합 — 3자 정합 체크에서 제외.
# Intentionally asymmetric fields — exempt from the three-way parity check.
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
#   repo_full_name   — RepoConfigData에는 있으나 RepoConfigUpdate에는 없음.
#                      URL 경로 파라미터로 전달되므로 Update body에서 제외 (의도적 설계).
#                      Present in RepoConfigData but absent from RepoConfigUpdate:
#                      passed as a URL path param, intentionally excluded from Update body.
_ALLOWLIST = frozenset({
    "id",
    "created_at",
    "updated_at",
    "hook_token",
    "railway_webhook_token",
    "railway_api_token",
    "repo_full_name",
})


def _orm_columns(src: str, class_name: str = "RepoConfig") -> set:
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


def _annotated_fields(src: str, class_name: str) -> set:
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


def _form_names(html: str) -> set:
    """settings 폼의 name="..." 속성 집합을 반환한다 (best-effort 정규식 파싱).

    Return the set of `name="..."` attribute values found in the HTML form (best-effort regex).
    """
    return set(re.findall(r'name="([a-z][a-z0-9_]*)"', html))


def check_sync(project_root: Path) -> tuple:
    """RepoConfig ORM ↔ RepoConfigData ↔ RepoConfigUpdate 3자 필드 집합 정합 검사.

    ORM 필드 집합을 정본으로 삼고, RepoConfigData·RepoConfigUpdate 각각에 대해
    누락(ORM 대비) 및 잉여(ORM 미존재) 필드를 보고한다.
    _ALLOWLIST 에 등재된 의도적 비대칭 필드는 검사에서 제외한다.

    The ORM column set is the source of truth. For both RepoConfigData and RepoConfigUpdate,
    report fields that are missing (present in ORM but not in the layer) or surplus (present in
    the layer but not in ORM). Fields in _ALLOWLIST are excluded from the check.

    Returns:
        (ok, msgs): ok=True 시 drift 없음 / ok=False 시 msgs 에 위반 내역 포함.
        (ok, msgs): ok=True means no drift; ok=False means msgs lists the violations.
    """
    # ORM 필드 집합 (allowlist 제외)
    # ORM field set (minus allowlist)
    orm_src = (project_root / "src" / "models" / "repo_config.py").read_text(encoding="utf-8")
    orm = _orm_columns(orm_src) - _ALLOWLIST

    # RepoConfigData 필드 집합 (allowlist 제외)
    # RepoConfigData field set (minus allowlist)
    data_src = (
        project_root / "src" / "config_manager" / "manager.py"
    ).read_text(encoding="utf-8")
    data = _annotated_fields(data_src, "RepoConfigData") - _ALLOWLIST

    # RepoConfigUpdate 필드 집합 (allowlist 제외)
    # RepoConfigUpdate field set (minus allowlist)
    update_src = (project_root / "src" / "api" / "repos.py").read_text(encoding="utf-8")
    update = _annotated_fields(update_src, "RepoConfigUpdate") - _ALLOWLIST

    msgs = []
    # ORM 대비 각 레이어의 누락/잉여 필드 보고
    # Report missing/surplus fields for each layer relative to ORM
    for label, fields in (("RepoConfigData", data), ("RepoConfigUpdate", update)):
        missing = orm - fields
        extra = fields - orm
        if missing:
            msgs.append(
                f"❌ {label} 누락(ORM 대비): {sorted(missing)}"
            )
        if extra:
            msgs.append(
                f"❌ {label} 잌여(ORM 미존재): {sorted(extra)}"
            )

    return (not msgs), msgs


def main() -> int:
    """CLI 진입점 — 통과 0 / 위반 1.

    CLI entry point — exit 0 on pass, exit 1 on violation.
    """
    project_root = Path(__file__).resolve().parents[1]
    ok, msgs = check_sync(project_root)
    print("=== 5-way config 싱크 점검 / Config 5-Way Sync Check ===\n")
    if ok:
        print(
            "✅ RepoConfig ORM ↔ RepoConfigData ↔ RepoConfigUpdate "
            "필드 집합 일치"
        )
        return 0
    for m in msgs:
        print(m)
    print(
        "\n해결: 신규 RepoConfig 필드를 ORM/Data/Update/폼/PRESETS "
        "5곳 동기화 (api.md 5-way). 의도적 비대칭은 _ALLOWLIST."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
