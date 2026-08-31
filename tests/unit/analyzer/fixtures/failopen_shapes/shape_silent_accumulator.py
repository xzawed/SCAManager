"""형태 4 — 조용한 누산기. 크래시하면 파싱 루프가 0건이 되어 **`return []` 없이**
빈 리스트가 나간다. 구 탐지기는 `return []` 을 찾으므로 원리적으로 못 본다.
실물: `buf_lint.py` · `clippy.py`.
Shape 4: silent accumulator — an empty result with no `return []` at the parse site.
"""
from __future__ import annotations
import json
import subprocess  # nosec B404


class _Shape4:
    name = "shape_silent_accumulator"

    def run(self, ctx) -> list:
        """한 줄씩 파싱 — 크래시 시 0건이 그대로 «이슈 없음» 이 된다."""
        try:
            r = subprocess.run(  # nosec B603 B607
                ["shape4", ctx.tmp_path], capture_output=True, text=True,
                timeout=30, check=False,
            )
            issues = []
            for line in r.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    issues.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            return issues
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            return []
        except FileNotFoundError:
            return []
