"""형태 3 — `ET.ParseError`. JSONDecodeError 와 같은 파싱 실패인데 구 탐지기는
문자열 "JSONDecodeError" 만 봐서 못 봤다. 실물: `src/analyzer/io/tools/cppcheck.py`.
Shape 3: XML parse failure — same class as JSONDecodeError, invisible to a literal match.
"""
from __future__ import annotations
import subprocess  # nosec B404
import xml.etree.ElementTree as ET  # nosec B405


class _Shape3:
    name = "shape_etree_parseerror"

    def run(self, ctx) -> list:
        """XML 파싱 실패 → 빈 결과."""
        try:
            r = subprocess.run(  # nosec B603 B607
                ["shape3", "--xml", ctx.tmp_path], capture_output=True, text=True,
                timeout=30, check=False,
            )
            return [e.get("msg") for e in ET.fromstring(r.stderr).findall(".//error")]  # nosec B314
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            return []
        except (FileNotFoundError, ET.ParseError):
            return []
