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

# 🔴 판정의 **행동**을 해시한다 — 소스 AST 가 아니다.
#
# ## 초판이 CI 를 거짓으로 빨갛게 만들었다 (Grok claim-review `01a02f70`, 실측 확인)
#
# 초판은 `ast.dump(score_is_unreliable)` 를 해시했다. 그 출력은 **파이썬 버전마다 다르다** —
# 3.12 는 빈 기본값(`posonlyargs=[]` 등)을 찍고 3.14 는 생략한다. 같은 소스에 대해:
#
#     py3.14  sha=c1805045947495ef  dump_len=2124   ← 여기서 핀을 떴다
#     py3.12  sha=32185cf588a13b92  dump_len=2426   ← CI 인터프리터
#
# 즉 CI 는 「판정 본문이 바뀌었다」며 백필을 요구했을 것이다 — **본문은 그대로인데.**
# 거짓 사유로 red 를 내는 가드는 무집행보다 나쁘다: 사람을 상수 갈아끼우기로 훈련시킨다.
#
# ## 그리고 정작 봐야 할 것을 못 봤다
#
# `ast.dump` 에는 **이름**만 있고 그 이름이 묶인 **값**은 없다. 그래서 아래가 전부 통과했다:
#     `_AI_UNVERIFIED_STATUSES` 에 상태 추가    → 행동 변화, 해시 불변
#     `AI_REVIEW_FAILED_STATUSES` 에 상태 추가  → 행동 변화, 해시 불변(다른 모듈)
#     `ai_review_failed` 본문 변경              → 행동 변화, 해시 불변(호출만 보인다)
#
# ## 그래서 무엇을 해시하는가
#
# **운영에 실재하는 키**로 만든 표본 전체의 판정 결과 벡터. 키 목록은 운영 DB 실측이다
# (2026-08-24, `json_object_keys` 집계 19키). 판정이 기존 행의 결과를 바꾸면 — 원인이
# 함수 본문이든 frozenset 이든 위임 함수든 — 벡터가 바뀐다. 파이썬 버전에는 의존하지 않고,
# 주석·어노테이션·이름 변경 같은 무해한 편집에는 발동하지 않는다.
#
# Hash the predicate's BEHAVIOUR over a corpus built from keys that actually exist in production,
# not its AST: ast.dump is version-dependent (measured) and blind to the frozensets and delegate.
_BEHAVIOUR_SHA = "6e36c9b592da815b"

# 이 벡터를 마지막으로 백필한 리비전. 판정이 바뀌면 새 리비전 번호로 올린다.
_BACKFILL_REVISION = "0046"

# 🔴 운영 DB 실측 최상위 키 19종 (2026-08-24). 판정과 무관한 키도 넣는다 —
#    「무관하다」가 계속 참인지도 이 벡터가 지켜본다.
_PRODUCTION_KEYS = (
    "issues", "file_feedbacks", "ai_suggestions", "direction_feedback",
    "commit_message_feedback", "code_quality_feedback", "ai_summary", "test_feedback",
    "breakdown", "security_feedback", "ai_review_status", "source",
    "ai_review_truncated", "ai_review_error_type", "static_analysis_incomplete",
    "ai_review_error_status_code", "grade", "static_uncovered_languages", "score",
)

# 키마다 시도할 값 — 참/거짓·존재/부재를 훑는다.
_VALUES = {
    "ai_review_status": ["success", "api_error", "parse_error", "disabled",
                         "no_api_key", "empty_diff", "skipped", "timeout", None],
    "source": ["pr", "push", "cli", None],
    "static_analysis_incomplete": [True, False, None],
    "ai_review_truncated": [True, False, None],
    "static_uncovered_languages": [["rust"], [], None],
    "breakdown": [{"ai_defaults_applied": True}, {"ai_defaults_applied": False}, {}, None],
    "ai_review_error_type": ["overloaded", None],
    "ai_review_error_status_code": [529, None],
    "grade": ["A", None],
    "score": [95, None],
}


def _corpus():
    """운영 키 구조에서 **파생한** 표본. 손으로 나열하지 않는다."""
    samples = [None, {}]
    base = {k: "x" for k in _PRODUCTION_KEYS if k not in _VALUES}
    for key, values in sorted(_VALUES.items()):
        for value in values:
            sample = dict(base)
            if value is not None:
                sample[key] = value
            samples.append(sample)
    # 조합 축 — 두 마커가 동시에 있을 때의 단락 순서를 고정한다.
    samples.append({"source": "cli", "ai_review_status": "success"})
    samples.append({"ai_review_status": "api_error", "static_analysis_incomplete": False})
    samples.append({"breakdown": {"ai_defaults_applied": True}, "ai_review_status": "success"})
    return samples


def _verdict_bits():
    return "".join("1" if score_is_unreliable(s) else "0" for s in _corpus())


def _behaviour_sha():
    """표본 전체의 판정 결과 벡터 해시 — 파이썬 버전 비의존."""
    return hashlib.sha256(_verdict_bits().encode()).hexdigest()[:16]


def test_predicate_behaviour_change_requires_a_backfill_revision():
    """🔴 판정 **결과**가 바뀌면 기존 행의 캐시가 낡는다 — 백필 없이는 통과시키지 않는다."""
    actual = _behaviour_sha()
    assert actual == _BEHAVIOUR_SHA, (
        f"`score_is_unreliable` 의 판정 결과가 바뀌었다 ({_BEHAVIOUR_SHA} -> {actual}).\n"
        "`analyses.score_unreliable` 은 이 함수의 **캐시**이므로 기존 행이 낡았다.\n"
        "-> (1) 새 alembic 리비전에서 전 행을 이 함수로 다시 채우고\n"
        "   (2) 이 파일의 `_BEHAVIOUR_SHA` 와 `_BACKFILL_REVISION` 을 갱신할 것.\n"
        "   백필 없이 해시만 고치면 평균이 조용히 틀린 채 초록이 된다.\n"
        "   (주석·어노테이션만 고쳤다면 이 벡터는 바뀌지 않는다 — 바뀌었다면 행동이 바뀐 것이다.)"
    )


def test_the_behaviour_hash_does_not_depend_on_the_interpreter():
    """🔴 초판이 여기서 무너졌다 — 계기가 인터프리터에 따라 다르면 CI 를 거짓으로 빨갛게 한다.

    결과 벡터는 파이썬 자료형 연산만 쓰므로 그런 의존이 없다. 그 사실을 구조로 못박는다:
    벡터가 두 판정을 모두 포함하고, 재실행에 안정적이며, AST 표현이 섞여 있지 않다.
    """
    bits = _verdict_bits()
    assert set(bits) == {"0", "1"}, "표본이 한쪽 판정으로 쏠렸다 — 벡터가 무의미하다"
    assert len(bits) == len(_corpus())
    assert _behaviour_sha() == _behaviour_sha(), "판정에 숨은 상태가 있다"
    # 🔴 문자열 검색으로 보면 **이 파일의 설명 주석**이 걸린다(실측 — 산문 가드는
    #    양방향으로 틀린다). 호출을 AST 로 찾는다.
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    dumps = [
        n.lineno for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == "dump" and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "ast"
    ]
    assert not dumps, (
        f"`ast.dump` 호출이 다시 들어왔다 (줄 {dumps}) — 그 출력은 파이썬 버전마다 다르다"
        " (실측 3.12 dump_len=2426 vs 3.14 dump_len=2124)."
    )


def test_the_corpus_covers_every_marker_the_predicate_uses():
    """🔴 공허화 차단 — 마커 키가 표본에 없으면 그 축의 변경을 못 본다."""
    corpus_keys = {k for s in _corpus() if isinstance(s, dict) for k in s}
    for marker in ("ai_review_status", "static_analysis_incomplete", "source",
                   "breakdown", "static_uncovered_languages"):
        assert marker in corpus_keys, f"표본에 마커 {marker!r} 가 없다"


def test_status_sets_and_delegate_are_inside_the_hashed_surface():
    """🔴 초판이 못 본 축 — frozenset·위임 함수 변경이 벡터를 실제로 움직이는가.

    `_AI_UNVERIFIED_STATUSES` 에 없는 상태(`skipped`·`timeout`)가 표본에 있고 지금은
    신뢰 가능으로 판정된다. 누가 그것을 집합에 넣으면 벡터가 바뀌어 백필이 요구된다.
    """
    assert score_is_unreliable({"ai_review_status": "skipped"}) is False, (
        "표본 전제가 깨졌다 — 이미 신뢰불가면 그 축의 변경 탐지가 무뎌진다"
    )
    assert score_is_unreliable({"ai_review_status": "timeout"}) is False
    assert score_is_unreliable({"ai_review_status": "api_error"}) is True, (
        "위임(`ai_review_failed`)의 판정이 표본에 반영되지 않는다"
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


_WRITE_FILES = ("src/worker/pipeline.py", "src/api/hook.py")


def _analysis_constructions() -> list[tuple[str, int, set[str]]]:
    """`Analysis(...)` 생성 호출 — (파일, 줄, 키워드 인자 이름들)."""
    out = []
    for rel in _WRITE_FILES:
        tree = ast.parse((_ROOT / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "Analysis"):
                out.append((rel, node.lineno, {k.arg for k in node.keywords if k.arg}))
    return out


def _result_attribute_writes() -> list[tuple[str, int, str]]:
    """`<obj>.result = ...` 대입 — (파일, 줄, 객체명)."""
    out = []
    for rel in _WRITE_FILES:
        tree = ast.parse((_ROOT / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for tgt in node.targets:
                if (isinstance(tgt, ast.Attribute) and tgt.attr == "result"
                        and isinstance(tgt.value, ast.Name)):
                    out.append((rel, node.lineno, tgt.value.id))
    return out


def test_the_write_site_scan_is_not_vacuous():
    """🔴 스캔이 0건이면 아래 단언이 전부 공허하다."""
    ctors = _analysis_constructions()
    assert len(ctors) == 2, (
        f"`Analysis(...)` 생성이 2곳이 아니다: {[(f, l) for f, l, _ in ctors]}\n"
        "→ 새 쓰기 경로가 생겼다면 `score_unreliable` 을 설정할 것."
    )
    assert _result_attribute_writes(), "`.result = ` 대입을 못 찾았다 — 파싱이 깨졌다"


def test_every_analysis_construction_sets_the_cache():
    """🔴 생성 시 캐시를 함께 넣는다 — **AST 키워드 인자**로 확인한다.

    초판은 `Analysis(` 이후 1400자에 `score_unreliable` 문자열이 있는지 봤다. 그런데
    같은 창에 `_claim_and_supersede_cli(..., _score_unreliable)` 호출이 있어
    **부분 문자열이 걸려** 대입을 지워도 초록이었다(뮤테이션으로 실측).
    산문 가드는 양방향으로 틀린다 — 구조로 본다.
    Substring matching gave a false pass; assert the keyword argument in the AST instead.
    """
    missing = [
        f"{rel}:{line}" for rel, line, kwargs in _analysis_constructions()
        if "score_unreliable" not in kwargs
    ]
    assert not missing, (
        f"`Analysis(...)` 가 캐시를 설정하지 않는다: {missing}\n"
        "→ `score_unreliable=score_is_unreliable(result_dict)` 를 인자로 넣을 것. "
        "빠지면 server_default(false) 가 들어가 신뢰 불가 행이 평균에 섞인다."
    )


def test_every_result_attribute_write_updates_the_cache():
    """🔴 `x.result = ...` 를 쓰면 같은 객체의 `x.score_unreliable` 도 갱신한다.

    CLI supersede(`pipeline.py`)가 이 경로다. 빠뜨리면 CLI 행이 full 분석으로 승격된
    뒤에도 옛 판정으로 남아 평균이 조용히 틀어진다.
    """
    problems = []
    for rel, line, obj in _result_attribute_writes():
        tree = ast.parse((_ROOT / rel).read_text(encoding="utf-8"))
        # 🔴 짝은 **같은 함수 안**에 있어야 한다. 파일 전체를 훑으면
        #    `def f(): x.result = a` 와 `def g(): x.score_unreliable = b` 가 짝으로 잡혀
        #    정작 그 쓰기는 캐시를 갱신하지 않는다(Grok `01a02f70` Q5-6).
        owner = None
        for fn in ast.walk(tree):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))                     and fn.lineno <= line <= (fn.end_lineno or fn.lineno):
                if owner is None or fn.lineno > owner.lineno:
                    owner = fn          # 가장 안쪽 함수
        scope = owner if owner is not None else tree
        paired = any(
            isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Attribute) and t.attr == "score_unreliable"
                    and isinstance(t.value, ast.Name) and t.value.id == obj
                    for t in n.targets)
            for n in ast.walk(scope)
        )
        if not paired:
            where = owner.name if owner is not None else "<module>"
            problems.append(f"{rel}:{line} ({obj}.result, in {where})")
    assert not problems, (
        f"`.result` 를 다시 쓰면서 캐시를 갱신하지 않는다: {problems}\n"
        f"→ 같은 객체에 `score_unreliable = score_is_unreliable(result_dict)` 를 대입할 것."
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


def test_the_partial_index_name_matches_between_model_and_migration():
    """🔴 모델과 마이그레이션의 인덱스 **이름이 같아야** 한다.

    이름이 갈리면 운영에는 마이그레이션이 만든 인덱스가 남고 ORM 은 다른 이름을 기대해
    ORM↔alembic 정합이 깨진다. 그 축(`test_orm_alembic_parity`)은 **PostgreSQL 이 있을 때만**
    돌아서, 로컬에서는 이 뮤테이션이 초록이었다(실측). 여기서 값싸게 메운다.

    The parity axis is PG-gated, so this cheap name check closes the local blind spot.
    """
    model_src = (_ROOT / "src" / "models" / "analysis.py").read_text(encoding="utf-8")
    migration = next(_VERSIONS.glob(f"{_BACKFILL_REVISION}_*.py")).read_text(encoding="utf-8")

    names = set(re.findall(r'"(ix_analyses_[a-z_]+)"', model_src))
    assert names, "모델에서 인덱스 이름을 하나도 못 읽었다 — 이 가드가 공허하다"

    target = "ix_analyses_reliable_scores"
    assert target in names, (
        f"모델이 {target} 을 선언하지 않는다 (선언된 것: {sorted(names)}). "
        "이름을 바꾸려면 마이그레이션도 함께 바꿀 것."
    )
    assert target in migration, (
        f"마이그레이션 {_BACKFILL_REVISION} 이 {target} 을 만들지 않는다 — 모델과 갈렸다."
    )
    # 술어도 같아야 한다 — 이름만 같고 조건이 다르면 계획이 인덱스를 못 쓴다.
    predicate = "score IS NOT NULL AND score_unreliable IS NOT TRUE"
    assert predicate in model_src, f"모델 부분 인덱스 술어가 다르다 (기대: {predicate})"
    assert predicate in migration, f"마이그레이션 부분 인덱스 술어가 다르다 (기대: {predicate})"
