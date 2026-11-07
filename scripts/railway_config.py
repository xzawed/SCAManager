#!/usr/bin/env python3
"""Railway 배포 설정을 «변수 값 없이» 읽는다 — `railway environment config --json` 의 안전한 대체.
Read the Railway deploy config without any variable values.

`railway environment config --json` 은 서비스 변수와 공유 변수의 **값**을 평문으로 싣는다
(CLI 가 복호화해서 조회한다). 그래서 credential 덤프 차단 훅이 그 명령을 막고 이 스크립트로 보낸다.

## 판정

- 서비스마다 `deploy` · `build` 두 절**만** 남긴다(허용 목록). CLI 가 새 절을 더해도 그 절은 버려진다.
- 남긴 절 안에 `variables` · `sharedVariables` · `value` 키가 있으면 **출력하지 않고 red** 다
  (CLI 가 나중에 값을 그 절로 옮겨도 새지 않는다).
- 못 읽으면 red — CLI 없음 · 실패 · JSON 아님 · 서비스 0개. 원문은 값이 들어 있을 수 있으니
  에러에도 싣지 않는다.

Keeps only `deploy` and `build` per service (allowlist). Refuses if a kept section carries a
variables/value key. Anything unreadable is red, and the raw output is never echoed.

Usage: py -3 scripts/railway_config.py [--environment production]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys

_KEEP = ("deploy", "build")
_VALUE_KEYS = frozenset({"variables", "sharedVariables", "value"})


def _make_stdout_safe() -> None:
    """Windows cp949 stdout 에서 한글 출력 크래시를 막는다 — UTF-8 재구성.
    Guard against the cp949 crash on Windows when printing Korean."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 캡처된 stream 등 — 무시 / captured streams: ignore


def _carries_values(node) -> bool:
    """남길 절 안 어디든 값 키가 있는가 / Does any nested key look like a value carrier?"""
    if isinstance(node, dict):
        return any(k in _VALUE_KEYS or _carries_values(v) for k, v in node.items())
    if isinstance(node, list):
        return any(_carries_values(v) for v in node)
    return False


def _fail(message: str) -> int:
    print(f"railway_config: {message}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    _make_stdout_safe()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--environment", "-e", help="환경 이름(기본 = 링크된 환경)")
    args = parser.parse_args(argv)

    # npm 으로 깐 CLI 는 Windows 에서 `railway.cmd` shim 이라 확장자 없는 이름으로는 실행되지 않는다.
    # The npm-installed CLI is a `railway.cmd` shim on Windows; resolve it through PATHEXT.
    exe = shutil.which("railway")
    if not exe:
        return _fail("railway CLI 가 없다 / railway CLI not found")
    cmd = [exe, "environment", "config", "--json"]
    if args.environment:
        cmd += ["--environment", args.environment]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=60, check=False)
    except FileNotFoundError:
        return _fail("railway CLI 가 없다 / railway CLI not found")
    except subprocess.TimeoutExpired:
        return _fail("railway CLI 가 60초 안에 끝나지 않았다 / timed out")
    if proc.returncode != 0:
        # stdout·stderr 어느 쪽도 싣지 않는다 — 어디에 값이 섞일지 이 스크립트는 모른다.
        # Echo neither stream: this script cannot know where a value might appear.
        return _fail(f"railway 실패 rc={proc.returncode} — `railway status` · `railway login` 으로 확인")
    try:
        data = json.loads(proc.stdout or "")
    except (TypeError, ValueError):
        return _fail("출력이 JSON 이 아니다 — 원문은 값이 있을 수 있어 보이지 않는다 / not JSON")

    services = data.get("services") if isinstance(data, dict) else None
    if not isinstance(services, dict) or not services:
        return _fail("서비스를 하나도 못 읽었다 / no services in the config")
    shown = {}
    for sid, svc in services.items():
        if not isinstance(svc, dict):
            continue
        kept = {k: svc[k] for k in _KEEP if k in svc}
        if _carries_values(kept):
            return _fail(f"{sid}: 남길 절에 값 키가 있다 — 출력을 거절한다 / value key inside a kept section")
        # 남길 절이 없는 서비스는 빈 객체로 찍지 않는다 — 대조할 값이 없다(Grok G3 지적).
        # A service with no kept section is omitted: there is nothing to compare.
        if kept:
            shown[sid] = kept
    if not shown:
        return _fail("서비스를 하나도 못 읽었다 / no readable service")
    print(json.dumps({"services": shown}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
