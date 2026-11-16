"""회고 범위가 창 안 PR 본문의 claim-review 판정을 센다 — 반증률 추세 (회고 원장 이관 K07 P2-25).

## 사고

09-16 회고가 «Grok 반증률 83%(57/69) — 내 첫 판단이 6번 중 5번 뒤집히는데 집계하는 곳이 없어 추세가
보이지 않는다» 를 확정했다. 판정은 PR 본문마다 `verdict:` 줄로 남지만 아무도 세지 않았다.

## 이 파일이 잠그는 것

1. 판정 어휘는 claim-review 가드(`check_claim_review_trace.VERDICT_LINE`)의 것 하나다 — 따로 적지 않는다.
2. 반박 쪽(BROKEN · WEAKENED · REFUTED)과 성립 쪽(SURVIVES · HOLDS · CONFIRMED)을 가른다 — 두 쪽을 모두 심는다.
3. 줄 맨 앞이 아닌 `verdict:` · 닫힌 어휘 밖의 값 · HTML 주석 안의 줄은 세지 않는다(가드와 같은 하드닝).
4. 창 밖 PR 은 세지 않고, gh 를 못 쓰거나 목록이 상한에 닿으면 «안 쟀다»(None)다.
5. 이 값은 범위 축이 아니다 — 못 재도 `unmeasured` 에 싣지 않는다(PR 목록을 가리지 않는다).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "retro_scope.py"


def _load():
    spec = importlib.util.spec_from_file_location("retro_scope_crt", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rs = _load()

# witness-corpus: 판정 줄의 꼴 — 반박 쪽 · 성립 쪽 · 어휘 밖 값 · 줄 중간 · HTML 주석 안 · 소문자
_BODY_MIXED = (
    "## Grok claim-review\n\n"
    "- session: 0d51302a-b70d-4c18-b1f7-141ac6c1ab91\n"
    "- claim: 첫 판은 이스케이프된 파이프를 교대로 쪼개지 않는다\n"
    "- verdict: BROKEN — 반례가 나왔다\n"
    "- verdict: weakened\n"
    "- verdict: SURVIVES\n"
    "| verdict | HOLDS |\n"
    "- verdict: PASS\n"
    "그때 verdict: REFUTED 라고 적었다\n"
    "<!-- - verdict: REFUTED -->\n"
    "- verdict\n"
    ": BROKEN 은 다음 줄이라 판정 줄이 아니다\n"
    "- verdict:\n"
    "  REFUTED 도 마찬가지다\n"
)
_BODY_CONFIRMED = "- verdict: CONFIRMED\n- verdict: REFUTED\n"
_BODY_NONE = "본문에 판정 줄이 없다\n"


def test_the_vocabulary_is_the_guards_own():
    """판정 어휘의 원천은 claim-review 가드 하나다 — 같은 패턴 문자열을 쓴다."""
    import sys  # noqa: PLC0415

    sys.path.insert(0, str(_SCRIPT.parent))
    from check_claim_review_trace import VERDICT_LINE  # noqa: PLC0415

    assert rs._VERDICT.pattern == VERDICT_LINE


def test_both_sides_are_counted_and_noise_is_not():
    """🔴 반박 · 성립 두 쪽을 심고, 어휘 밖 값 · 줄 중간 · 주석 안 줄은 세지 않는다."""
    out = rs.tally_verdicts([_BODY_MIXED, _BODY_CONFIRMED, _BODY_NONE])
    assert out["verdicts"] == {"BROKEN": 1, "CONFIRMED": 1, "HOLDS": 1, "REFUTED": 1, "SURVIVES": 1,
                               "WEAKENED": 1}, out
    assert out["prs"] == 3 and out["prs_with_verdict"] == 2, out
    assert out["refuted_share"] == 0.5, out


def test_an_all_surviving_window_is_zero_not_none():
    """대조군 — 반박이 하나도 없으면 0 이다. None 은 «판정 줄이 하나도 없다» 에만 쓴다."""
    assert rs.tally_verdicts(["- verdict: SURVIVES\n"])["refuted_share"] == 0.0
    assert rs.tally_verdicts([_BODY_NONE])["refuted_share"] is None


def _rows(*pairs):
    return [{"number": n, "body": b} for n, b in pairs]


def test_only_window_prs_are_counted(monkeypatch):
    """창 밖 PR(검색 날짜가 하루 앞이라 섞여 들어온 것)은 세지 않는다."""
    monkeypatch.setattr(rs, "_gh_json", lambda _a: _rows((10, "- verdict: BROKEN\n"), (11, "- verdict: SURVIVES\n")))
    out = rs.claim_review_tally("2026-08-30T10:00:00+09:00", [11])
    assert out["prs"] == 1 and out["verdicts"] == {"SURVIVES": 1}, out


@pytest.mark.parametrize("rows", [None, "not-a-list", "limit"])
def test_unreadable_github_is_unmeasured(monkeypatch, rows):
    """gh 를 못 쓰거나 형식이 깨졌거나 목록이 상한에 닿으면 None — 일부만 세고 추세를 말하지 않는다."""
    value = _rows(*((n, "") for n in range(rs._GH_LIMIT))) if rows == "limit" else rows
    monkeypatch.setattr(rs, "_gh_json", lambda _a: value)
    assert rs.claim_review_tally("2026-08-30T10:00:00+09:00", [11]) is None


def test_the_tally_rides_on_compute_without_touching_unmeasured(monkeypatch):
    """`compute` 결과에 실리고, 못 재도 범위 축(`unmeasured`)에는 싣지 않는다."""
    monkeypatch.setattr(rs, "boundary_commit", lambda _f: "a" * 40)
    monkeypatch.setattr(rs, "report_head", lambda _f: None)
    monkeypatch.setattr(rs, "merged_prs", lambda _b, _upper=None: [11])
    monkeypatch.setattr(rs, "prs_merged_before", lambda *_a: [])
    monkeypatch.setattr(rs, "commit_time", lambda _r: "2026-08-30T10:00:00+09:00")
    monkeypatch.setattr(rs, "_gh_json", lambda _a: [{"number": 11, "mergedAt": "2026-08-31T00:00:00Z",
                                                     "body": "- verdict: BROKEN\n"}])
    out = rs.compute(fetched=True)
    assert out["claim_review"]["verdicts"] == {"BROKEN": 1}, out.get("claim_review")
    monkeypatch.setattr(rs, "claim_review_tally", lambda *_a: None)
    out = rs.compute(fetched=True)
    assert out["claim_review"] is None
    assert not any("claim" in u for u in out["unmeasured"]), out["unmeasured"]
