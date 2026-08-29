"""형태 9 — **raise 를 가진** 조용한 누산기. 축 A 가 꺼진 뒤에도 남는 침묵.

실물 좌표: `src/analyzer/io/tools/clippy.py::            for line in (r.stdout or "").splitlines():`

기존 `shape_silent_accumulator.py` 는 모듈에 `raise` 가 없어 **축 A**(모듈 안 raise 부재)로
잡힌다. 그래서 그 픽스처는 축 C 를 판별하지 못한다 — A 가 먼저 잡아 C 가 발화할 기회가 없다.

이 파일은 그 그림자를 걷는다. 어댑터가 **다른 이유로** `raise` 를 얻으면(여기서는 빈 stdout)
축 A 가 꺼지고, 루프 안의 파싱 실패 삼킴은 **통째로 투명해진다.** 실제로 `ba1e0955` 가
clippy 에 빈-stdout raise 를 넣으면서 정확히 그 일이 일어났다 — 픽스처 docstring 이 clippy 를
이 형태의 실물 좌표로 지목하는데 탐지기는 clippy 를 결함 0건으로 보고했다.

🔴 판별점: stdout 이 **비어 있지 않고** 읽어 낸 이슈가 0건인 크래시. 빈 stdout raise 는
그 입력을 건드리지 않는다.

The same shape once the module gains a raise for an unrelated reason: axis A goes dark and the
in-loop swallow becomes invisible.
"""


def _parse_line(line):
    """한 줄을 파싱 — 실패하면 조용히 버린다. 이것이 침묵의 자리다."""
    import json
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None
    if obj.get("kind") != "issue":
        return None
    return obj


class _Analyzer:
    name = "shape_silent_accumulator_with_raise"

    def run(self, ctx):
        r = _spawn(ctx)
        # 축 A 를 끄는 raise — 이 형태와 무관한 이유로 존재한다.
        if not r.stdout.strip():
            raise RuntimeError("produced no output")
        issues = []
        for line in r.stdout.splitlines():
            parsed = _parse_line(line)
            if parsed is not None:
                issues.append(parsed)
        # 🔴 여기서 끝난다 — 읽은 것이 0건이어도 「깨끗함」으로 나간다.
        return issues


def _spawn(ctx):
    raise NotImplementedError
