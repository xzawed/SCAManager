#!/usr/bin/env python3
"""semgrep 자기 venv 감사 — `requirements-semgrep.txt` 를 바꾼 PR 만 막고, 나머지는 경고로 남긴다 (회고 원장 L09 P2-54).

semgrep 은 앱과 다른 venv 다(`requirements-semgrep.txt` · 이미지 `/opt/semgrep`). 그 정확 전이 핀에 상류 권고가 뜨면
우리 쪽에서 고칠 길이 없는데, 감사가 늘 막으면 무관한 PR · main 이 빨개진다.

- **막는다**: PR 이 `requirements-semgrep.txt` 를 바꿨을 때 — semgrep 을 올리거나 바꾸는 그 PR 이 권고를 들여오는 자리다.
  바꿨는지 못 재면(PR 범위가 반쪽이거나 git 이 base · head 를 못 찾음) 막는다.
- **경고만**: 그 밖의 PR · main push. `::warning::` 와 job summary 에 남긴다.
- **주간 예약 실행**(`.github/workflows/semgrep-audit-weekly.yml`): `--always-block` 으로 돌리고, 실패하면
  `--notify <보고서>` 가 고정 제목의 열린 이슈에 댓글을 달거나 새 이슈를 연다. 예약 실행은 초록으로 끝난다.

예외(`--ignore-vuln`)는 이 파일 한 곳에만 둔다 — CI 스텝과 주간 실행이 같은 목록을 쓴다.

semgrep's own-venv audit: blocks only the PR that changes requirements-semgrep.txt (or whose change cannot be
measured); elsewhere it warns. The weekly scheduled run blocks and reports through an issue.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess  # nosec B404 — git · pip-audit · gh 만, 인자는 이 파일의 상수
import sys
import tempfile
from pathlib import Path

# 감사 이슈도 공개 쓰기다 — 게시 전 검사 훅은 CI 도 스크립트 안의 gh 도 보지 않는다: 올리기 전에 같은 꼴로 잰다(원장 #1940 M03 P2-16).
# The audit issue is a public write no hook sees; scan it with the same shapes before posting.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scan_publish import count_kinds  # noqa: E402  # pylint: disable=wrong-import-position

_ROOT = Path(__file__).resolve().parents[1]
REQS = "requirements-semgrep.txt"
ISSUE_TITLE = "semgrep venv 감사 — 예외 밖 권고 (주간)"
# 이슈 본문 상한(GitHub 65,536자) 안에 감사 출력의 끝 부분만 싣는다 / keep the tail within GitHub's body limit
_REPORT_TAIL = 15000

# 🔴 권고가 막으면 예외를 넣기 전에 semgrep 을 올려 풀리는지 먼저 본다. 예외는 아래에 적은 것뿐이다.
#
# CVE-2026-59951 (mcp 1.29.0, 2026-10-16) — semgrep 이 강제하는 전이 핀.
#    semgrep(`requirements-semgrep.txt` 의 핀)이 `mcp==1.29.0`(정확 핀)을 요구해 **버전 업으로 해결 불가**.
#    권고 전제 = mcp 의 Streamable HTTP «서버» 를 상태 유지 모드로 띄움. 우리 사용 방식에선 **도달 불가**:
#      · semgrep 은 `["semgrep","scan","--config=<고정 룰 묶음>","--json",…]` 비대화형 CLI subprocess 로만
#        호출된다(src/analyzer/io/tools/semgrep.py) — `semgrep mcp` 서버를 띄우는 곳이 0건.
#      · src/·scripts/ 가 `mcp` 패키지를 import 하는 곳 0건, FastMCP·StreamableHTTP 기동 0건.
#        (src/mcp/ 는 스키마 선언만 있는 별개 모듈로 이 패키지와 무관하다.)
#    재검토 조건 — 충족되면 이 ID 를 즉시 지운다:
#      (1) semgrep 이 mcp 핀을 >=1.30.0 으로 올리면(그 판으로 semgrep 을 올리고 예외 삭제)
#      (2) 우리가 MCP 서버를 Streamable HTTP 로 실제 띄우게 되면(도달 불가 근거가 무효)
#
# CVE-2026-114603 · CVE-2026-126360 (opentelemetry-api 1.37.0, 10-22 · 11-13) — semgrep 이 강제하는 전이 핀.
#    semgrep 이 `opentelemetry-api~=1.37.0` 을 요구해 **버전 업으로 해결 불가**(수정판 114603 = 1.45.1 ·
#    126360 = 1.45.2). 둘 다 바깥 값이 전파 extract 에 들어와야 한다 — 114603 = 들어오는 `tracestate` 헤더
#    (`TraceState.from_header`), 126360 = 조작한 `traceparent` 의 정규식 역추적(`TraceContextTextMapPropagator.extract`).
#    우리 사용 방식에선 **도달 불가**:
#      · 앱 코드는 OpenTelemetry 를 쓰지 않는다 — src/·scripts/ 에 opentelemetry·tracestate·traceparent·OTEL_ 0건.
#        Starlette 의 `OpenTelemetryMiddleware` 는 직접 붙여야 켜지고 붙이는 곳 0건.
#      · 운영 의존성 설치본에서 extract 를 부르는 곳은 그 미들웨어 · semgrep 자체 텔레메트리 · OTel 계측의
#        서버 span 도우미(`_start_internal_or_server_span`)뿐이다. 도우미를 부르는 설치 패키지는 0개다.
#        semgrep 은 `--trace` 일 때만 extract 하고(우리는 `semgrep scan` 에 주지 않는다) 그 `traceparent` 도
#        부모 프로세스 환경변수로 스스로 만든다. anthropic SDK 의 추적은 extract 하지 않는다.
#    재검토 조건 — 충족되면 해당 ID 를 즉시 지운다:
#      (1) semgrep 이 그 ID 의 수정판을 허용하면(그 판으로 semgrep 을 올리고 예외 삭제)
#      (2) 앱에 OpenTelemetry 서버 계측(Starlette `OpenTelemetryMiddleware` · asgi/fastapi 계측)을 켜거나
#          semgrep 에 `--trace` 를 주게 되면(둘 다 삭제)
#
# CVE-2026-116684 · CVE-2026-116685 · CVE-2026-116686 (mcp 1.29.0, 2026-10-28) — CVE-2026-59951 과 같은 semgrep
#    정확 핀(`mcp==1.29.0`)이라 **버전 업으로 해결 불가**(수정판 1.30.0). 권고 전제와 우리 쪽:
#      · 116685(리다이렉트를 따라 헤더 전송) · 116686(도구 출력 스키마의 `$ref` 를 가져옴)은 MCP «클라이언트»
#        (`ClientSession`·`streamablehttp_client`·`sse_client`·`ClientSessionGroup`) 를 쓸 때만이다. semgrep
#        소스에 그 API 가 0건이고(핀을 올리면 다시 잰다), 앱 설치본에는 `mcp` 가 없다.
#      · 116684(bearer 토큰 audience 미검사)는 SDK 의 HTTP «서버» bearer 인증(`AuthSettings`+`token_verifier`)을
#        켤 때만이다. semgrep 에서 그 코드는 `semgrep mcp` 하위 명령뿐이고, 우리는 `semgrep scan` 만 부른다.
#    재검토 조건 — 충족되면 세 ID 를 즉시 지운다:
#      (1) semgrep 이 mcp 핀을 >=1.30.0 으로 올리면(CVE-2026-59951 과 함께 삭제)
#      (2) 우리가 MCP 클라이언트를 쓰거나 `semgrep mcp`(또는 SDK 의 HTTP 서버 인증)를 띄우게 되면
#
# CVE-2026-115563 (mcp 1.29.0, 2026-11-23) — 위와 같은 semgrep 정확 핀(`mcp==1.29.0`)이라 **버전 업으로 해결 불가**
#    (수정판 1.30.0 · 2.2.0). 권고 전제 = SDK 를 HTTP MCP «클라이언트»로 쓰며 `mcp.client.auth` 의 OAuth 공급자
#    (`OAuthClientProvider` · `ClientCredentialsOAuthProvider` · `PrivateKeyJWTOAuthProvider` · `RFC7523OAuthClientProvider`)를
#    전송 인증으로 붙일 때만이다. semgrep 1.185.0 · 1.186.0 소스는 `mcp.client` 를 한 번도 import 하지 않고(서버 · 공용 타입만 —
#    핀을 올리면 다시 잰다), 앱 설치본에는 `mcp` 가 없다.
#    재검토 조건 — 위 세 ID 의 (1) · (2) 와 같다(함께 지운다).
#
# CVE-2026-132276 (wcmatch 8.5.2, 2026-11-23) — semgrep 이 `wcmatch~=8.3` 을 요구해 **버전 업으로 해결 불가**(수정판 11.2).
#    권고 전제 = 별(`*`)이 여럿인 패턴에 공격자가 고른 긴 이름을 맞춤(별 k 개면 O(n^k)). 우리 사용 방식에선 **도달 불가**:
#      · semgrep 이 wcmatch 를 부르는 곳은 `target_manager.py` 의 규칙 `paths:` include · exclude 대조 하나다 — 패턴은 우리가
#        고정한 룰 묶음에서만 오고(`--include` · `--exclude` 를 주지 않는다), 그 묶음의 `paths:` 는 `**/*.m`(별 하나)뿐이다.
#      · 맞추는 대상은 우리가 지은 임시 파일 경로(`<임시 폴더>/analyze<확장자>`)다 — 바깥이 고르는 것은 확장자 10자까지
#        (`src/analyzer/io/static.py::temp_suffix`).
#      · 실측(wcmatch 8.5.2): 우리 패턴 × 지을 수 있는 최악 경로 1,080개의 한 번 대조가 최대 16 µs — 같은 계기에서 권고 PoC
#        꼴(`*_*_*_*_*.csv`)은 120자에 1.6 s.
#    재검토 조건 — 충족되면 즉시 지운다:
#      (1) semgrep 이 wcmatch >=11.2 를 허용하면(그 판으로 semgrep 을 올리고 예외 삭제)
#      (2) 룰 `paths:` 에 별이 둘 이상인 패턴이 들어오거나, semgrep 에 `--include` · `--exclude` 를 주거나, 분석 대상의
#          원래 이름을 semgrep 에 넘기게 되면
# «도달 불가» 전제(앱은 `semgrep scan` 만 · `--trace` · `mcp` · 경로 필터 인자 없음 · 대상 = 임시 파일 · 앱에 `mcp` 없음 ·
# 룰 `paths:` 패턴은 별 하나까지)는 tests/unit/scripts/test_semgrep_own_venv.py 가 잰다.
# Exceptions: each needs a reason and a removal condition above; try bumping semgrep first. The reachability
# premises are measured by test_semgrep_own_venv.py.
IGNORED_VULNS: tuple[str, ...] = (
    "CVE-2026-59951",
    "CVE-2026-114603",
    "CVE-2026-126360",
    "CVE-2026-116684",
    "CVE-2026-116685",
    "CVE-2026-116686",
    "CVE-2026-115563",
    "CVE-2026-132276",
)


def _make_stdout_safe() -> None:
    """Windows cp949 stdout 에서 이모지/한글 출력 크래시 방지 — UTF-8 재구성(errors=replace).
    Guard against the cp949 emoji/Korean print crash on Windows (UTF-8, replace on miss)."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 재구성 불가한 스트림(파이프·구버전) — 출력 인코딩은 최선 노력 / best-effort only


def audit_argv() -> list[str]:
    """semgrep venv 요구 파일을 예외 목록과 함께 감사하는 명령. / The audit command with the exception list."""
    argv = [sys.executable, "-m", "pip_audit", "-r", REQS, "--desc", "on"]
    for vuln in IGNORED_VULNS:
        argv += ["--ignore-vuln", vuln]
    return argv


def reqs_changed(base: str, head: str, cwd: Path | None = None) -> bool | None:
    """이 PR(병합 기점 → head)이 `requirements-semgrep.txt` 를 바꿨는가 — 못 재면 None(호출부가 막는다).

    🔴 세 점(`base...head`) — 병합 기점과 비교한다. 두 점은 base 가 앞서 나가며 들여온 다른 PR 의 변경까지
    이 PR 의 변경으로 읽는다. 🔴 `git diff --quiet` 의 종료 코드를 읽는다: 0 = 같음 · 1 = 다름 · 그 밖 =
    범위를 못 찾음(얕은 체크아웃 등). «못 찾음» 을 «안 바뀜» 으로 읽으면 바꾼 PR 이 경고만 받고 지나간다.
    Three-dot (merge base → head) so a base that moved ahead is not read as this PR's change.
    Exit 0 = unchanged, 1 = changed, anything else = unknown; unknown must not read as unchanged.
    """
    try:
        proc = subprocess.run(  # nosec B603 B607
            ["git", "diff", "--quiet", f"{base}...{head}", "--", REQS],
            cwd=str(cwd or _ROOT), capture_output=True, text=True, timeout=60, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode == 0:
        return False
    if proc.returncode == 1:
        return True
    return None


def must_block(*, in_pr: bool, changed: bool | None, always: bool) -> bool:
    """감사 실패를 red 로 낼 것인가. / Whether a failed audit turns the run red."""
    if always:
        return True
    if not in_pr:
        return False
    return changed is not False


def run_audit() -> tuple[int, str]:
    """감사를 돌려 (종료 코드, 출력). 도구가 없거나 못 돌면 종료 코드는 0 이 아니다.

    `PYTHONUTF8=1` — 요구 파일의 한글 주석을 pip 이 로캘 인코딩으로 읽는다. Windows(cp949)에서는 그 자리에서
    `UnicodeDecodeError` 로 죽었다(CI 의 Linux 는 UTF-8 이라 같은 파일을 읽는다).
    UTF-8 mode: pip reads the requirements file in the locale encoding, which is cp949 on this Windows box.
    """
    try:
        proc = subprocess.run(  # nosec B603
            audit_argv(), cwd=str(_ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=900, check=False,
            env={**os.environ, "PYTHONUTF8": "1"},
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 2, f"pip-audit 를 돌리지 못했다: {exc}"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _append_step_summary(markdown: str) -> None:
    """job summary 에 한 단락 — 로그 안쪽만으로는 아무도 안 본다. 기록 실패는 판정을 바꾸지 않는다."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(markdown)
    except OSError:
        pass  # 기록 실패가 판정을 바꾸면 안 된다 / logging must never change the verdict


def _block_reason(*, always: bool, changed: bool | None) -> str:
    if always:
        return "주간 감사(`--always-block`)"
    if changed:
        return f"이 PR 이 `{REQS}` 를 바꿨다 — 권고를 들여오는 자리다"
    return f"이 PR 이 `{REQS}` 를 바꿨는지 못 쟀다(PR 범위가 반쪽이거나 base · head 가 없다) — 못 재면 막는다"


def _gh(args: list[str]) -> subprocess.CompletedProcess:
    """gh CLI 한 번 — 시험이 바꿔 끼운다. / One gh call; tests replace this."""
    return subprocess.run(  # nosec B603 B607
        ["gh", *args], cwd=str(_ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120, check=False,
    )


def _issue_body(report: Path | None) -> str:
    if report is not None and report.is_file():
        text = report.read_text(encoding="utf-8", errors="replace")[-_REPORT_TAIL:]
    else:
        text = "(감사 출력이 없다 — 감사 스텝이 끝나지 못했다)"
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    run = f"{server}/{repo}/actions/runs/{run_id}" if repo and run_id else "(실행 링크 없음)"
    return (
        "주간 semgrep venv 감사가 예외 밖 권고를 찾았거나 감사를 끝내지 못했다.\n\n"
        f"- 실행: {run}\n"
        f"- 다음 할 일: semgrep 을 올려 풀리는지 본다 → 안 되면 `scripts/semgrep_audit.py` 에 근거 · 제거 조건과 함께 "
        f"예외를 적는다(그 PR 은 `{REQS}` 를 바꾸면 이 감사가 막는다).\n\n"
        "<details><summary>감사 출력(끝 부분)</summary>\n\n```\n"
        f"{text.replace('```', '`` `')}\n```\n</details>\n"
    )


def notify(report: Path | None) -> int:
    """고정 제목의 **열린** 이슈에 댓글 — 없으면 새 이슈. 제목은 정확히 같아야 같은 이슈다.

    🔴 열린 이슈를 못 읽으면 새로 만들지 않고 1 — 중복 이슈를 쌓거나 조용히 넘어가지 않는다.
    Comment on the open issue with this exact title, or open one; failing to list issues is a failure.
    """
    listed = _gh(["issue", "list", "--state", "open", "--limit", "200", "--json", "number,title"])
    if listed.returncode != 0:
        print(f"🔴 열린 이슈를 읽지 못했다 — 알리지 못했다:\n{(listed.stderr or '')[-500:]}", file=sys.stderr)
        return 1
    try:
        issues = json.loads(listed.stdout or "[]")
    except ValueError:
        print("🔴 이슈 목록을 해석하지 못했다 — 알리지 못했다", file=sys.stderr)
        return 1
    same = [item for item in issues if item.get("title") == ISSUE_TITLE]
    body = _issue_body(report)
    found = count_kinds(body)
    if found:
        shapes = " · ".join(f"{kind} {n}" for kind, n in sorted(found.items()))
        print(f"🔴 이슈 본문에 비밀값 · 개인정보 꼴 {shapes}(값은 열지 않는다) — 올리지 않았다. 실행 로그에서 감사 출력을 본다",
              file=sys.stderr)
        return 1
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", delete=False) as fh:
        fh.write(body)
        body_file = fh.name
    try:
        if same:
            done = _gh(["issue", "comment", str(same[0]["number"]), "--body-file", body_file])
        else:
            done = _gh(["issue", "create", "--title", ISSUE_TITLE, "--body-file", body_file])
    finally:
        Path(body_file).unlink(missing_ok=True)
    if done.returncode != 0:
        print(f"🔴 이슈에 알리지 못했다:\n{(done.stderr or '')[-500:]}", file=sys.stderr)
        return 1
    print(f"✅ 알림 — {'이슈 #' + str(same[0]['number']) + ' 에 댓글' if same else '새 이슈'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    _make_stdout_safe()
    parser = argparse.ArgumentParser(description="semgrep 자기 venv 감사")
    parser.add_argument("--always-block", action="store_true", help="주간 실행 — 감사 실패를 늘 red 로")
    parser.add_argument("--notify", metavar="REPORT", help="주간 실행의 알림 — 보고서 파일로 이슈에 알린다")
    parser.add_argument("--report", metavar="PATH", help="감사 출력을 이 파일에도 쓴다(주간 실행의 알림 본문)")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.notify is not None:
        return notify(Path(args.notify))

    base = (os.environ.get("PR_BASE_SHA") or "").strip()
    head = (os.environ.get("PR_HEAD_SHA") or "").strip()
    in_pr = bool(base or head)
    changed = reqs_changed(base, head) if base and head else None
    block = must_block(in_pr=in_pr, changed=changed, always=args.always_block)

    rc, out = run_audit()
    print(out)
    if args.report:
        Path(args.report).write_text(out, encoding="utf-8")
    if rc == 0:
        print("✅ semgrep venv 감사 통과 — 예외 밖 권고 없음")
        return 0
    if block:
        print(f"🔴 semgrep venv 감사 실패 — {_block_reason(always=args.always_block, changed=changed)}.\n"
              "   semgrep 을 올려 풀리는지 먼저 본다 → 안 되면 scripts/semgrep_audit.py 에 근거 · 제거 조건과 함께 예외를 적는다.",
              file=sys.stderr)
        return 1
    print(f"::warning title=semgrep venv 감사::예외 밖 권고(또는 감사 실패) — 이 실행은 `{REQS}` 를 바꾸지 않아 막지 않는다. "
          "주간 감사가 이슈로 알린다.")
    _append_step_summary(
        "- ⚠️ **semgrep venv 감사 실패 — 경고만**(이 실행은 semgrep 요구 파일을 바꾸지 않았다). "
        "주간 감사가 이슈로 알린다.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
