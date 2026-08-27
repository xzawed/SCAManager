"""음성 대조 — 이것은 **잡히면 안 된다**.

`return []` 이 두 자리에만 있다: `TimeoutExpired`(`ctx.timed_out` 이 담당)와
`FileNotFoundError`(조달 축 `unavailable_tools` 가 담당). 분석 실패는 전부 raise 다.
실물 관용구: `semgrep.py::_fail` · `python.py::_fail`.
Negative control: empty returns only on the timeout and procurement axes; analysis
failures raise. Flagging this would mean the detector cannot tell the axes apart.
"""
from __future__ import annotations
import json
import subprocess  # nosec B404


class _Ok:
    name = "ok_narrow_axes"

    def run(self, ctx) -> list:
        """정상 fail-closed 어댑터."""
        try:
            r = subprocess.run(  # nosec B603 B607
                ["ok", ctx.tmp_path], capture_output=True, text=True,
                timeout=30, check=False,
            )
            if not r.stdout.strip().startswith("["):
                raise RuntimeError(f"ok did not analyze (exit={r.returncode})")
            try:
                return json.loads(r.stdout)
            except json.JSONDecodeError as exc:
                raise RuntimeError("ok produced unparseable JSON") from exc
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            return []
        except FileNotFoundError:
            return []
