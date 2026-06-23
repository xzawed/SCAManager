"""워크플로우 loop-until-dry 단일출처 drift 가드 (PR-W / W1 폴백).
Workflow loop-until-dry single-source drift guard (PR-W / W1 fallback).

워크플로우 스크립트는 sibling .mjs 를 import 불가(런타임 실측: 정적 import = SyntaxError,
동적 import() = "not available")하므로, 정본 템플릿(_lib/loop-until-dry.template.mjs)의
파라미터·불변식을 각 워크플로우가 인라인 선언하고 본 테스트가 'inline == 정본' 을 강제해
drift 를 차단한다(정책 16 단일출처 효과 대체).
Workflow scripts cannot import sibling .mjs (runtime-verified), so each workflow inlines the
canonical template's params/invariants and this test enforces 'inline == canonical' to block
drift (substitutes for the single-source effect of an import; policy 16).
"""
import re
from pathlib import Path

# 리포 루트 / repo root
_ROOT = Path(__file__).resolve().parents[3]

# loop-until-dry 를 인라인한 워크플로우 / workflows that inline loop-until-dry
_WORKFLOWS = ["integrity-audit.mjs", "retrospective.mjs"]

# 정본 파라미터 4종 / the 4 canonical params
_PARAMS = ["DRY_THRESHOLD", "MAX_ROUNDS_WITH_BUDGET", "MAX_ROUNDS_NO_BUDGET", "BUDGET_FLOOR"]

# 각 워크플로우가 반드시 포함해야 하는 loop-until-dry 핵심 불변식 토큰
# Core loop-until-dry invariant tokens every workflow must contain
_INVARIANTS = [
    "seen.has(key(",                    # (1) dedup: 발견된 finding 키 재출현 차단 / dedup re-emergence
    "dry < DRY_THRESHOLD",              # (2) dry counter: 연속 신규-0 종료 / consecutive-dry stop
    "dry++",                            # (2) dry 증가 / dry increment
    "budget.remaining() > BUDGET_FLOOR",  # (4) budget floor: 잔여 예산 하한 / budget floor guard
]


def _strip_num(raw: str) -> int:
    """JS 숫자 구분자(_) 제거 후 정수 변환 / drop JS numeric separators then int."""
    return int(raw.replace("_", ""))


def _parse_template_params(text: str) -> dict:
    """LOOP_PARAMS = { NAME: value, ... } 블록에서 정본 값 추출.
    Extract canonical values from the LOOP_PARAMS = { ... } block."""
    out = {}
    for name in _PARAMS:
        m = re.search(rf"{name}\s*:\s*([0-9_]+)", text)
        if m:
            out[name] = _strip_num(m.group(1))
    return out


def _parse_workflow_params(text: str) -> dict:
    """워크플로우의 `const NAME = value` 인라인 선언 추출.
    Extract a workflow's inline `const NAME = value` declarations."""
    out = {}
    for name in _PARAMS:
        m = re.search(rf"const\s+{name}\s*=\s*([0-9_]+)", text)
        if m:
            out[name] = _strip_num(m.group(1))
    return out


def _check_loop_sync(root: Path):
    """정본 템플릿 ↔ 워크플로우 인라인 파라미터·불변식 정합 검사.
    Check canonical template ↔ workflow inline params/invariants. Returns (ok, msgs)."""
    msgs = []
    wf_dir = root / ".claude" / "workflows"
    template = wf_dir / "_lib" / "loop-until-dry.template.mjs"
    if not template.exists():
        return False, [f"정본 템플릿 없음 / template missing: {template}"]

    canon = _parse_template_params(template.read_text(encoding="utf-8"))
    for name in _PARAMS:
        if name not in canon:
            msgs.append(f"템플릿 파라미터 누락 / template missing param: {name}")

    for wf_name in _WORKFLOWS:
        wf = wf_dir / wf_name
        if not wf.exists():
            msgs.append(f"워크플로우 없음 / workflow missing: {wf_name}")
            continue
        text = wf.read_text(encoding="utf-8")
        params = _parse_workflow_params(text)
        for name in _PARAMS:
            if name not in params:
                msgs.append(f"{wf_name}: 상수 미선언 / const not declared: {name}")
            elif name in canon and params[name] != canon[name]:
                msgs.append(f"{wf_name}: {name} drift {params[name]} != 정본/canonical {canon[name]}")
        for token in _INVARIANTS:
            if token not in text:
                msgs.append(f"{wf_name}: 불변식 토큰 누락 / invariant token missing: {token!r}")
    return (not msgs), msgs


# --- 현재 repo 통과 (dogfooding) / current repo passes ---

def test_loop_sync_passes_on_current_repo():
    ok, msgs = _check_loop_sync(_ROOT)
    assert ok, msgs


# --- 합성 위반 적발 (양방향) / synthetic violation caught (bidirectional) ---

def _seed(tmp_path: Path, template_text: str, wf_text: str):
    """tmp 리포에 템플릿 + 워크플로우 2종 생성 / seed tmp repo with template + 2 workflows."""
    wf = tmp_path / ".claude" / "workflows"
    (wf / "_lib").mkdir(parents=True)
    (wf / "_lib" / "loop-until-dry.template.mjs").write_text(template_text, encoding="utf-8")
    for name in _WORKFLOWS:
        (wf / name).write_text(wf_text, encoding="utf-8")
    return tmp_path


_GOOD_TEMPLATE = (
    "export const LOOP_PARAMS = { DRY_THRESHOLD: 2, MAX_ROUNDS_WITH_BUDGET: 5, "
    "MAX_ROUNDS_NO_BUDGET: 3, BUDGET_FLOOR: 60_000 }\n"
)
_GOOD_WF = (
    "const DRY_THRESHOLD = 2\nconst MAX_ROUNDS_WITH_BUDGET = 5\n"
    "const MAX_ROUNDS_NO_BUDGET = 3\nconst BUDGET_FLOOR = 60_000\n"
    "if (!seen.has(key(f))) {}\nwhile (dry < DRY_THRESHOLD) { dry++ }\n"
    "if (budget.remaining() > BUDGET_FLOOR) {}\n"
)


def test_loop_sync_flags_param_drift(tmp_path):
    drifted = _GOOD_WF.replace("DRY_THRESHOLD = 2", "DRY_THRESHOLD = 9")
    root = _seed(tmp_path, _GOOD_TEMPLATE, drifted)
    ok, msgs = _check_loop_sync(root)
    assert not ok
    assert any("drift" in m for m in msgs)


def test_loop_sync_flags_missing_invariant(tmp_path):
    # 불변식 토큰(budget floor) 제거 → 적발 / strip a budget-floor invariant → caught
    broken = _GOOD_WF.replace("budget.remaining() > BUDGET_FLOOR", "true")
    root = _seed(tmp_path, _GOOD_TEMPLATE, broken)
    ok, msgs = _check_loop_sync(root)
    assert not ok
    assert any("invariant token missing" in m for m in msgs)


def test_loop_sync_flags_missing_template(tmp_path):
    ok, msgs = _check_loop_sync(tmp_path)
    assert not ok
    assert any("template missing" in m for m in msgs)
