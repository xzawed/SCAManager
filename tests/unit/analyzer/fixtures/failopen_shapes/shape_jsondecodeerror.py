"""형태 2 — JSON 파싱 실패를 `[]` 로 삼킨다 (구 탐지기도 잡던 관용구, 대조군).
Shape 2: JSONDecodeError swallowed as []. The old detector caught this one.
"""
from __future__ import annotations
import json
import subprocess  # nosec B404


class _Shape2:
    name = "shape_jsondecodeerror"

    def run(self, ctx) -> list:
        """JSON 파싱 실패 → 빈 결과."""
        try:
            r = subprocess.run(  # nosec B603 B607
                ["shape2", ctx.tmp_path], capture_output=True, text=True,
                timeout=30, check=False,
            )
            return json.loads(r.stdout)
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            return []
        except json.JSONDecodeError:
            return []
        except FileNotFoundError:
            return []
