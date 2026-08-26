"""`truncate_html_message` 가 닫는 태그를 붙인 **뒤에** 다시 잘라 깨진 HTML 을 낸다 (감사 C4, #1519).

함수의 존재 이유가 「절단이 Telegram 400(parse error)을 만들지 않게」다. 그런데 마지막 줄이

    return (out + suffix)[:max_length]

라서, 닫는 태그를 다 붙인 결과가 `max_length` 를 넘으면 **그 닫는 태그 한가운데를 자른다.**
막으려던 것을 마지막 한 줄이 다시 만든다.

실측 (nest = blockquote·pre·code·b·i·u·s, 닫는 태그 합 42자 > 예약 40자, max_length=200):

    ...xxxxx</s></u></i></b></code></pre></blockquote     <- `>` 가 없다
    balanced = False, leftover open tags = ['blockquote']

Telegram 은 이것을 400 으로 거절하고 **알림이 통째로 사라진다** — 잘린 알림이 아니라 무알림이다.

🔴 오늘 운영 템플릿(`<b>`·`<strong>`·`<code>`·`<a>`·`<i>`)의 중첩은 얕아 40자를 넘지
않으므로 **현재는 잠복**이다. 그러나 `_HTML_CLOSE_RESERVE = 40` 은 「이 정도면 되겠지」이고,
넘는 순간 아무 경고 없이 함수의 계약이 깨진다. 상수를 키우는 것은 같은 도박을 더 크게 하는
것이라, 예약 대신 **결과가 들어갈 때까지 본문을 줄이는** 방식으로 바꾼다.

The final clamp can slice through the closing tags this function just appended, producing exactly
the malformed HTML it exists to prevent. Latent with today's templates, unbounded in principle.
"""
from __future__ import annotations

import re

import pytest

from src.notifier._common import truncate_html_message

_TAG = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9-]*)(?:\s[^>]*)?>")

# 닫는 태그 합이 커지도록 중첩을 깊게 — Telegram 이 실제로 지원하는 태그만 쓴다.
# Telegram supports these; nesting them makes the closing run long.
_DEEP_NEST = ["blockquote", "pre", "code", "b", "i", "u", "s"]


def _unbalanced_reason(html: str) -> str | None:
    """well-formed 가 아니면 이유를, 맞으면 None 을 돌려준다."""
    if html.rfind("<") > html.rfind(">"):
        return f"끝에 닫히지 않은 태그 조각이 있다: {html[html.rfind('<'):]!r}"
    stack: list[str] = []
    for m in _TAG.finditer(html):
        closing, name = m.group(1), m.group(2).lower()
        if closing:
            if not stack or stack[-1] != name:
                return f"짝이 맞지 않는 닫는 태그 </{name}> (스택 {stack})"
            stack.pop()
        else:
            stack.append(name)
    if stack:
        return f"닫히지 않은 태그가 남았다: {stack}"
    return None


def _closing_run_length(tags: list[str]) -> int:
    return sum(len(f"</{t}>") for t in tags)


# ─── 계기 자기검증 ───────────────────────────────────────────────────────────


def test_the_probe_closing_run_is_long_enough_to_break_a_fixed_reserve():
    """🔴 전제 — 이 파일이 쓰는 중첩의 닫는 태그 합이 충분히 긴가.

    짧으면 「안 깨졌다」가 「고쳤다」가 아니라 「애초에 경계를 안 건드렸다」가 된다.
    40 은 이 결함을 만들던 고정 예약값이다 — 예약이 사라졌어도 그 눈금으로 재는 것이
    「그때 깨졌던 입력을 지금은 통과한다」를 보장한다.
    """
    assert _closing_run_length(_DEEP_NEST) > 40, (
        f"닫는 태그 합 {_closing_run_length(_DEEP_NEST)} 가 40 이하다 — 프로브가 무력하다"
    )


def test_the_checker_catches_a_known_broken_string():
    """🔴 전제 — 검사기가 실제로 깨진 HTML 을 잡는가."""
    assert _unbalanced_reason("<b>hi</b") is not None
    assert _unbalanced_reason("<b>hi") is not None
    assert _unbalanced_reason("<b>hi</b>") is None


# ─── 결함 ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("max_length", [60, 100, 200, 500])
def test_deep_nesting_never_yields_a_severed_closing_tag(max_length):
    """닫는 태그 줄이 길어도 출력은 well-formed 여야 한다.

    이것이 이 함수의 유일한 존재 이유다 — 깨진 HTML 은 Telegram 400 이고,
    400 은 잘린 알림이 아니라 **무알림**이다.
    """
    text = "".join(f"<{t}>" for t in _DEEP_NEST) + ("x" * 500)
    out = truncate_html_message(text, max_length)

    assert len(out) <= max_length, f"길이 계약 위반: {len(out)} > {max_length}"
    reason = _unbalanced_reason(out)
    assert reason is None, f"max_length={max_length}: {reason}\n출력 꼬리: {out[-70:]!r}"


def test_closing_tags_survive_the_length_clamp_exactly_at_the_boundary():
    """예약분과 닫는 태그 합이 **정확히** 맞부딪히는 지점에서도 깨지지 않는다.

    경계 한 칸 차이로 자르는지를 본다 — 여유가 있을 때만 도는 테스트는 이 결함을 놓친다.
    """
    for extra in range(0, 8):
        nest = _DEEP_NEST + ["b"] * extra
        text = "".join(f"<{t}>" for t in nest) + ("y" * 400)
        out = truncate_html_message(text, 300)
        reason = _unbalanced_reason(out)
        assert reason is None, f"extra={extra}: {reason}\n출력 꼬리: {out[-70:]!r}"
        assert len(out) <= 300


# ─── 대조군 ──────────────────────────────────────────────────────────────────


def test_shallow_nesting_still_keeps_as_much_content_as_before():
    """대조군 — 얕은 중첩(운영 템플릿)에서 본문이 줄어들지 않는다.

    고정 예약(40)을 없애는 변경이라, 오히려 **더 많이** 담겨야 정상이다.
    여기가 red 면 이 PR 이 알림 본문을 깎은 것이다.
    """
    text = "<b>" + ("z" * 500) + "</b>"
    out = truncate_html_message(text, 200)
    assert _unbalanced_reason(out) is None
    assert len(out) <= 200
    # 예약 40 을 쓰던 구현은 본문 z 를 156자만 담았다.
    assert out.count("z") > 156, f"본문이 오히려 줄었다 — z {out.count('z')}자"


def test_text_within_limit_is_returned_untouched():
    """대조군 — 한도 안이면 손대지 않는다."""
    text = "<b>short</b>"
    assert truncate_html_message(text, 1000) == text

@pytest.mark.parametrize("max_length", [-5, -1, 0, 1, 2])
def test_length_contract_holds_for_degenerate_limits(max_length):
    """🔴 퇴화 입력 — 음수·영·접미사보다 짧은 한도에서도 계약을 지킨다.

    음수를 그대로 슬라이스하면 `[:max_length]` 가 **뒤에서** 잘라 출력이 오히려
    0 을 넘는다. 상한을 먼저 0 으로 묶어 닫았다.
    """
    out = truncate_html_message("<b>hello world</b>", max_length)
    assert len(out) <= max(max_length, 0), f"max_length={max_length} 인데 {out!r}"
    assert _unbalanced_reason(out) is None


@pytest.mark.parametrize("max_length", [-5, -1, 0])
def test_plain_truncate_also_holds_the_contract_on_negative_limits(max_length):
    """🔴 같은 모듈의 `truncate_message` 도 같은 구멍이 있었다.

    실측(고치기 전): `truncate_message("hello world", -1)` -> `".."` (길이 2).
    그 함수의 docstring 이 「출력 길이 ≤ max_length 보장」이라고 적어 둔 채였다.
    C4 검증 중 Grok 이 짚어 같은 PR 에서 닫았다 — 한 줄이고 같은 계약이다.
    """
    from src.notifier._common import truncate_message

    out = truncate_message("hello world", max_length)
    assert len(out) <= max(max_length, 0), f"max_length={max_length} 인데 {out!r}(len {len(out)})"
