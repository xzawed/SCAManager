"""형태 10 — 조용한 누산기 + **누산과 무관한** `if not x: raise`.

축 C 의 완화 판정이 「아무 이름에나」 걸리면, 이런 무관한 가드 하나로 축이 꺼지고
그 어댑터의 침묵은 다시 통째로 투명해진다. 그래서 완화의 정의역은
**누산 루프가 실제로 쓰는 이름들**이어야 한다.

이 파일이 그 좁히기를 판별한다 — `target` 은 루프가 쓰지 않는다.
`shape_silent_accumulator_with_raise` 로는 이 구별을 못 한다(그쪽 raise 는
`not r.stdout.strip()` 이라 애초에 이름이 아니다).

A shape whose raise-on-empty guards a name the accumulating loop never writes: the swallow
is still unmitigated, so axis C must still fire.
"""


def _parse_line(line):
    """한 줄 파싱 — 실패하면 조용히 버린다."""
    import json
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


class _Analyzer:
    name = "shape_silent_accumulator_unrelated_guard"

    def run(self, ctx):
        target = _resolve_target(ctx)
        # 🔴 누산과 무관한 가드다 — 읽어 낸 이슈가 0건인 것과 아무 상관이 없다.
        if not target:
            raise RuntimeError("no target to analyze")
        issues = []
        for line in _spawn(ctx, target).stdout.splitlines():
            parsed = _parse_line(line)
            if parsed is not None:
                issues.append(parsed)
        # 🔴 여기서 끝난다 — 한 줄도 못 읽어도 「깨끗함」으로 나간다.
        return issues


def _resolve_target(ctx):
    raise NotImplementedError


def _spawn(ctx, target):
    raise NotImplementedError
