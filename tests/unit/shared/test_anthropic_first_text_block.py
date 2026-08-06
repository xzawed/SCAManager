"""`first_text_block` 회귀 가드 — `content[0].text` 가정이 만든 조용한 전량 사망을 막는다.

## 왜 필요한가 (2026-08-06 5+1 회고 P1 · backlog R61)

`src/` 3곳 + `.claude/hooks/doc_review_gate.py` 1곳이 Anthropic 응답을 **`content[0].text`**
로 인덱싱하고 있었다. 그 관용구는 **첫 블록이 항상 text 라고 가정**한다. 그러나 `content` 는
블록 **배열**이고 thinking(확장 사고)·tool_use 가 앞설 수 있다.

🔴 **왜 조용한가**: 네 호출부가 전부 `except Exception` 안에 있다. 그래서 `AttributeError` 는
`api_error` 로 삼켜지고, 운영자는 *"AI 리뷰가 왜 다 실패하지"* 만 보게 된다 — `#1289`(빈 env 가
기본값을 덮은 P0)와 **결말이 같고 원인만 다른** 클래스다. 모델이나 설정을 한 번 바꾸면
전량 사망한다.

## 이 테스트가 고정하는 것

1. thinking 이 앞서도 **text 를 찾아낸다**
2. text 가 없으면 **조용히 `""` 를 반환하지 않고 `ValueError`** — 빈 문자열은 하류에서
   "빈 응답" 과 구별되지 않아 *무엇이 잘못됐는지 모르는* 실패가 된다
3. 🔴 **호출부 배선** — `content[0]` 직접 인덱싱이 다시 들어오면 red (정의만 하고 안 쓰면 dead code)
"""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.shared.anthropic_caching import first_text_block

_ROOT = Path(__file__).resolve().parents[3]


def _block(btype: str, **kw) -> SimpleNamespace:
    return SimpleNamespace(type=btype, **kw)


def test_returns_text_when_it_is_the_only_block():
    msg = SimpleNamespace(content=[_block("text", text="hello")])
    assert first_text_block(msg) == "hello"


def test_skips_thinking_block_that_precedes_the_text():
    """🔴 이 케이스가 결함의 실체다 — 구 코드는 여기서 `AttributeError` 로 죽었다."""
    msg = SimpleNamespace(content=[
        _block("thinking", thinking="…내부 추론…"),
        _block("text", text='{"score": 1}'),
    ])
    assert first_text_block(msg) == '{"score": 1}'


def test_skips_tool_use_block_that_precedes_the_text():
    msg = SimpleNamespace(content=[
        _block("tool_use", id="t1", name="x", input={}),
        _block("text", text="ok"),
    ])
    assert first_text_block(msg) == "ok"


def test_old_indexing_would_have_failed_on_the_same_input():
    """🔴 대조군 — 이 테스트가 *실제 회귀*를 다루는지 증명한다.

    같은 입력에 구 관용구(`content[0].text`)를 적용하면 죽는다는 것을 여기서 보인다.
    이것이 없으면 위 테스트들이 '원래 잘 되던 것' 을 확인하는 공허한 가드일 수 있다.
    """
    msg = SimpleNamespace(content=[
        _block("thinking", thinking="…"),
        _block("text", text="ok"),
    ])
    with pytest.raises(AttributeError):
        _ = msg.content[0].text          # 구 관용구
    assert first_text_block(msg) == "ok"  # 신 헬퍼


def test_raises_rather_than_returning_empty_when_no_text_block():
    """조용한 `""` 는 '빈 응답' 과 구별되지 않는다 — 원인을 말하는 예외가 낫다."""
    msg = SimpleNamespace(content=[_block("tool_use", id="t1", name="x", input={})])
    with pytest.raises(ValueError, match="text 블록이 없다"):
        first_text_block(msg)


def test_raises_on_empty_content():
    with pytest.raises(ValueError):
        first_text_block(SimpleNamespace(content=[]))


def test_tolerates_magicmock_blocks_whose_type_is_auto_generated():
    """🔴 `MagicMock(text=...)` 은 `.type` 이 **자동 생성**돼 None 이 아니다.

    초판 헬퍼가 `btype is None` 만 허용해 이 목을 전부 탈락시켰고, **기존 테스트 20건이
    red** 로 그것을 잡았다. 리포 전반이 이 형태로 Anthropic 응답을 목킹하므로 고정한다.
    (판별 계약: *명시적으로 비-text 라고 선언한 블록만* 건너뛴다.)
    """
    from unittest.mock import MagicMock

    msg = SimpleNamespace(content=[MagicMock(text='{"text": "ok"}')])
    assert first_text_block(msg) == '{"text": "ok"}'


def test_still_skips_a_block_that_explicitly_declares_a_non_text_type():
    """대조군 — 위 완화가 판별을 죽이지 않았는지. thinking 은 여전히 건너뛴다."""
    msg = SimpleNamespace(content=[
        _block("thinking", thinking="…", text="이건 읽으면 안 된다"),
        _block("text", text="정답"),
    ])
    assert first_text_block(msg) == "정답"


def test_tolerates_blocks_without_a_type_field():
    """구 SDK·테스트 목처럼 `type` 이 없는 객체도 `.text` 가 있으면 받는다."""
    msg = SimpleNamespace(content=[SimpleNamespace(text="legacy")])
    assert first_text_block(msg) == "legacy"


# ── 배선 (정의 ≠ 사용 — 3-불변식 ③) ──────────────────────────────────────
#
# 🔴 정규식이 아니라 **AST** 로 본다 (Grok claim-review 6580850b 적발).
# 초판은 `\.content\[0\]` 부재만 봐서 아래가 전부 통과했다:
#   · `blocks = response.content` → `blocks[0].text`   (변수 경유)
#   · `content[1]` · `content[i]` · `content[-1]`      (다른 첨자)
#   · dead code 에 헬퍼 호출을 남기고 라이브 경로는 옛 관용구  (사용 단언도 green)
# AST 는 **`.content` 에 대한 모든 첨자 접근**과 **`.content` 를 담은 지역 변수의 첨자**를
# 함께 본다. 산문/문자열 매칭이 아니라 구조를 보는 것이 불변식 ① 의 요구다.

import ast


def _content_subscripts(source: str) -> list[str]:
    """`.content` 첨자 접근 전부 — 직접 + 지역 변수 경유. / All subscripts of `.content`."""
    tree = ast.parse(source)
    hits: list[str] = []
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
            continue
        # 이 스코프에서 `X = <...>.content` 로 묶인 이름 수집
        aliases: set[str] = set()
        for node in ast.walk(func):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Attribute)                     and node.value.attr == "content":
                aliases |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        for node in ast.walk(func):
            if not isinstance(node, ast.Subscript):
                continue
            v = node.value
            if isinstance(v, ast.Attribute) and v.attr == "content":
                hits.append(f"line {node.lineno}: <...>.content[...]")
            elif isinstance(v, ast.Name) and v.id in aliases:
                hits.append(f"line {node.lineno}: {v.id}[...] (= <...>.content 별칭)")
    return hits


_CALL_SITES = (
    "src/analyzer/io/ai_review.py",
    "src/services/dashboard_service.py",
    "src/services/repo_insight_service.py",
    ".claude/hooks/doc_review_gate.py",
    "scripts/i18n_comments/translate_comments.py",
)


@pytest.mark.parametrize("rel", _CALL_SITES)
def test_call_site_does_not_index_content_zero(rel: str):
    """🔴 `content[0]` 직접 인덱싱이 다시 들어오면 red.

    헬퍼를 만들어 두고 호출부가 옛 관용구로 돌아가면 결함이 그대로 살아난다 —
    정의만 있고 배선이 없는 상태를 이 가드가 막는다.
    """
    src = (_ROOT / rel).read_text(encoding="utf-8")
    hits = [m.group(0) for m in re.finditer(r"\.content\[0\]", src)]
    assert not hits, (
        f"{rel} 이 `content[0]` 을 직접 인덱싱한다 — 첫 블록이 text 가 아니면 조용히 죽는다.\n"
        "→ `first_text_block(...)`(src) 또는 `_first_text_block(...)`(훅)을 쓸 것."
    )


@pytest.mark.parametrize("rel", _CALL_SITES)
def test_call_site_actually_uses_the_helper(rel: str):
    """부재만 확인하면 '아무 데서도 응답을 안 읽는' 상태도 통과한다 — 사용을 함께 단언."""
    src = (_ROOT / rel).read_text(encoding="utf-8")
    assert "first_text_block(" in src, f"{rel} 이 헬퍼를 쓰지 않는다"


def test_hook_duplicate_matches_the_src_helper_behaviour():
    """🔴 훅은 standalone 이라 `src` 를 import 할 수 없어 헬퍼가 **중복**이다.

    중복은 갈라진다 — 두 구현이 같은 입력에 같은 답을 내는지 여기서 고정한다.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_gate_probe", _ROOT / ".claude" / "hooks" / "doc_review_gate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    cases = [
        [_block("text", text="a")],
        [_block("thinking", thinking="…"), _block("text", text="b")],
        [SimpleNamespace(text="c")],
    ]
    for content in cases:
        msg = SimpleNamespace(content=content)
        assert mod._first_text_block(msg) == first_text_block(msg)

    with pytest.raises(ValueError):
        mod._first_text_block(SimpleNamespace(content=[_block("tool_use", id="t", name="x", input={})]))
