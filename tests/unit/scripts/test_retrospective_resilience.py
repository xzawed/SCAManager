"""retrospective.mjs 회복력·출력 완전성 가드 (회고 백로그 C10).
Retrospective.mjs resilience / output-completeness guard (retro backlog C10).

2026-06-23 회고가 completeness 라운드 API 500 으로 gap 라운드를 통째로 소실(C10) + confirmed
출력에서 evidence·citation_verified 가 누락돼 보고서 추적성이 깨진 사고를 회귀 차단한다.
정적 가드는 주석 제거 후 실코드 기준 매칭(#936 false-pass 봉인 패턴 재적용).
Static guard matches comment-stripped code (re-applies the #936 false-pass sealing pattern).
"""
import re
from pathlib import Path

# 리포 루트 / repo root
_ROOT = Path(__file__).resolve().parents[3]
_RETRO = _ROOT / ".claude" / "workflows" / "retrospective.mjs"
_INTEGRITY = _ROOT / ".claude" / "workflows" / "integrity-audit.mjs"


def _strip_comments(text: str) -> str:
    """JS 주석 제거 — 불변식이 주석에만 있는 false-pass 차단 (#936 학습).
    Strip JS comments so invariants present only in comments don't false-pass (#936)."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)  # 블록 주석 / block comments
    text = re.sub(r"//.*", "", text)                         # 라인 주석 / line comments
    return text


def _surfaces_evidence(code: str) -> bool:
    """confirmed 출력 map 이 evidence·citation_verified 를 환류하는가 (C10).
    Does the confirmed output map surface evidence·citation_verified?"""
    return "evidence: f.evidence" in code and "citation_verified: f.citation_verified" in code


def _completeness_is_resilient(code: str) -> bool:
    """Completeness→Report 구간이 try/catch 로 격리됐는가 (best-effort, C10).
    Is the Completeness→Report span isolated by try/catch (best-effort)?"""
    m = re.search(
        r"phase\(\s*['\"]Completeness['\"]\s*\).*?phase\(\s*['\"]Report['\"]\s*\)",
        code, re.DOTALL,
    )
    if not m:
        return False
    region = m.group(0)
    return "try {" in region and "catch" in region


def _code() -> str:
    return _strip_comments(_RETRO.read_text(encoding="utf-8"))


# --- 현재 repo 통과 (dogfooding) / current repo passes ---

def test_confirmed_output_surfaces_evidence_and_citation():
    assert _surfaces_evidence(_code()), \
        "confirmed 출력에 evidence·citation_verified 누락 (C10 회귀)"


def test_completeness_round_is_resilient():
    assert _completeness_is_resilient(_code()), \
        "Completeness 라운드가 try/catch 로 보호되지 않음 (C10 회귀 — 2026-06-23 500 사고)"


def test_integrity_audit_completeness_round_is_resilient():
    """integrity-audit.mjs 도 Completeness 라운드를 try/catch 로 격리 (C10 패턴 계승, 2026-06-29 구조검토).
    integrity-audit.mjs's Completeness round is also try/catch-isolated (C10 pattern inherited)."""
    code = _strip_comments(_INTEGRITY.read_text(encoding="utf-8"))
    assert _completeness_is_resilient(code), \
        "integrity-audit.mjs Completeness 라운드가 try/catch 로 보호되지 않음 (C10 회귀)"


# --- 합성 위반 적발 (주석 false-pass 봉인) / synthetic violation caught ---

def test_evidence_guard_rejects_comment_only():
    """evidence 토큰이 주석에만 있으면 false-pass 하지 않음 (#936 봉인)."""
    fake = (
        "confirmed: confirmed.map((f) => ({\n"
        "  // evidence: f.evidence, citation_verified: f.citation_verified\n"
        "  title: f.title,\n"
        "}))\n"
    )
    assert not _surfaces_evidence(_strip_comments(fake))


def test_resilience_guard_rejects_comment_only_try():
    """try/catch 가 주석에만 있으면 false-pass 하지 않음 (#936 봉인)."""
    fake = (
        "phase('Completeness')\n"
        "// try { ... } catch (e) {}\n"
        "const gaps = await agent(x)\n"
        "phase('Report')\n"
    )
    assert not _completeness_is_resilient(_strip_comments(fake))


# --- coverage<1.0 보강: UNVERIFIED 1회 bounded 재검증 (C10-d) ---

def _has_coverage_boost(code: str) -> bool:
    """coverage<1.0 시 UNVERIFIED 만 1회 bounded 재검증하는가 (C10-d)."""
    return "verified.filter" in code and "verifyAll(unresolved" in code


def test_coverage_boost_reverifies_unverified():
    """UNVERIFIED 만 1회 bounded 재검증으로 verdict_coverage 보강 (C10-d, 실코드 기준)."""
    assert _has_coverage_boost(_code()), \
        "coverage 보강 재검증(UNVERIFIED 1회 bounded) 누락 (C10-d 회귀)"


def test_coverage_boost_guard_rejects_comment_only():
    """재검증 토큰이 주석에만 있으면 false-pass 하지 않음 (#936 봉인)."""
    fake = (
        "// const unresolved = verified.filter((v) => v.verdict === 'UNVERIFIED')\n"
        "// verifyAll(unresolved, context)\n"
        "phase('Report')\n"
    )
    assert not _has_coverage_boost(_strip_comments(fake))


# ── FP 객체 환류 (#1443 b) ────────────────────────────────────────────────────
#
# 🔴 종전에는 `roi.fp_blocked` **개수만** 반환했다. 개수는 「몇 건을 걸렀나」는 말하지만
#    **무엇이 왜 FP 였는지**는 말하지 않는다. 그래서 다음 회고가 같은 오탐을 처음부터
#    다시 판정한다 — loop-until-dry 가 매번 같은 바닥을 다시 긁는 이유다.


def test_false_positive_objects_are_returned_not_just_counted():
    """🔴 반환 JSON 에 `false_positives[]` 가 있고 **사유**를 담는다."""
    code = _strip_comments(_RETRO.read_text(encoding="utf-8"))
    assert "false_positives:" in code, (
        "FP 객체가 반환되지 않는다 — `roi.fp_blocked` 개수만으로는 다음 회고가 "
        "같은 오탐을 다시 판정한다"
    )
    # 개수 축은 그대로 남아야 한다(ROI 표가 쓴다) — 대체가 아니라 추가다.
    assert "fp_blocked: falsePositives.length" in code, "ROI 개수 축이 사라졌다"


def test_false_positive_payload_carries_the_reason():
    """🔴 `reason` 이 핵심 — 무엇을 근거로 기각했는가가 없으면 재판정을 못 막는다."""
    code = _strip_comments(_RETRO.read_text(encoding="utf-8"))
    block = code[code.index("false_positives:"):]
    block = block[:block.index("scope_drift_during_run")] if "scope_drift_during_run" in block else block
    for field in ("title", "reason", "claim", "domain"):
        assert f"{field}:" in block, f"FP payload 에 `{field}` 가 없다"


def test_false_positive_fields_are_coalesced_so_keys_never_vanish():
    """🔴 FP payload 의 **모든** 필드가 `?? null` 이다 — 코얼레스가 없으면 키가 사라진다.

    Grok claim-review `01a01536` 적발: `domain`·`title`·`claim`·`reason` 이 코얼레스되지
    않으면, StructuredOutput 이 우회된 경우 그 값이 `undefined` 가 되고 `JSON.stringify` 가
    **키를 통째로 드롭**한다. 그러면 payload 가 채워진 것처럼 보이면서 비어 있다 —
    다음 회고는 「FP 목록이 있다」고 읽고 그 안에서 아무것도 못 찾는다.
    Every FP field must be coalesced; an uncoalesced undefined is dropped by JSON.stringify,
    leaving a payload that looks populated but is empty.
    """
    code = _strip_comments(_RETRO.read_text(encoding="utf-8"))
    block = code[code.index("false_positives:"):]
    block = block[:block.index("scope_drift_during_run")]
    for field in ("domain", "severity", "title", "file", "line", "claim", "reason", "verdict"):
        assert f"{field}: f.{field} ?? null" in block, (
            f"FP payload 의 `{field}` 가 코얼레스되지 않았다 — undefined 면 키가 사라진다"
        )
