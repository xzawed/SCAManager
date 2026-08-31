"""fail-open — `if` 가 감싼 것은 판별식이 아니라 **try/except 통째**다.

축 D 의 첫 판은 「`except` **밖의** `if` 안에 `raise` 가 있는가」를 `ast.walk(If)` 로 물었다.
그러면 `if` 는 except 밖인데 그 안의 `raise` 는 **중첩된 except 안**인 경우가 통과한다 —
들여쓰기 한 번짜리 우회이고, 이 파일이 적은 규칙(「except 안의 raise 는 세지 않는다」)과도
정면으로 어긋난다.

여기서 감싸는 `if` 는 **언어 게이트**다 — 그럴듯하지만 도구 출력을 전혀 보지 않는다.
살아 있는 `raise` 는 `JSONDecodeError` 핸들러의 것뿐이라 잡는 것은 「파싱이 예외를 냈다」뿐이고,
크래시 stdout 이 깨끗한 것과 바이트가 같으면 여전히 «이슈 0건 · 완전» 이다.

🔴 `if True:` 로 쓰지 않는다 — CodeQL 이 `py/constant-conditional-expression` 과
`py/unreachable-statement` 로 잡는다(실측, PR #1588). 언어 게이트가 더 현실적이기도 하다:
누군가 실제로 쓸 법한 모양이라야 이 픽스처가 지키는 값이 있다.

🔴 그래서 판정을 **`raise` 쪽**에 건다: 「`raise` 가 except 밖이고 어떤 `if` 아래인가」.
`raise` 가 except 밖이면 그것을 감싼 `if` 도 반드시 except 밖이므로 한 조건이면 족하다.
실측(Grok claim-review `01a05521`): 첫 판에서 이 모양은 `reasons == []` 였다.

The `if` wraps the whole try/except, not a predicate: the only live raise is still inside an
except handler, so anchoring on the `if` lets a one-indent edit pass.
"""
from __future__ import annotations

import json
import subprocess  # nosec B404


_SUPPORTED = frozenset({"shell"})


class _Analyzer:
    name = "shape_if_wraps_the_except_raise"

    def run(self, ctx) -> list:
        # 🔴 언어 게이트 — 그럴듯하지만 **도구 출력을 보지 않는다.** 판별식이 아니다.
        if ctx.language in _SUPPORTED:
            try:
                r = subprocess.run(  # nosec B603 B607
                    ["probe", ctx.tmp_path], capture_output=True, text=True,
                    timeout=30, check=False,
                )
                rows = json.loads(r.stdout or "[]")
                return [{"line": row.get("line", 0)} for row in rows]
            except json.JSONDecodeError as exc:
                raise RuntimeError("probe produced unparseable JSON") from exc
            except subprocess.TimeoutExpired:
                ctx.timed_out = True
                return []
            except FileNotFoundError:
                return []
        return None  # 🔴 `return []` 이 아니다 — 그러면 축 B 가 켜져 D 를 격리하지 못한다.
