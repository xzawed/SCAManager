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

# 각 워크플로우가 반드시 포함해야 하는 loop-until-dry 핵심 불변식 토큰 (주석 제외 실코드 기준)
# Core loop-until-dry invariant tokens every workflow must contain (matched against code, not comments)
_INVARIANTS = [
    "seen.has(key(",                       # (1) dedup: finding 키 재출현 차단 / dedup re-emergence
    "seen.add(",                           # (1) dedup: 발견 키 기록 / record surfaced key
    "dry < DRY_THRESHOLD",                 # (2) dry 종료 조건 / consecutive-dry stop
    "dry++",                               # (2) dry 증가 / dry increment
    "dry = 0",                             # (2) 신규 발견 시 dry 리셋 / reset dry on fresh
    "round < MAX_ROUNDS",                  # (3) round cap
    # (3) MAX_ROUNDS 파생 — 두 상수가 실제 사용됨을 강제(declared-but-unused 우회 차단)
    # (3) MAX_ROUNDS derivation — forces both consts to be USED (blocks declared-but-unused bypass)
    "budget.total ? MAX_ROUNDS_WITH_BUDGET : MAX_ROUNDS_NO_BUDGET",
    "budget.remaining() > BUDGET_FLOOR",   # (4) budget floor guard
]


# 정본 공유 함수 — 사용처가 글자 그대로 인라인해야 한다(주석 · 공백을 접고 소스를 비교).
# 토큰 존재만 보면 두 사용처의 `key` 가 갈라져도 초록이었다(11-06 회고: 키가 합친 건 121건 중 0).
# Canonical shared functions every consumer inlines verbatim; token presence alone stayed green while
# the two consumers' `key` diverged.
_SHARED_FUNCS = ["key", "freshOf", "priorList"]


def _function_source(code: str, name: str) -> str | None:
    """최상위 `function NAME(` 부터 열 0 의 `}` 까지 — 공백을 접은 비교용 소스. 없으면 None.
    Top-level `function NAME(` up to the column-0 `}`, whitespace-folded; None when absent."""
    m = re.search(rf"^(?:export\s+)?function {name}\(.*?^\}}", code, re.S | re.M)
    if not m:
        return None
    return re.sub(r"\s+", " ", re.sub(r"^export\s+", "", m.group(0))).strip()


def _strip_num(raw: str) -> int:
    """JS 숫자 구분자(_) 제거 후 정수 변환 / drop JS numeric separators then int."""
    return int(raw.replace("_", ""))


def _strip_comments(text: str) -> str:
    """JS 주석(블록·라인) 제거 — 불변식이 주석에만 있는 false-pass 차단 (#936 학습).
    Strip JS block/line comments so invariant tokens are matched against real code only
    (seals the #936 'comment false-pass' anti-pattern). 워크플로우 관련 영역엔 문자열 내 '//' 가
    없어 단순 제거로 충분(보수적 휴리스틱)."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)  # 블록 주석 / block comments
    text = re.sub(r"//.*", "", text)                         # 라인 주석 / line comments
    return text


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

    template_text = template.read_text(encoding="utf-8")
    canon = _parse_template_params(template_text)
    for name in _PARAMS:
        if name not in canon:
            msgs.append(f"템플릿 파라미터 누락 / template missing param: {name}")
    # 🔴 공유 함수는 주석을 지우지 않은 **원문**으로 비교한다 — `_strip_comments` 는 문자열 안의 `//` 뒤도
    #    지워 `"http://a"` 와 `"http://b"` 를 같게 읽는다(Grok claim-review 반증). 글자 그대로가 계약이다.
    # Compare shared functions on raw text: comment stripping also eats `//` inside string literals.
    canon_funcs = {name: _function_source(template_text, name) for name in _SHARED_FUNCS}
    for name, src in canon_funcs.items():
        if src is None:
            msgs.append(f"템플릿 공유 함수 누락 / template missing shared function: {name}")

    for wf_name in _WORKFLOWS:
        wf = wf_dir / wf_name
        if not wf.exists():
            msgs.append(f"워크플로우 없음 / workflow missing: {wf_name}")
            continue
        # 주석 제외 실코드 기준 — 선언·불변식이 주석에만 존재하는 false-pass 차단 (#936)
        # Match against comment-stripped code so declarations/invariants in comments don't false-pass (#936)
        raw = wf.read_text(encoding="utf-8")
        code = _strip_comments(raw)
        params = _parse_workflow_params(code)
        for name in _PARAMS:
            if name not in params:
                msgs.append(f"{wf_name}: 상수 미선언 / const not declared: {name}")
            elif name in canon and params[name] != canon[name]:
                msgs.append(f"{wf_name}: {name} drift {params[name]} != 정본/canonical {canon[name]}")
        for token in _INVARIANTS:
            if token not in code:
                msgs.append(f"{wf_name}: 불변식 토큰 누락 / invariant token missing: {token!r}")
        for name in _SHARED_FUNCS:
            got = _function_source(raw, name)
            if got is None:
                msgs.append(f"{wf_name}: 공유 함수 없음 / shared function missing: {name}")
            elif canon_funcs[name] is not None and got != canon_funcs[name]:
                msgs.append(f"{wf_name}: {name} 소스 drift — 정본 템플릿과 다르다 / "
                            "shared function differs from the canonical template")
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


_SHARED_SRC = (
    "function key(f) {\n  return `${f.file}|${f.title}`\n}\n"
    "function freshOf(found, seen) {\n  return found.filter((f) => !seen.has(key(f)))\n}\n"
    "function priorList(items, cap = 150) {\n  return items.slice(0, cap).join('\\n')\n}\n"
)
_GOOD_TEMPLATE = (
    "export const LOOP_PARAMS = { DRY_THRESHOLD: 2, MAX_ROUNDS_WITH_BUDGET: 5, "
    "MAX_ROUNDS_NO_BUDGET: 3, BUDGET_FLOOR: 60_000 }\n"
    + _SHARED_SRC.replace("function ", "export function ")
)
_GOOD_WF = (
    "const DRY_THRESHOLD = 2\nconst MAX_ROUNDS_WITH_BUDGET = 5\n"
    "const MAX_ROUNDS_NO_BUDGET = 3\nconst BUDGET_FLOOR = 60_000\n"
    "const MAX_ROUNDS = budget.total ? MAX_ROUNDS_WITH_BUDGET : MAX_ROUNDS_NO_BUDGET\n"
    "while (dry < DRY_THRESHOLD && round < MAX_ROUNDS) {\n"
    "  if (!seen.has(key(f))) { dry++; continue }\n"
    "  dry = 0\n  seen.add(key(f))\n"
    "  if (budget.remaining() > BUDGET_FLOOR) {}\n}\n"
    + _SHARED_SRC
)


def test_loop_sync_seed_is_clean(tmp_path):
    """대조군 — 아래 위반 시험들의 씨앗은 그 자체로 통과한다(위반이 심은 것에서만 나온다)."""
    root = _seed(tmp_path, _GOOD_TEMPLATE, _GOOD_WF)
    ok, msgs = _check_loop_sync(root)
    assert ok, msgs


def test_loop_sync_flags_shared_function_drift(tmp_path):
    """🔴 사용처의 `key` 가 정본과 달라지면 적발 — 토큰(`seen.has(key(`)은 그대로여도."""
    drifted = _GOOD_WF.replace("`${f.file}|${f.title}`", "`${f.domain}|${f.file}|${f.title}`")
    root = _seed(tmp_path, _GOOD_TEMPLATE, drifted)
    ok, msgs = _check_loop_sync(root)
    assert not ok
    assert any("key 소스 drift" in m for m in msgs), msgs


def test_loop_sync_flags_drift_after_a_double_slash_inside_a_string(tmp_path):
    """🔴 문자열 안 `//` 뒤의 어긋남도 잡는다 — 주석 제거를 거치면 `"http://a"` · `"http://b"` 가 같아진다."""
    template = _GOOD_TEMPLATE.replace("`${f.file}|${f.title}`", "'http://a' + f.title")
    drifted = _GOOD_WF.replace("`${f.file}|${f.title}`", "'http://b' + f.title")
    root = _seed(tmp_path, template, drifted)
    ok, msgs = _check_loop_sync(root)
    assert not ok
    assert any("key 소스 drift" in m for m in msgs), msgs


def test_loop_sync_flags_shared_function_missing_from_the_template(tmp_path):
    root = _seed(tmp_path, _GOOD_TEMPLATE.replace("export function priorList", "export function other"), _GOOD_WF)
    ok, msgs = _check_loop_sync(root)
    assert not ok
    assert any("template missing shared function: priorList" in m for m in msgs), msgs


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


def test_loop_sync_flags_invariant_only_in_comment(tmp_path):
    # 불변식이 실제 코드가 아닌 주석에만 존재하면 적발 (false-pass 봉인 — #936 학습).
    # invariant present only in a comment (not real code) must be flagged (#936 false-pass lesson).
    commented = _GOOD_WF.replace(
        "if (budget.remaining() > BUDGET_FLOOR) {}",
        "// budget.remaining() > BUDGET_FLOOR (주석으로만 존재 / comment only)",
    )
    root = _seed(tmp_path, _GOOD_TEMPLATE, commented)
    ok, msgs = _check_loop_sync(root)
    assert not ok
    assert any("invariant token missing" in m for m in msgs)


def test_loop_sync_flags_missing_template(tmp_path):
    ok, msgs = _check_loop_sync(tmp_path)
    assert not ok
    assert any("template missing" in m for m in msgs)
