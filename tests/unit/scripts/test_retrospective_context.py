"""회고 워크플로는 `context` 를 문자열로 만들고, 범위 소속을 정수 집합으로 본다 (회고 2026-09-16 P1-1 · P2-28).

## 사고

호출자가 `retro_scope.py --json` 을 파싱한 **객체**를 `context` 로 넘겼다. 워크플로는 그것을
템플릿 문자열에 이어 붙여 전 에이전트가 「세션 컨텍스트: [object Object]」를 받았고, 범위
대조(`String(context).includes(String(n))`)는 55/55 «브리프에 없음» 오경보를 냈다. 반대로
부분문자열 대조는 `#16842` 안의 `1684` 를 «언급됨» 으로 읽어 빠진 PR 을 숨길 수 있다.

## 어떻게 재는가

워크플로 런타임 밖에서는 스크립트 전체를 돌릴 수 없다(전역 `agent`·`phase` 가 필요하다).
그래서 두 순수 함수를 소스에서 떼어 **Node 로 실제 실행**하고, 배선은 주석을 걷어 낸 코드로
본다. Node 가 없으면 skip 이 아니라 red 다 — 못 재면 초록이 아니다.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

_WORKFLOW = Path(__file__).resolve().parents[3] / ".claude" / "workflows" / "retrospective.mjs"


def _function_source(src: str, name: str) -> str:
    """`function <name>(` 부터 중괄호가 닫힐 때까지 — 없으면 red."""
    start = src.find(f"function {name}(")
    assert start != -1, f"`function {name}` 이 워크플로에 없다 — 이름이 바뀌었으면 이 시험도 고칠 것"
    depth, i = 0, src.index("{", start)
    while True:
        depth += {"{": 1, "}": -1}.get(src[i], 0)
        if depth == 0:
            return src[start:i + 1]
        i += 1


def _node(expr: str):
    """두 헬퍼를 정의한 뒤 `expr` 의 값을 JSON 으로 돌려받는다."""
    node = shutil.which("node")
    if node is None:
        pytest.fail("node 가 없어 판정할 수 없다 — 못 재면 red (CI test-and-analyze 는 setup-node 가 있다)")
    src = _WORKFLOW.read_text(encoding="utf-8")
    prog = "\n".join([
        _function_source(src, "contextText"),
        _function_source(src, "prNumbersIn"),
        f"console.log(JSON.stringify({expr}))",
    ])
    out = subprocess.run([node, "--input-type=module", "-e", prog], capture_output=True,
                         text=True, encoding="utf-8", check=True)
    return json.loads(out.stdout)


def _code_without_comments() -> str:
    text = _WORKFLOW.read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"//.*", "", text)


def test_an_object_context_becomes_json_text():
    """🔴 객체는 JSON 문자열이 된다 — «[object Object]» 가 프롬프트에 들어가면 안 된다."""
    got = _node('contextText({prs: [1684, 1685], head: "abc"})')
    assert isinstance(got, str), got
    assert "[object Object]" not in got, got
    assert "1684" in got and "1685" in got, got


def test_string_and_missing_context_pass_through():
    """대조군 — 문자열은 그대로, 없는 값은 null 이다(빈 문자열로 바꾸지 않는다)."""
    assert _node('[contextText("호출자 브리프"), contextText(null), contextText(undefined)]') == [
        "호출자 브리프", None, None]


def test_pr_membership_is_by_whole_number_not_substring():
    """🔴 `#16842` 는 1684 를 언급하지 않는다 — 부분문자열 대조는 빠진 PR 을 숨긴다.

    SHA 안의 숫자(`291c9cae` 의 291)도 PR 번호가 아니다.
    """
    got = _node(
        '[prNumbersIn("#16842").has(1684), '
        'prNumbersIn(\'{"prs": [1684, 1685]}\').has(1685), '
        'prNumbersIn("#1684~#1743").has(1743), '
        'prNumbersIn("head 291c9cae").has(291)]'
    )
    assert got == [False, True, True, False], got


def test_the_workflow_wires_both_helpers():
    """배선 — 두 헬퍼를 실제로 쓰고, 부분문자열 대조가 남아 있지 않다."""
    code = _code_without_comments()
    assert re.search(r"const context = contextText\(opts\.context", code), (
        "context 가 contextText 를 거치지 않는다 — 객체가 그대로 프롬프트에 들어간다")
    assert "prNumbersIn(context)" in code, "범위 대조가 prNumbersIn 을 쓰지 않는다"
    assert not re.search(r"\.includes\(String\(n\)\)", code), "부분문자열 범위 대조가 남아 있다"
