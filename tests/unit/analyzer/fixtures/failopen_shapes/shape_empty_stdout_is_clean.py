"""형태 6 — 빈 stdout 을 «깨끗함» 으로 읽는다. 항상 문서를 내보내는 도구에서는
빈 출력이 곧 크래시다(실측: sqlfluff clean 은 `[{"violations": []}]`, 빈값이 아니다).
실물: `sqlfluff.py:56` · `shellcheck.py:40` · `hadolint.py:54` · `cppcheck.py:56`.
Shape 6: empty stdout read as clean, for a tool whose clean run still emits a document.
"""
from __future__ import annotations
import json
import subprocess  # nosec B404


class _Shape6:
    name = "shape_empty_stdout_is_clean"

    def run(self, ctx) -> list:
        """빈 stdout → 빈 결과."""
        try:
            r = subprocess.run(  # nosec B603 B607
                ["shape6", ctx.tmp_path], capture_output=True, text=True,
                timeout=30, check=False,
            )
            if not r.stdout.strip():
                return []
            return json.loads(r.stdout)
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            return []
        except FileNotFoundError:
            return []
