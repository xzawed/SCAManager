"""fail-open — 크래시 헬퍼는 **부르지만** 올리지 않는다.

축 D 의 첫 판은 `empty_output_is_a_crash` **호출 자체**를 판별식의 신호로 셌다. 그러면
**헬퍼 호출은 남기고 `raise` 만 지우는** 되돌림에 눈먼다 — 이 래칫이 잡아야 할 바로 그 편집이다.

실물 좌표: `shellcheck.py::            if empty_output_is_a_crash(issues, r):` 의 갈래에서
`raise analysis_failed(...)` 만 `pass` 로 바꾸면 이 파일과 같은 모양이 된다. #1582 가 실측으로
세운 판별식(「이슈 0건 + 비정상 종료」)이 그대로 있는 것처럼 보이지만 아무것도 막지 않는다.
같은 형태가 `buf_lint.py` · `psscriptanalyzer.py` 에도 있다.

🔴 그래서 판정은 **`raise` 쪽**에 건다 — 호출 이름을 세지 않는다.
실측(Grok claim-review `01a05521`): 첫 판에서 이 모양은 `reasons == []` 였다.

The helper is called but nothing is raised: counting the call as the signal blinds the
ratchet to the exact edit it exists to catch.
"""
from __future__ import annotations

import json
import subprocess  # nosec B404

from src.analyzer.io.tools._common import empty_output_is_a_crash


class _Analyzer:
    name = "shape_helper_call_without_raise"

    def run(self, ctx) -> list:
        try:
            r = subprocess.run(  # nosec B603 B607
                ["probe", ctx.tmp_path], capture_output=True, text=True,
                timeout=30, check=False,
            )
            issues = [{"line": row.get("line", 0)} for row in json.loads(r.stdout or "[]")]
            if empty_output_is_a_crash(issues, r):
                # 🔴 여기에 `raise` 가 있어야 한다. 호출만 남으면 판별식은 장식이다.
                pass
            return issues
        except json.JSONDecodeError as exc:
            raise RuntimeError("probe produced unparseable JSON") from exc
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            return []
        except FileNotFoundError:
            return []
