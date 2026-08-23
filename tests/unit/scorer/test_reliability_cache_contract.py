"""🔴 `analyses.score_unreliable` 은 캐시다 — 정의와 어긋나면 평균이 **조용히** 틀린다.

🔴 The column is a cache of `score_is_unreliable(result)`; drift = silently wrong averages.

## 무엇을 사는가 (실측)

집계는 판정 근거가 `result` JSON 안에 있어 그 전량을 읽어야 했다.
로컬 PG17, 운영 동형 5,164행 · 33 MB:

    result 블롭 전량 로드        16.2 ms · 5,164행 · 33 MB 전송
    json 5경로 `->` 추출        422.5 ms  ← `json` 은 텍스트라 접근마다 재파싱
    jsonb 5경로 `->`             74.7 ms  (테이블 재작성 필요)
    컬럼 + 부분인덱스              0.45 ms · **4행** · 버퍼 6 (Index Only Scan)

## 무엇을 잃는가 (정직 기준)

`reliability.py` 의 설계 문구는 *「역사 행을 다시 쓰지 않는다 · 마이그레이션 0」* 이다.
캐시 컬럼은 그 선택과 **정면으로 충돌한다** — 판정에 마커가 추가되면 기존 행의 캐시가
낡는다. 예외도 red 도 없이 평균만 달라진다.

그래서 충돌을 없애는 대신 **명시적 절차로 바꾼다**: 판정 함수 본문이 바뀌면
`_PREDICATE_BODY_SHA` 가 어긋나고, 이 테스트가 백필 리비전을 요구하며 red 가 된다.
(Grok claim-review `01a02f4f`: "sampled test is theater · 정의 변경이 진짜 위험")
"""
from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path

import pytest

from src.scorer.reliability import score_is_unreliable

_ROOT = Path(__file__).resolve().parents[3]
_RELIABILITY = _ROOT / "src" / "scorer" / "reliability.py"
_VERSIONS = _ROOT / "alembic" / "versions"

# 🔴 판정 **본문**(docstring 제외)의 AST 해시. 마커가 하나라도 늘거나 조건이 바뀌면 달라진다.
#    갱신할 때는 반드시 **백필 리비전을 함께** 만든다 — 그것이 이 상수의 존재 이유다.
_PREDICATE_BODY_SHA = "c1805045947495ef"

# 이 해시를 마지막으로 갱신한 백필 리비전. 판정이 바뀌면 새 리비전 번호로 올린다.
_BACKFILL_REVISION = "0046"


def _predicate_body_sha() -> str:
    tree = ast.parse(_RELIABILITY.read_text(encoding="utf-8"))
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "score_is_unreliable"
    )
    # docstring 은 판정이 아니다 — 설명을 고쳤다고 백필을 요구하면 가드가 미움받고 꺼진다.
    fn.body = [
        x for x in fn.body
        if not (isinstance(x, ast.Expr) and isinstance(x.value, ast.Constant)
                and isinstance(x.value.value, str))
    ]
    dumped = ast.dump(ast.Module(body=[fn], type_ignores=[]))
    return hashlib.sha256(dumped.encode()).hexdigest()[:16]


def test_predicate_change_requires_a_backfill_revision():
    """🔴 판정이 바뀌면 기존 행의 캐시가 낡는다 — 백필 없이는 통과시키지 않는다."""
    actual = _predicate_body_sha()
    assert actual == _PREDICATE_BODY_SHA, (
        f"`score_is_unreliable` 본문이 바뀌었다 ({_PREDICATE_BODY_SHA} → {actual}).\n"
        "`analyses.score_unreliable` 은 이 함수의 **캐시**이므로 기존 행이 낡았다.\n"
        "→ ① 새 alembic 리비전에서 전 행을 이 함수로 다시 채우고\n"
        "  ② 이 파일의 `_PREDICATE_BODY_SHA` 와 `_BACKFILL_REVISION` 을 갱신할 것.\n"
        "  백필 없이 해시만 고치면 평균이 조용히 틀린 채 초록이 된다."
    )


def test_the_named_backfill_revision_exists_and_calls_the_predicate():
    """🔴 리비전 번호만 적고 실제로 백필하지 않으면 위 가드는 서류다."""
    matches = list(_VERSIONS.glob(f"{_BACKFILL_REVISION}_*.py"))
    assert matches, f"백필 리비전 {_BACKFILL_REVISION} 파일이 없다"
    src = matches[0].read_text(encoding="utf-8")
    assert "score_is_unreliable" in src, (
        f"{matches[0].name} 이 판정 함수를 부르지 않는다 — SQL 로 판정을 다시 쓰면 "
        "정의가 두 벌이 되고, 이 리포는 이미 그 형태로 다쳤다(JSON 불린 발산)."
    )
    assert "score_unreliable" in src, f"{matches[0].name} 이 캐시 컬럼을 채우지 않는다"


def test_the_hash_guard_is_not_vacuous():
    """해시 계산이 깨져 있으면 위 단언이 늘 통과한다."""
    sha = _predicate_body_sha()
    assert re.fullmatch(r"[0-9a-f]{16}", sha), f"해시 형식이 깨졌다: {sha!r}"


# ── 쓰기 경로가 캐시를 실제로 채우는가 ────────────────────────────────────────
#
# 🔴 ORM 이벤트를 쓰지 않는다 (Grok `01a02f4f` Q1). 이 리포에는 모델 이벤트가 하나도 없고,
#    이벤트는 「어떤 쓰기도 잊을 수 없다」를 **보장하지 못한다**(bulk update·raw SQL·
#    alembic 데이터 마이그레이션은 발동하지 않는다). 쓰기 지점은 grep 가능한 3곳뿐이라
#    명시 대입이 더 정직하고, 누락은 아래 가드가 잡는다.

_WRITE_SITES = (
    ("src/worker/pipeline.py", "Analysis("),          # 통상 insert
    ("src/api/hook.py", "Analysis("),                 # CLI 훅 insert
    ("src/worker/pipeline.py", "locked.result = "),   # CLI supersede update
)


@pytest.mark.parametrize("rel,anchor", _WRITE_SITES)
def test_every_result_write_site_also_sets_the_cache(rel, anchor):
    """🔴 `result` 를 쓰는 곳은 캐시도 함께 쓴다 — 한 곳만 빠져도 그 행이 조용히 틀린다."""
    src = (_ROOT / rel).read_text(encoding="utf-8")
    assert anchor in src, f"{rel}: 앵커 {anchor!r} 가 사라졌다 — 이 가드가 공허하다"
    idx = src.index(anchor)
    window = src[idx:idx + 1400]
    assert "score_unreliable" in window, (
        f"{rel} 의 {anchor!r} 부근이 `score_unreliable` 을 설정하지 않는다.\n"
        "→ `score_unreliable=score_is_unreliable(result_dict)` 를 함께 쓸 것."
    )


def test_no_other_write_site_appeared():
    """🔴 공허화 차단 — `Analysis(` 생성이 늘면 위 목록이 낡는다."""
    hits = []
    for path in (_ROOT / "src").rglob("*.py"):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"(?<![A-Za-z_])Analysis\($", line.strip()) or \
               re.search(r"(?<![A-Za-z_])Analysis\(\s*$", line):
                hits.append(f"{path.relative_to(_ROOT).as_posix()}:{i}")
    assert len(hits) == 2, (
        f"`Analysis(` 생성 지점이 2곳이 아니다: {hits}\n"
        "→ 새 쓰기 경로가 생겼다면 `score_unreliable` 을 설정하고 _WRITE_SITES 에 추가할 것."
    )


# ── 캐시 값이 판정과 일치하는가 (계산 축) ─────────────────────────────────────

_CORPUS = [
    None, {},
    {"ai_review_status": "success"},
    {"ai_review_status": "api_error"},
    {"ai_review_status": "disabled"},
    {"static_analysis_incomplete": True},
    {"source": "cli"},
    {"breakdown": {"ai_defaults_applied": True}},
    {"breakdown": {"ai_defaults_applied": False}},
    {"static_uncovered_languages": ["rust"]},
    {"static_uncovered_languages": []},
]


def test_corpus_exercises_both_verdicts():
    assert {score_is_unreliable(r) for r in _CORPUS} == {True, False}


def test_truthy_marker_is_now_fail_closed():
    """🔴 `is True` → truthy (2026-08-24) — 불린이 아닌 참값을 흘려보내지 않는다.

    운영 실측: `ai_defaults_applied` 는 boolean 3,599행 + 키 없음 1,564행, **비-불린 0행**.
    즉 현재 데이터에서 이 변경은 증명 가능한 no-op 이고, 미래의 fail-open 만 닫는다.
    """
    assert score_is_unreliable({"breakdown": {"ai_defaults_applied": 1}}) is True
    assert score_is_unreliable({"breakdown": {"ai_defaults_applied": "yes"}}) is True
    assert score_is_unreliable({"breakdown": {"ai_defaults_applied": False}}) is False
    assert score_is_unreliable({"breakdown": {"ai_defaults_applied": 0}}) is False
    assert score_is_unreliable({"breakdown": {}}) is False
