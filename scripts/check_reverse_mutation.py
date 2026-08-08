#!/usr/bin/env python3
"""역-뮤테이션 게이트 — PR 의 테스트가 **그 PR 이 고친 결함을 실제로 관측하는가** (P1).

## 왜 만드나 (2026-08-07 다중 관점 진단의 지배 원인)

이 저장소가 반복해 온 결함의 형태는 하나로 수렴한다:

> **결함을 고친 당사자가 그 결함을 검증할 관측자를 같은 PR 안에서 만들고,
> 그 관측자는 하필 그 PR 이 고친 결함에만 맹목이다.**

실측된 사례(전부 외부 검증이 뒤늦게 잡았다):
- R61 — 5번째 호출부를 가드가 못 봄 + 정규식이 4가지 우회 허용
- R58 — 공허화 경로가 둘이 아니라 셋
- R63 — 비-dict JSON 경로가 여전히 2행을 남김
- R65 — **모든 가드가 스파이/패치라 "기록된다" 가 한 번도 관측된 적 없음**
- R57 — CI env 무검증 · 인자 순서 무검증 · 판정 불가를 "변경 없음" 이라 단언

산문 규칙으로는 닫히지 않는다. 이 저장소의 🔴 규칙 337개 중 실측 준수율이
**0/42**(정책 13) · **발화율 100% / 이행률 0%**(R43)인 것들이 있다 — 규칙이 도달해도
지켜지지 않는다는 뜻이고, 그래서 **기계 질문**이 필요하다.

## 계약

PR 의 **생산 표면 변경 전체**를 base 로 되돌린 뒤, 그 PR 이 추가/수정한 테스트만 실행한다.

- **red 여야 한다.** green 이면 그 테스트는 이 PR 이 고친 것을 보지 않는다 → 게이트 실패.
- 되돌림이 no-op 이면(파일이 실제로 안 바뀜) **판정 불가로 실패**한다 — 뮤테이션 유효성
  (AGENTS.md 불변식 2)을 게이트 자신에게도 적용한다.
- baseline(되돌리기 전)이 이미 red 면 **판정 불가로 실패**한다 — 무엇 때문에 빨간지 모른다.

## 🔴 이 게이트가 닫지 못하는 것 (정직 기준)

- **신호 등급이 둘이다.** 되돌림으로 테스트가 `import` 하던 심볼이 사라지면 *collection
  error* 가 나는데, 이는 결합은 증명하지만 **단언의 내용은 증명하지 않는다**. 실제
  assertion 실패가 강한 신호다. 소급 검증 5건 중 3건이 collection error 였다 —
  그래서 출력에서 **두 등급을 구분해 인쇄**한다(숨기지 않는다).
- 테스트를 **한 줄도 안 건드린 PR** 은 대상이 아니다. 그런 PR 이 결함을 고쳤다면 이
  게이트는 침묵한다 — 그 축은 커버리지/리뷰가 맡는다.
- 되돌림 단위가 **파일 전체**라 한 PR 이 두 결함을 고쳤을 때 어느 쪽을 관측하는지는 모른다.

Reverse-mutation gate: revert the PR's production changes and re-run only the tests it
touched. If they still pass, those tests do not observe what the PR changed.
"""
from __future__ import annotations

import os
import subprocess  # nosec B404
import sys
import tempfile
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

_ROOT = Path(__file__).resolve().parents[1]

# 되돌릴 "생산 표면".
# 🔴 `src/` 만 되돌리면 안 된다 — `#1298`·`#1305` 는 `src/` 변경이 **0건**이라 원리적으로
#    미검출된다(설계 적대 검증이 실측으로 짚은 지점). 가드·워크플로·훅도 생산물이다.
PROD_PREFIXES = (
    "src/",
    "scripts/",
    "alembic/",
    ".github/workflows/",
    ".claude/hooks/",
    ".claude/workflows/",
    ".claude/settings.json",
    ".pre-commit-config.yaml",
    "e2e/conftest.py",
)
TEST_PREFIXES = ("tests/",)

# 면제 — 이 게이트가 원리적으로 판정할 수 없는 PR 을 저자가 **명시**한다.
# 🔴 사유 16자 이상. 조용한 통과가 아니라 보이는 결정이 되도록 job summary 에 계수한다.
import re  # noqa: E402  (stdout 재구성 이후 import — guards.md 관용구)

_EXEMPT = re.compile(
    r"^[ \t]*(?![`'\"])reverse-mutation-not-applicable\s*:\s*\S.{15,}", re.MULTILINE)
_LINE_BREAKS = re.compile(r"\s+")


def _run(args: list[str], cwd: Path, timeout: int = 1800) -> subprocess.CompletedProcess:
    return subprocess.run(  # nosec B603
        args, cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout, check=False,
    )


def classify(files: list[str]) -> tuple[list[str], list[str]]:
    """(생산 표면, 테스트) 로 분류."""
    prod = [f for f in files
            if f.startswith(PROD_PREFIXES) and not f.startswith(TEST_PREFIXES)]
    tests = [f for f in files if f.startswith(TEST_PREFIXES) and f.endswith(".py")]
    return prod, tests


def changed_files(base_sha: str, head_sha: str, cwd: Path) -> list[str] | None:
    """`base...head`(merge-base) 변경 파일. 판정 불가면 None.

    🔴 three-dot 이어야 한다 — two-dot 은 base 가 앞서간 만큼을 함께 세어
    **남의 변경을 이 PR 의 것으로** 오판한다.
    """
    proc = _run(["git", "diff", "--name-only", f"{base_sha}...{head_sha}"], cwd, timeout=120)
    if proc.returncode != 0:
        return None
    return [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]


def _append_step_summary(markdown: str) -> None:
    """job summary 에 누적 — `::notice` 는 로그 안쪽이라 아무도 보지 않는다."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(markdown)
    except OSError:
        pass  # 기록 실패가 판정을 바꾸면 안 된다 / logging must never change the verdict


def _pytest(paths: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """되돌림이 **실제로 반영되도록** 바이트코드 캐시를 끄고 실행한다.

    🔴 이것이 없으면 게이트가 **fail-open** 한다 (2026-08-08 CI 실측, Linux 에서만 발현):
    baseline 실행이 `src/x.py` 를 `__pycache__/x.pyc` 로 컴파일한다. 그 다음
    `git checkout base -- src/x.py` 가 소스를 되돌리는데, 되돌린 내용이 **같은 바이트 수**
    이고 두 작업이 **같은 초** 안에 일어나면 Python 의 (mtime, size) 검증이 통과해
    **옛 `.pyc` 를 그대로 재사용**한다. 그러면 되돌렸는데도 테스트가 초록이고,
    게이트는 *"이 테스트는 변경을 관측하지 않는다"* 고 **거짓 보고**한다.

    Windows 에서는 파일 연산이 느려 초가 넘어가므로 재현되지 않았다 — 플랫폼 비대칭이
    이 결함을 로컬에서 숨겼다.

    Disable bytecode caching so the revert is actually observed; otherwise a same-size revert
    within the same second reuses the stale .pyc and the gate reports a false "vacuous".
    """
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run(  # nosec B603
        [sys.executable, "-B", "-m", "pytest", *paths, "-q", "--no-header",
         "-p", "no:cacheprovider"],
        cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=1800, check=False, env=env,
    )
    return proc


def _grade(proc: subprocess.CompletedProcess) -> str:
    """red 의 등급 — assertion 실패인가, 수집 오류인가."""
    out = (proc.stdout or "") + (proc.stderr or "")
    if " failed" in out:
        return "assertion"
    if "error" in out.lower():
        return "collection"
    return "unknown"


def evaluate(base_sha: str, head_sha: str, repo: Path | None = None) -> tuple[int, list[str]]:
    """(exit code, 출력 줄) — 순수 판정부.

    🔴 `repo` 를 인자로 받는 이유: 테스트가 **합성 git 리포**를 만들어 판정 전체를
    실행할 수 있어야 한다. 이 저장소만 대상으로 하면 게이트 자신을 검증할 때
    "스파이로 대체하고 kwargs 만 본다"(R65 가 잡은 클래스)로 흐른다.
    """
    root = repo or _ROOT
    lines: list[str] = []
    files = changed_files(base_sha, head_sha, root)
    if files is None:
        return 1, ["🔴 변경 파일을 산출하지 못했다 — **판정 불가**(fail-closed)."]

    prod, tests = classify(files)
    if not tests:
        return 0, [f"⏭️  테스트 변경 0건 — 이 게이트의 대상이 아니다 (생산 표면 {len(prod)}건)."]
    if not prod:
        return 0, [f"⏭️  생산 표면 변경 0건 — 되돌릴 것이 없다 (테스트 {len(tests)}건)."]

    with tempfile.TemporaryDirectory() as tmp:
        wt = Path(tmp) / "wt"
        add = _run(["git", "worktree", "add", "--detach", str(wt), head_sha], root, timeout=600)
        if add.returncode != 0:
            return 1, [f"🔴 worktree 생성 실패 — 판정 불가: {add.stderr[-200:]}"]
        try:
            base_proc = _pytest(tests, wt)
            if base_proc.returncode != 0:
                return 1, [
                    "🔴 되돌리기 **전에 이미 red** — 무엇 때문에 빨간지 알 수 없다(판정 불가).",
                    f"   {(base_proc.stdout or '')[-400:]}",
                ]

            existing, created = [], []
            for f in prod:
                probe = _run(["git", "cat-file", "-e", f"{base_sha}:{f}"], wt, timeout=60)
                (existing if probe.returncode == 0 else created).append(f)
            if existing:
                rv = _run(["git", "checkout", base_sha, "--", *existing], wt, timeout=600)
                if rv.returncode != 0:
                    return 1, [f"🔴 되돌리기 실패 — 판정 불가: {rv.stderr[-200:]}"]
            for f in created:
                _run(["git", "rm", "-f", "--quiet", f], wt, timeout=120)

            # 🔴 뮤테이션 유효성 (AGENTS.md 불변식 2) — 게이트 자신에게도 적용한다.
            #    `git diff` 는 작업트리↔index 를 보므로 `checkout` 뒤에는 항상 비어 있다.
            dirty = _run(["git", "status", "--porcelain"], wt, timeout=120)
            if not (dirty.stdout or "").strip():
                return 1, ["🔴 되돌림이 **no-op** — 뮤테이션이 무효라 아무것도 증명하지 못한다."]

            after = _pytest(tests, wt)
            tail = [l for l in (after.stdout or "").splitlines()
                    if "passed" in l or "failed" in l or "error" in l]
            summary = tail[-1] if tail else "?"

            if after.returncode != 0:
                grade = _grade(after)
                lines.append(
                    f"✅ 역-뮤테이션 red — 이 PR 의 테스트가 변경을 관측한다 ({summary})")
                lines.append(f"   신호 등급: **{grade}**"
                             + ("  (수집 오류 — 결합은 증명하나 단언 내용은 증명하지 않는다)"
                                if grade == "collection" else ""))
                lines.append(f"   되돌린 생산 파일 {len(prod)}건 · 실행 테스트 {len(tests)}건")
                return 0, lines

            lines.append("🔴 역-뮤테이션이 **green** — 이 PR 의 테스트는 이 PR 의 변경을 "
                         "관측하지 않는다.")
            lines.append(f"   되돌린 생산 파일 {len(prod)}건: {', '.join(prod[:6])}"
                         + (" …" if len(prod) > 6 else ""))
            lines.append(f"   실행 테스트 {len(tests)}건: {', '.join(tests[:6])}")
            lines.append(f"   결과: {summary}")
            lines.append("")
            lines.append("   → 그 변경을 **실제로 깨뜨리는** 단언을 추가하세요.")
            lines.append("   → 이 게이트로 판정할 수 없는 변경이면 PR 본문에 적으세요:")
            lines.append("        reverse-mutation-not-applicable: <왜 판정 불가인가 — 16자 이상>")
            lines.append("      🔴 그 사용은 job summary 에 계수됩니다.")
            return 1, lines
        finally:
            _run(["git", "worktree", "remove", "--force", str(wt)], root, timeout=600)


def main() -> int:
    print("=== 역-뮤테이션 게이트 / Reverse-Mutation Gate ===\n")
    base_sha = os.environ.get("PR_BASE_SHA", "")
    head_sha = os.environ.get("PR_HEAD_SHA", "")
    if not (base_sha and head_sha):
        print("⏭️  PR 환경변수(PR_BASE_SHA/PR_HEAD_SHA)가 없다 — 로컬 실행에서는 쉰다.")
        return 0

    exemption = _EXEMPT.search(os.environ.get("PR_BODY", "") or "")
    if exemption:
        reason = _LINE_BREAKS.sub(" ", exemption.group(0).strip())[:200]
        print(f"::notice title=reverse-mutation exempted::{reason}")
        _append_step_summary(f"- ⏭️ **역-뮤테이션 면제** — {reason}\n")
        print(f"⏭️  면제 마커 확인 — {reason}")
        return 0

    code, lines = evaluate(base_sha, head_sha)
    stream = sys.stdout if code == 0 else sys.stderr
    for line in lines:
        print(line, file=stream)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
