"""형태 5 — 도구는 돌았지만 **분석은 못 했다**를 유효 JSON 으로 보고하는 경우.
`success: false` 는 파싱 실패가 아니라 정상 JSON 이라 파싱 축 탐지기가 전부 통과시킨다.
실물: `slither.py::_parse_slither_json` (Solidity 컴파일 실패).
Shape 5: "ran but did not analyze" reported as valid JSON — no parse error fires.
"""
from __future__ import annotations
import json
import subprocess  # nosec B404


class _Shape5:
    name = "shape_success_false"

    def run(self, ctx) -> list:
        """컴파일 실패 → 유효 JSON · 이슈 0건."""
        try:
            r = subprocess.run(  # nosec B603 B607
                ["shape5", ctx.tmp_path, "--json", "-"], capture_output=True, text=True,
                timeout=30, check=False,
            )
            return _parse_shape5(r.stdout)
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            return []
        except FileNotFoundError:
            return []


def _parse_shape5(text: str) -> list:
    """`success: false` 를 «깨끗함» 으로 돌려준다 — 이것이 fail-open 이다."""
    data = json.loads(text)
    if not data.get("success", False):
        return []
    return list(data.get("results", {}).get("detectors", []))
