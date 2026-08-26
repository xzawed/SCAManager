"""형태 1 — 비-JSON stdout 을 `[]` 로 삼킨다 (구 탐지기도 잡던 관용구, 대조군).
Shape 1: non-JSON stdout swallowed as []. The old detector caught this one.
"""
from __future__ import annotations
import json
import subprocess  # nosec B404


class _Shape1:
    name = "shape_startswith"

    def run(self, ctx) -> list:
        """비-JSON stdout → 빈 결과."""
        try:
            r = subprocess.run(  # nosec B603 B607
                ["shape1", ctx.tmp_path], capture_output=True, text=True,
                timeout=30, check=False,
            )
            if not r.stdout.strip().startswith("["):
                return []
            return json.loads(r.stdout)
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            return []
        except FileNotFoundError:
            return []
