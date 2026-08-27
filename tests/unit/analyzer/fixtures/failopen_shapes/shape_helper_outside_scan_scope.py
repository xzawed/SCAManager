"""형태 8 — fail-open 이 **검사 범위 밖 이름의 헬퍼**에 산다.

`run()` 은 제대로 raise 하므로 「크래시 판별식이 있다」를 만족한다. 그런데 실제 파싱은
`_parse*` 도 아닌 이름의 헬퍼가 하고, 거기서 실패를 `[]` 로 삼킨다. 탐지기가 함수 이름을
열거해 범위를 정하면 이 형태에 눈먼다 — 관용구 열거와 **같은 클래스의 결함**이다.

실물 후보: `ktlint.py::json_array_payload` · `slither.py::_extract_line_number` 처럼
`run`·`_parse*` 어느 쪽도 아닌 이름의 헬퍼들. 현재 그 헬퍼들에 `return []` 은 없지만
(2026-08-26 실측 0건), 범위를 이름으로 정하는 한 다음 어댑터가 여기로 샌다.

Shape 8: the fail-open lives in a helper whose name is outside the scan scope. Scoping the
detector by function name is the same failure class as enumerating idioms.
"""
from __future__ import annotations
import json
import subprocess  # nosec B404


class _Shape8:
    name = "shape_helper_outside_scan_scope"

    def run(self, ctx) -> list:
        """판별식은 있다 — 그런데 파싱 실패는 헬퍼가 조용히 삼킨다."""
        try:
            r = subprocess.run(  # nosec B603 B607
                ["shape8", ctx.tmp_path], capture_output=True, text=True,
                timeout=30, check=False,
            )
            if not r.stdout.strip().startswith("["):
                raise RuntimeError(f"shape8 did not analyze (exit={r.returncode})")
            return _extract_issues(r.stdout)
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            return []
        except FileNotFoundError:
            return []


def _extract_issues(text: str) -> list:
    """이름이 `_parse*` 가 아니라 범위 밖이다 — 여기서 삼킨 실패는 아무도 못 본다."""
    try:
        return list(json.loads(text))
    except json.JSONDecodeError:
        return []
