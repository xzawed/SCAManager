"""형태 7 — `except OSError` 가 조달 축을 넘어 **실행 실패**까지 삼킨다.
`shutil.which` 를 통과한 뒤의 ENOEXEC(깨진 shebang)·PermissionError·TOCTOU 는
「바이너리 부재」가 아니라 미분석이므로 `incomplete` 여야 한다. `FileNotFoundError`
로 좁힌 `semgrep.py`·`python.py` 와 달리 이쪽은 그 구별을 잃는다.
실물: `eslint.py:164` · `tsc.py:109` · `yamllint.py:88`.
Shape 7: `except OSError` swallows spawn failures that are not a missing binary.
"""
from __future__ import annotations
import json
import subprocess  # nosec B404


class _Shape7:
    name = "shape_oserror_swallows_spawn"

    def run(self, ctx) -> list:
        """파싱 축은 fail-closed 인데 spawn 축이 fail-open 이다."""
        try:
            r = subprocess.run(  # nosec B603 B607
                ["shape7", ctx.tmp_path], capture_output=True, text=True,
                timeout=30, check=False,
            )
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            return []
        except OSError:
            return []
        if not r.stdout.strip().startswith("["):
            raise RuntimeError("shape7 did not analyze")
        return json.loads(r.stdout)
