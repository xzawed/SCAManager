"""fail-closed — 누산 루프가 있지만, 삼킴은 **정리 코드**의 것이다.

축 C 가 「모듈 어딘가에 삼키는 except 가 있는가」로 물으면 이 파일이 결함으로 잡힌다.
그건 거짓 양성이고, 거짓 양성이 나오면 사람이 가드를 끈다. 물어야 하는 것은
「그 삼킴이 **누산 루프를 먹이는가**」다 — 여기서는 아니다.

An accumulating loop plus an unrelated swallow in cleanup: the swallow feeds nothing.
"""


class _Analyzer:
    name = "shape_unrelated_cleanup_swallow"

    def run(self, ctx):
        tmp = _mkdir()
        try:
            r = _spawn(ctx, tmp)
            if not r.stdout.strip():
                raise RuntimeError("produced no output")
            issues = []
            for line in r.stdout.splitlines():
                issues.append(_row(line))
            return issues
        finally:
            _cleanup(tmp)


def _cleanup(tmp):
    """정리 실패는 분석 결과와 무관하다 — 여기 삼킴은 누산과 아무 관계가 없다.

    🔴 `pass` 가 아니라 `return None` 이다 — CodeQL `py/empty-except` 를 자초하지 않으면서
    같은 삼킴 형태를 유지한다. 축 C 의 `_swallows_without_raising` 는 둘을 구별하지 않는다.
    """
    import shutil
    try:
        shutil.rmtree(tmp)
    except OSError:
        return None
    return None


def _row(line):
    return {"raw": line}


def _mkdir():
    raise NotImplementedError


def _spawn(ctx, tmp):
    raise NotImplementedError
