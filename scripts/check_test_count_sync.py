#!/usr/bin/env python3
"""테스트 수치 축 — PR 본문의 `pytest tests/unit → N passed / M skipped` 가 실측과 같은가 (회고 P0-D · R48).

테스트 수는 문서(STATE · README)에 적지 않는다 — 원천은 실행 결과다. 이 스크립트는 그 원천과
PR 본문이 적은 수를 대조한다.

- **junit 산출물이 있으면(CI)**: 본문 총계(passed + skipped) ↔ 그 잡의 **실제 실행 결과**.
  단위 테스트가 1건이라도 실패했으면 본문이 무엇이든 red.
- **없으면(로컬 `pre_push_gate --pr-body`)**: `--collect-only` 수집값과 대조한다 — 「돌렸는가」가
  아니라 「수가 신선한가」만 잰다(배너가 그렇게 인쇄한다).
- **본문에 수치 줄이 없으면**: 비봇 PR 은 red · 봇 PR 과 PR 맥락이 없는 실행(로컬 · push)은
  «미실행»(초록이 아니라 '안 쟀음').

🔴 fail-closed — 수집 실패 · 파싱 미검출은 exit 1. 빈 범위 위의 ✅ 를 내지 않는다.

Test-count axis: the PR body's unit-test claim against the job's junit in CI, or the live
collection locally. Counts are not kept in docs; the run is the source.
"""
from __future__ import annotations

import os
import re
import subprocess  # nosec B404
import sys
import xml.etree.ElementTree as ET  # nosec B405 — 자체 CI 산출물만 파싱
from pathlib import Path

# Windows cp949 stdout 에서 한글/이모지 크래시 방지 (guards.md 관용구)
# Prevent cp949 crashes on Korean/emoji output (guards.md idiom).
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

_ROOT = Path(__file__).resolve().parents[1]

# 🔴 PR 본문은 **단일 리더**를 통해서만 읽는다 — 원문을 정규식에 넘기면 HTML 주석 안
# 마커가 "리뷰어 비가시 + 게이트 통과" 를 성립시킨다(회고 N-P0-1 · backlog R20 결함 1).
# 스크립트 간 공유 관용구는 `retro_scope.py:34` 선례를 따른다(standalone 실행이라
# sys.path 조작이 필요하다). 단일성 강제: `tests/unit/scripts/test_pr_body_single_reader.py`.
# Read the PR body only through the single hardened reader; see the guard test.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_claim_review_trace import (  # noqa: E402  # pylint: disable=wrong-import-position
    read_pr_body,
)


# 마지막 매치 사용 + 단수형 허용 ("1 test collected") — Grok 계약.
# Use the LAST match; tolerate the singular form.
_COLLECTED = re.compile(r"(\d+) tests? collected")


def parse_collected(output: str) -> int | None:
    """`--collect-only -q` 출력에서 수집 수 — **마지막** 매치, 미검출 시 None.
    Last match of the collected-count line; None when absent (caller must fail closed)."""
    matches = _COLLECTED.findall(output)
    return int(matches[-1]) if matches else None


# CI 가 `pytest tests/` 와 함께 만드는 junit 산출물 — **실행 증거**의 유일한 기계 출처.
# The junit artifact CI already produces; the only machine source of execution evidence.
_JUNIT = _ROOT / "pytest-results.xml"


def junit_unit_counts(path: Path | None = None) -> tuple[int, int, int] | None:
    """junit XML 에서 **단위 테스트만** `(passed, skipped, failed)`. 없거나 못 읽으면 None.

    🔴 왜 `classname` 으로 거르는가: CI 는 `pytest tests/`(단위 + 통합)를 돌리므로
    `<testsuite tests=…>` 총계는 본문의 **단위** 수치와 맞지 않는다. junit 의 `classname` 은
    `tests.unit.gate.test_engine` 처럼 점 경로라 여기서 갈라진다(산출물 형태 실측 확인).

    🔴 **None 과 `(0,0,0)` 을 구별한다.** 산출물이 없으면 「안 쟀음」이지 「0건」이 아니다 —
    이 구별을 잃으면 호출부가 빈 값 위에 ✅ 를 찍는다(이 리포가 반복해 온 fail-open).

    🔴 `collect_count` 와 무엇이 다른가: 수집은 「테스트가 몇 개 있는가」를, 이쪽은 「몇 개가
    실제로 돌아 어떤 결과였는가」를 본다. **실패 수를 센다**는 것이 그 차이의 핵심이다.
    Unit-only (passed, skipped, failed) from the junit artifact; None when absent/unparsable.
    """
    target = path or _JUNIT
    if not target.is_file():
        return None
    try:
        root = ET.parse(target).getroot()  # nosec B314 — 자체 CI 산출물
    except (ET.ParseError, OSError):
        return None
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    passed = skipped = failed = 0
    for suite in suites:
        for case in suite.iter("testcase"):
            if not (case.get("classname") or "").startswith("tests.unit"):
                continue
            if case.find("skipped") is not None:
                skipped += 1
            elif case.find("failure") is not None or case.find("error") is not None:
                failed += 1
            else:
                passed += 1
    return passed, skipped, failed


def collect_count(test_path: str) -> int:
    """실측 수집 — 실패는 **어떤 모드에서도** 예외로 전파한다(fail-closed).
    Run the real collection; any failure raises (fail-closed in every mode)."""
    proc = subprocess.run(  # nosec B603
        [sys.executable, "-m", "pytest", test_path, "--collect-only", "-q"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=600, cwd=str(_ROOT), check=False,
    )
    # exit 5 = 수집 0건, exit 2 = 수집 오류 — 둘 다 "count 를 신뢰할 수 없음" 이다.
    # Exit 5 (nothing collected) and 2 (collection errors) both mean the count is untrustworthy.
    if proc.returncode != 0:
        raise RuntimeError(
            f"pytest collect 실패 (exit {proc.returncode}) — {test_path}\n"
            f"{(proc.stdout or '')[-500:]}\n{(proc.stderr or '')[-300:]}"
        )
    count = parse_collected(proc.stdout)
    if count is None:
        raise RuntimeError(
            f"'N tests collected' 라인을 찾지 못했다 — {test_path} (포맷 drift = 축 소멸이므로 실패)"
        )
    return count


def _append_step_summary(markdown: str) -> None:
    """GitHub Actions job summary 에 한 줄 추가 (없으면 무시 — 로컬 실행).

    🔴 Actions **로그 안쪽**은 사실상 아무도 보지 않는다 — 본문 불일치는 사람이 실제로 여는
    자리에 남아야 한다. 이 저장소가 반복해 고쳐 온 "관측은 하는데 아무도 안 보는" 클래스다.
    """
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(markdown)
    except OSError:
        pass  # 기록 실패가 판정을 바꾸면 안 된다 / logging must never change the verdict


# 🔴 본문 수치 주장 — 6-step ② 의 집행 가능한 형태 (backlog R48).
#
# 회고 권고(2026-08-08): *"전체 테스트를 돌렸는가"* 는 자기 신고라 기계가 진위를 못 잰다.
# 질문을 *"본문에 적힌 수가 실측 수집값에서 파생됐는가"* 로 바꾸면 **잴 수 있다**.
#
# 형식 2종이 실재한다(2026-08-10, 최근 20 PR 실측) — 둘 다 받아야 한다:
#   · 화살표 `pytest tests/unit  →  6841 passed / 9 skipped / EXIT=0`        (#1304~#1314)
#   · 표     `| `pytest tests/unit` 전체 | **6985 passed / 9 skipped / …** |` (#1316~#1320)
# 화살표만 지원하면 이 축은 **현행 관행에서 영원히 미실행**이 된다.
#
# `pytest tests/unit` 앵커가 뮤테이션 표(`**2 failed** / 3 passed`)를 배제한다 —
# 그 행들은 전체 스위트 주장이 아니라 개별 뮤테이션 결과다.
# Two real body formats; the `pytest tests/unit` anchor excludes per-mutation rows.
# 🔴 **줄 단위 2단 파싱** — 한 정규식으로 두 숫자를 잡으면 `[^\n]*?` 두 개가 중첩돼
#    백트래킹이 super-linear 가 되고(SonarCloud S8786), 더 나쁘게는 앞 숫자에서 뒤 숫자까지
#    **전방으로 침범**한다. 후보 줄을 먼저 고르고 그 줄 안에서 각각 찾으면 둘 다 사라진다.
#
# 🔴 `(?![\w/])` 가 필수다 — `\b` 는 `tests/unit/scripts` 에서도 성립해, 스코프 실행 증거
#    (`pytest tests/unit/scripts → 2 failed, 494 passed, 1 skipped`)를 **전체 스위트 주장으로
#    오독**한다. 이 리포 본문은 뮤테이션 증거표를 일상적으로 담으므로 실제 오탐원이다
#    (적대 감사 `wf_9a4878aa-eab` 적발).
_BODY_CLAIM_LINE = re.compile(r"pytest[`'\"\s]*tests/unit(?![\w/])", re.IGNORECASE)
# 천단위 구분자 허용 — `6,995 passed` 가 `995` 로 읽히던 오탐(같은 감사).
_PASSED = re.compile(r"(\d[\d,_]*)\s*passed", re.IGNORECASE)
_SKIPPED = re.compile(r"(\d[\d,_]*)\s*skipped", re.IGNORECASE)


def _to_int(raw: str) -> int:
    return int(raw.replace(",", "").replace("_", ""))


def parse_body_claim(body: str) -> tuple[int, int] | None:
    """PR 본문이 주장하는 `(passed, skipped)`. 미검출은 None (빈 값과 구별한다).

    🔴 **첫 매치를 쓴다** — `parse_collected`(pytest 출력)와 반대 관용구이고, 그 차이에
    이유가 있다. pytest 출력의 순서는 **도구가 정하지만** PR 본문의 순서는 **저자가 정한다**.
    마지막 매치를 쓰면 헤드라인에 틀린 수를 적고 접힌 `<details>` 부록에 맞는 수를 넣어
    리뷰어와 가드에게 **다른 것을 보여줄 수 있다**(적대 감사가 실행으로 실증). 첫 매치는
    리뷰어가 실제로 읽는 자리다.

    🔴 `skipped` 는 **선택**이다 — skip 이 0건이면 pytest 는 그 토큰을 아예 출력하지 않는다.
    필수로 두면 그 상태에서 축이 조용히 미실행이 된다.
    """
    for line in (body or "").splitlines():
        if not _BODY_CLAIM_LINE.search(line):
            continue
        passed = _PASSED.search(line)
        if not passed:
            continue
        skipped = _SKIPPED.search(line)
        return _to_int(passed.group(1)), _to_int(skipped.group(1)) if skipped else 0
    return None


# CI 가 넘기는 저자 신원. 본문에서 읽지 않는다 — 본문 마커는 자기인증
# (`check_claim_review_trace` 가 이미 배운 함정).
# Author identity comes from CI env, never from the PR body (self-certification trap).
_AUTHOR_LOGIN_ENV = "PR_AUTHOR_LOGIN"
_AUTHOR_TYPE_ENV = "PR_AUTHOR_TYPE"


def is_bot_author() -> bool:
    """CI env 기준 봇 여부. 본문을 보지 않는다.

    GitHub App 은 `user.type == "Bot"` 이고, dependabot 로그인은 `dependabot[bot]`.
    둘 중 하나면 봇으로 본다.

    🔴 **부재·공백은 봇이 아니다.** 저자 env 가 비는 순간 전 PR 이 면제되면
    이 리포의 fail-open 사고와 같은 클래스다. 호출자가 변수를 안 넘기는 것이
    만능 면제가 되면 안 된다.
    Absent/empty author env is NOT a bot — that must not become a universal exemption.
    """
    login = (os.environ.get(_AUTHOR_LOGIN_ENV) or "").strip()
    typ = (os.environ.get(_AUTHOR_TYPE_ENV) or "").strip()
    if not login and not typ:
        return False
    return typ.casefold() == "bot" or login.casefold().endswith("[bot]")


def check_body_claim(body: str, unit: int | None, *, advisory: bool = False) -> int:
    """본문 수치 ↔ 실측 수집값 대조.

    반환: 0 = 일치 · 봇/advisory 의 미실행 / 1 = 불일치 · 비봇의 수치 라인 부재.

    ## 모드 (각각 다른 것을 한다 — 섞지 말 것)

    - **기본 (CI PR)**: 수치 라인 없음 + 비봇 → red(1). 저자 env 부재/공백 = 비봇.
    - **봇 PR**: 수치 라인 없음 → 기존 *"미실행"* 문구 + 0.
      무조건 의무화하면 본문을 기계가 만드는 dependabot PR 이 전부 red 다.
    - **`advisory=True`** (PR 맥락이 없는 실행 — 로컬 `pre_push_gate` · CI push):
      수치 라인 없음 → *"미실행"* + 0. 로컬·push 에는 PR 본문이 없다.

    `unit` 은 junit 이 없을 때만 쓰는 수집값이다 — `None` 이면 대조할 실측이 없어 red.

    🔴 **미검출을 초록으로 위장하지 않는다** — 수치 라인이 없으면 이 축은 아무것도
    검증하지 않은 것이므로 *"미실행"* 을 명시 출력한다. 빈 범위 위의 ✅ 는 이 리포가
    반복해 온 fail-open 이다(`check_lint_js_nonvacuous` 가 같은 이유로 범위 붕괴를 red 로 본다).

    🔴 **이 축이 무엇을 재는지 정확히 — 2026-08-18 부터 두 모드다**:

    - **junit 산출물이 있으면(CI)**: 본문 수치를 `pytest-results.xml` 의 **실제 실행 결과**와
      대조한다. 실패가 1건이라도 있으면 본문이 무엇이든 red — `--collect-only` 가 원리적으로
      못 보던 축이다. CI 는 `pytest tests/` 를 이 가드보다 **먼저** 돌리므로 산출물이 있다.
    - **없으면(로컬·push)**: 종전대로 수집값 대조로 강등되고, 배너가 「실행 증거 아님」을
      명시한다. 이 경우 재는 것은 *"낡거나 파생되지 않은 수치의 탐지"* 뿐이다.

    종전 서술(적대 감사 `wf_9a4878aa-eab` 이 초판 주장을 BROKEN 판정): 이 가드가 쓰는
    `--collect-only` 는 11초인데 실제 스위트는 208~247초라 저자가 19배 싼 경로로 같은 숫자를
    만들 수 있었다. 그 지적이 위 junit 모드의 근거다(구 backlog R76 · Issue #1442).

    🔴 **닫힌 것 / 닫히지 않은 것 (2026-08-15 사용자 결정 — 공허 통과 차단)**:
    - 닫힘: 비봇 PR 에 수치 라인이 없으면 red. (#1272 가 자기 면제한 바로 그 구멍.
      저자 신원은 CI env 에서만 읽는다 — 본문 마커는 자기인증이다.)
    - 닫히지 않음: 봇 PR. 무조건 의무화하면 dependabot 본문이 전부 red 다.
    - **닫힘 (2026-08-18, #1442)**: junit 산출물이 있는 CI 에서는 실행 결과와 대조한다.
      로컬·push 에서는 여전히 수집값 대조이고, 배너가 그 사실을 인쇄한다.
    Two modes: execution evidence when the junit artifact exists, collection freshness otherwise.
    """
    claim = parse_body_claim(body)
    if claim is None:
        print(
            "⚠️  본문 수치 축 **미실행** — 본문에서 "
            "`pytest tests/unit … N passed / M skipped` 를 찾지 못했다.\n"
            "    이 축은 아무것도 검증하지 않았다(초록이 아니라 '안 쟀음')."
        )
        # 봇·advisory 만 미실행으로 끝낸다. 비봇 기본은 red — 수치 라인 삭제가
        # 가장 싼 대응이던 구멍을 닫는다 (2026-08-15).
        # Bot/advisory keep the "not measured" pass; non-bot missing claim is now red.
        if advisory or is_bot_author():
            return 0
        print(
            "🔴 본문에 테스트 수치 라인이 없다 — 비봇 PR 은 수치를 적어야 한다.\n"
            "   `pytest tests/unit → N passed / M skipped` 를 본문에 넣으세요.\n"
            "   봇 PR 만 이 축을 건너뛴다(dependabot 본문은 기계가 만든다).",
            file=sys.stderr,
        )
        return 1
    passed, skipped = claim

    # 🔴 **실행 증거 축** (#1442) — junit 산출물이 있으면 수집값이 아니라 **실제 실행 결과**와
    #    대조한다. `--collect-only` 는 「테스트가 몇 개 있는가」만 보므로, 돌지 않았거나
    #    실패한 스위트도 같은 수를 낸다. CI 는 이미 이 산출물을 만든다(오라클이 이미 있었다).
    # 🔴 **총계만 대조한다 — skip 분해는 안 본다** (CI 실측 2026-08-18).
    #    본문 수치는 저자가 **로컬에서** 잰다(6-step ②). 그런데 환경 조건부 skip 이 있어
    #    로컬 9 skipped ↔ CI 5 skipped 처럼 정당하게 갈린다(openai SDK 는 CI 에만 설치).
    #    분해까지 요구하면 이 축은 **원리적으로 만족 불가**가 된다 — 초판이 그랬고 CI 가 잡았다.
    #    총계는 환경 무관이고, 「돌렸는가」는 아래 `ran_failed` 와 산출물 존재가 책임진다.
    # Compare totals only: environment-conditional skips legitimately differ local↔CI.
    run = junit_unit_counts()
    if run is not None:
        ran_passed, ran_skipped, ran_failed = run
        if ran_failed:
            print(
                f"🔴 단위 테스트 {ran_failed}건이 **실패**했다 — 본문 수치가 무엇이든 이 PR 의 "
                f"스위트는 초록이 아니다. junit 실측: {ran_passed} passed / "
                f"{ran_skipped} skipped / {ran_failed} failed",
                file=sys.stderr,
            )
            return 1
        if (passed + skipped) != (ran_passed + ran_skipped):
            print(
                f"🔴 본문 수치가 **실행 결과**와 다르다 — 본문 {passed}+{skipped}="
                f"{passed + skipped} vs junit 실측 {ran_passed}+{ran_skipped}="
                f"{ran_passed + ran_skipped}. "
                "→ 수집값이 아니라 실제로 돌린 출력에서 옮길 것.",
                file=sys.stderr,
            )
            return 1
        print(
            f"✅ 본문 수치 축 일치 (**실행 증거**) — 본문 {passed}+{skipped} == junit 실측 "
            f"{ran_passed}+{ran_skipped} (실패 0). "
            "skip 분해는 대조하지 않는다 — 환경 조건부 skip 이 로컬↔CI 에서 갈린다."
        )
        return 0

    if unit is None:
        # 🔴 junit 도 수집값도 없다 — 무엇과도 대조하지 못했다. 초록이 아니다.
        # Neither the run nor a collection to compare against: not green.
        print("🔴 본문 수치를 대조할 실측이 없다 — junit 산출물도 수집값도 없다 (fail-closed).",
              file=sys.stderr)
        return 1
    if passed + skipped == unit:
        # 🔴 junit 부재 — 수집값 대조로 강등된다. 「신선한가」는 재지만 「돌렸는가」는 못 잰다.
        print(
            f"✅ 본문 수치 축 일치 — 본문 {passed}+{skipped}={passed + skipped} "
            f"== 실측 **수집** {unit}. "
            "⚠️ junit 산출물 부재 — 이 대조는 수치의 신선도이지 **실행 증거 아님**."
        )
        return 0
    print(
        f"🔴 본문 수치가 실측과 다르다 — 본문 {passed} passed + {skipped} skipped "
        f"= {passed + skipped} vs 실측 수집 {unit} (차 {passed + skipped - unit:+d})\n"
        "   → 6-step ② 가 요구하는 것은 '돌렸다는 말' 이 아니라 **기계값에서 파생된 수**다.\n"
        "   `py -3 -m pytest tests/unit -q` 를 다시 돌려 본문 수치를 그 출력으로 갱신하세요.\n"
        "   🔴 실측 4건이 이 형태였다(#1305 −10 · #1310 −1 · #1312 −16) — base 가 앞서간\n"
        "      탓이 아니라 본문이 틀린 것이었다(브랜치 tip 재측정으로 배제).",
        file=sys.stderr,
    )
    _append_step_summary(
        f"- 🔴 **본문 수치 불일치** — 본문 {passed + skipped} vs 실측 {unit}\n"
    )
    return 1


def main() -> int:
    body = read_pr_body()
    # PR 맥락 = CI `pull_request` 가 넘기는 SHA. 없으면(로컬 · push) 수치 부재는 «미실행» 이다.
    # The PR context is the SHA env CI passes on pull_request; without it a missing claim is "not measured".
    in_pr = bool(
        (os.environ.get("PR_HEAD_SHA") or "").strip()
        or (os.environ.get("PR_BASE_SHA") or "").strip()
    )
    # 🔴 수집(≈11초)은 쓰일 때만 돈다 — 본문에 수치가 있고 실행 결과(junit)가 없을 때.
    #    CI 는 junit 과 대조하고, 수치가 없는 본문은 수집값을 쓰지 않는다.
    # Collect only when it is the comparison source: a claim exists and no junit does.
    unit = None
    if parse_body_claim(body) is not None and junit_unit_counts() is None:
        try:
            unit = collect_count("tests/unit")
        except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
            # 🔴 도구 실패는 실패다 — 여기서 삼키면 `|| true` 와 같다.
            # Tool failure is a failure; swallowing it here would be `|| true`.
            print(f"🔴 실측 수집 실패 (fail-closed): {exc}", file=sys.stderr)
            return 1
    return check_body_claim(body, unit, advisory=not in_pr)


if __name__ == "__main__":
    sys.exit(main())
