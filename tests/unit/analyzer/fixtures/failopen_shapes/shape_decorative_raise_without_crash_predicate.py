"""fail-open — `raise` 는 있지만 **크래시 판별식이 없다**(장식용 raise).

축 A 는 「모듈 안 어느 함수에도 `raise` 가 없다」를 묻는다. 그래서 `except` 갈래의
`raise` 하나만 있으면 A 가 꺼진다. 그런데 그 raise 가 잡는 것은 **「파싱이 예외를 냈다」**
뿐이고, **「도구가 조용히 죽어 깨끗한 것과 바이트가 같은 출력을 냈다」**는 잡지 못한다.

실물 좌표 — 이 형태는 `shellcheck.py` 가 #1582 **이전에** 갖고 있던 것이다:
크래시 stdout 이 깨끗할 때와 바이트가 같아(`[]`) JSON 파싱은 성공하고, 이슈 0건이
«이슈 0건 · 완전» 으로 기록됐다. 그것을 닫은 것이 `_common.py::empty_output_is_a_crash`
(「이슈 0건 + 비정상 종료」)이고, 그 한 줄을 지우면 어댑터는 이 파일과 같은 모양이 된다.

🔴 이 픽스처가 재는 것은 **되돌림**이다. 뮤테이션 실측(main `0017a3eb`): `except` 밖의
`if …: raise` 를 지우면 fail-closed 17개 중 **13개**가 이 모양이 되는데, 축 A·B·C 는
그중 어느 것도 잡지 못했다 — 남은 `except` 의 raise 가 축 A 를 끄기 때문이다.
눈먼 13개에는 탐지기 자신의 경성 대조군 `semgrep` 이 들어 있었다.

축 B 도 못 본다: `return []` 은 두 정당한 축(`TimeoutExpired`·`FileNotFoundError`)에만 있다.
축 C 도 못 본다: 누산 루프가 파싱 실패를 삼키지 않는다.

A decorative raise: it catches "the parse threw", never "the tool died quietly and emitted
output byte-identical to clean". Axes A/B/C are all off, so only a crash-predicate axis sees it.
"""
from __future__ import annotations

import json
import subprocess  # nosec B404


class _Analyzer:
    name = "shape_decorative_raise_without_crash_predicate"

    def run(self, ctx) -> list:
        try:
            r = subprocess.run(  # nosec B603 B607
                ["probe", ctx.tmp_path], capture_output=True, text=True,
                timeout=30, check=False,
            )
            # 🔴 여기에 있어야 할 것: 「도구가 기대한 형식의 출력을 냈는가」.
            #    크래시해도 `[]` 를 내는 도구에서는 아래 파싱이 **성공**하고 0건이 된다.
            #    `if empty_output_is_a_crash(issues, r): raise ...` 가 지워진 자리다.
            try:
                rows = json.loads(r.stdout or "[]")
            except json.JSONDecodeError as exc:
                # 장식용 raise — 축 A 를 끄지만 조용한 크래시는 못 잡는다.
                raise RuntimeError("probe produced unparseable JSON") from exc
            return [{"line": row.get("line", 0)} for row in rows]
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            return []
        except FileNotFoundError:
            return []
