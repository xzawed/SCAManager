"""어댑터 공통 — 분석 실패를 예외로 만든다.
Shared adapter helper: turn an analysis failure into an exception.

`static.py::_run_analyzers` 는 `run()` 이 **예외를 올릴 때만** `incomplete` 로 승격한다.
`[]` 를 돌려주면 그 실패가 «이슈 0건 · 완전» 이 되어 미분석 코드가 auto-merge 된다.

## 🔴 크래시 판별식은 exit code 가 아니다

린터는 **이슈를 찾으면 비-0 으로 끝난다**(tflint 2 · dart 3 · buf 100). 판별식은
「기대한 형식의 출력을 냈는가」이고, 그 형식은 도구마다 다르다:

    봉투형          깨끗해도 봉투를 낸다   → 봉투가 아니면(빈 출력 포함) 실패
                    stylelint `[` · dart `{` · tflint `{` · eslint `[`
    빈 출력 합법형  깨끗하면 빈 출력이다   → 읽은 이슈가 없고 **비-0** 일 때만 실패
                    psscriptanalyzer · buf_lint · flake8 · tsc

두 부류를 섞으면 한쪽은 조용히 통과하고 다른 쪽은 깨끗한 파일을 전부 차단한다.
`empty_output_is_a_crash` 가 후자의 판정을 한 곳에 둔다.

이 파일은 어댑터가 아니라 헬퍼다 — `_` 접두라 재고 탐지기
(`tests/unit/analyzer/test_adapter_fail_open_inventory.py::_fail_open_adapters`)가
주사하지 않는다.
"""
from __future__ import annotations

ERR_EXCERPT = 200


def analysis_failed(tool: str, ctx, r, reason: str = "did not produce parsable output"):
    """미분석을 나타내는 `RuntimeError` 를 만든다 — 올리는 것은 호출부가 한다.

    Build (do not raise) the RuntimeError that marks a file as unanalyzed.
    """
    detail = str(getattr(r, "stderr", "") or getattr(r, "stdout", "") or "").strip()
    return RuntimeError(
        f"{tool} {reason} for {ctx.tmp_path} "
        f"(exit={getattr(r, 'returncode', '?')}): {detail[:ERR_EXCERPT]}"
    )


def empty_output_is_a_crash(issues: list, r) -> bool:
    """빈 출력 합법형에서 「깨끗함」과 「미분석」을 가른다.

    읽어 낸 이슈가 하나도 없는데 비정상 종료했으면 도구가 분석을 못 한 것이다.
    🔴 `stderr` 는 보지 않는다 — 정상 실행도 안내문을 stderr 로 낸다. 정본은
    `python.py` 의 flake8 갈래와 `tsc.py` 이고 둘 다 stderr 를 보지 않는다.

    Distinguish "clean" from "never analyzed" for tools whose clean output is empty.
    """
    return not issues and getattr(r, "returncode", 0) != 0
