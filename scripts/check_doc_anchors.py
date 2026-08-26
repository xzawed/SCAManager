#!/usr/bin/env python3
"""문서의 코드 좌표는 **줄번호가 아니라 앵커**여야 하고, 앵커는 **유일**해야 한다.

## 🔴 왜 (2026-08-26 실측)

영역 문서의 `file:line` 참조 93건 중 **24건이 틀려 있었다.** 깨진 시점이 특정된다 —
하루 전 머지 3건이고, 그때 red 가 된 게이트는 0건이다:

    030e4d6c (08-25)  src/main.py:74 = `class SecurityHeadersMiddleware`   정확
    a9c09bf6 (부모)   동일
    ea870b7c (08-26)  src/main.py:74 = ''  (빈 줄)  <- 위에 코드가 삽입됐다

`CLAUDE.md` 는 「좌표는 실측값」을 요구했지만 그것을 재는 가드가 없었다.

## 판정

줄번호는 **코드가 위에서 늘어나면 반드시 틀려진다.** 그래서 구조로 막는다:

    `path:NNN`        금지 — 다음 삽입에 조용히 거짓이 된다
    `path::anchor`    허용 — anchor 는 그 파일에 **정확히 한 번** 나타나는 문자열이다
    `::anchor`        허용 — 섹션이 「좌표는 `X`」로 선언한 기준 파일에 대조한다

## 🔴 유일성이 이 가드의 전부다 (Grok 반증, session 01a0402e-17c8-72e2-85ed-33871d75a0a2)

초판은 「앵커가 파일 어딘가에 있는가」만 봤다. 그러면 `result_dict["static_analysis_incomplete"]`
대입을 지워도 그 이름을 언급하는 **주석 두 줄이 남아** 초록이다. 즉 «✅ 전건 실재» 를
인쇄하면서 사라진 코드를 가리킨다 — 그건 줄번호보다 나쁘다(거짓 집행자).
docstring 이 「유일하게 그 자리를 가리키는 문자열」이라 약속해 놓고 코드는 존재만 봤다.

그래서 **count == 1** 을 강제한다. 다중 일치는 「자리를 특정하지 못한다」이므로 red 다.
호출부가 여러 곳이라 유일해지지 않으면, 그것은 문서가 **정의부**를 가리켜야 한다는 신호다.

## 이 가드가 재는 것 / 재지 않는 것

- 잰다: 앵커가 그 파일에 **정확히 한 번** 나타나는가. 0회·2회 이상이면 red.
- 안 잰다: 그 자리가 문장의 주장과 맞는가. 다만 사라지면 red 이므로 조용히 틀릴 수는 없다.

사용법 / Usage: python scripts/check_doc_anchors.py
"""
from __future__ import annotations

import io
import pathlib
import re
import subprocess
import sys


def _make_stdout_safe() -> None:
    """Windows(cp949) 콘솔에서 한국어 출력이 UnicodeEncodeError 로 죽는 것을 막는다.
    Repo convention: every script re-wraps stdout as UTF-8 before printing non-ASCII.
    """
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


_make_stdout_safe()

# 검사 대상 — 사람이 읽는 README 는 제외한다(코드 좌표를 싣지 않는다).
_SKIP_BASENAMES = ("README",)

# 🔴 `md` 를 포함한다 — 빠져 있던 동안 `docs/architecture.md::tools/` 는 **앵커로 파싱조차
#    되지 않아** 문자열이 사라져도 초록이었다(Grok 지적).
_EXTS = "py|ya?ml|toml|json|html|js|ts|ini|cfg|sh|md"

# 앵커가 이보다 짧으면 아무 데나 맞는다 — `src/main.py::a` 같은 자기면제를 막는다.
_MIN_ANCHOR = 4

# `path::anchor` — anchor 는 백틱만 아니면 무엇이든(공백·괄호 포함).
_ANCHOR = re.compile(r"`([A-Za-z0-9_./+-]+\.(?:" + _EXTS + r"))::([^`]+)`")
# 섹션이 기준 파일을 선언한 뒤의 `::anchor`.
_BASE_ANCHOR = re.compile(r"`::([^`]+)`")
_BASE_DECL = re.compile(r"좌표는\s*`([A-Za-z0-9_./+-]+\.(?:" + _EXTS + r"))`")

# 🔴 **꼬리를 열거하지 않는다.** 초판은 `` `path:123` `` 과 `` `path:123-456` `` 만 알았고
#    실제 문서의 `:51,150`(쉼표) · `:34~41`(물결) · `` `gitleaks`:30 ``(백틱 밖) ·
#    `(:48)`(괄호) · `` `x` :5 ``(공백) 을 놓쳤다 — 이 파일이 고치려는 실패를 스스로 저질렀다.
#    그래서 「콜론 뒤에 숫자가 오는가」만 본다.
_LINE_REF = re.compile(r"`([A-Za-z0-9_./+-]+\.(?:" + _EXTS + r")):\d")
_BARE_REF = re.compile(r"`\s*:\d")           # `:377`  ·  `x` :5
_PAREN_REF = re.compile(r"\(\s*:\d")         # (:48) · (:48-49)
# `path.py:symbol` — 단일 콜론 + 식별자. 앵커가 되려면 콜론이 둘이어야 한다.
_SINGLE_COLON = re.compile(r"`([A-Za-z0-9_./+-]+\.(?:" + _EXTS + r")):(?!:)[A-Za-z_]")


def tracked_files() -> set[str]:
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True,
                         encoding="utf-8").stdout
    return set(out.splitlines())


def target_docs(tracked: set[str]) -> list[str]:
    return sorted(
        f for f in tracked
        if f.endswith(".md") and not f.rsplit("/", 1)[-1].startswith(_SKIP_BASENAMES)
    )


def resolve(path: str, tracked: set[str]) -> str | None:
    """정확 경로 또는 유일한 basename 일치. 애매하면 None."""
    if path in tracked:
        return path
    hits = [t for t in tracked if t.endswith("/" + path)]
    return hits[0] if len(hits) == 1 else None


def file_text(path: str) -> str:
    return pathlib.Path(path).read_bytes().decode("utf-8", errors="replace")


def _check_anchor(doc: str, i: int, path: str | None, anchor: str,
                  tracked: set[str], shown: str) -> str | None:
    """앵커 하나를 검사하고 실패 사유를 낸다(통과면 None)."""
    if path is None:
        return f"{doc}:{i}  {shown} — 기준 파일 선언(「좌표는 `X`」)이 없다"
    if len(anchor) < _MIN_ANCHOR:
        return f"{doc}:{i}  {shown} — 앵커가 {_MIN_ANCHOR}자 미만이라 아무 데나 맞는다"
    target = resolve(path, tracked)
    if target is None:
        return f"{doc}:{i}  {shown} — 파일 {path} 를 못 찾는다(또는 basename 이 애매하다)"
    n = file_text(target).count(anchor)
    if n == 0:
        return f"{doc}:{i}  {shown} — 앵커 문자열이 {target} 에 없다"
    if n > 1:
        return (f"{doc}:{i}  {shown} — {target} 에 {n}회 나타나 자리를 특정하지 못한다. "
                f"정의부를 가리키도록 좁혀라")
    return None


def scan(tracked: set[str]) -> tuple[list[str], list[str], int]:
    """(앵커 실패, 줄번호 참조, 검사한 앵커 수)."""
    dead: list[str] = []
    line_refs: list[str] = []
    checked = 0

    for doc in target_docs(tracked):
        base: str | None = None
        for i, line in enumerate(file_text(doc).splitlines(), 1):
            decl = _BASE_DECL.search(line)
            if decl:
                base = decl.group(1)

            for m in _ANCHOR.finditer(line):
                checked += 1
                bad = _check_anchor(doc, i, m.group(1), m.group(2), tracked,
                                    f"`{m.group(1)}::{m.group(2)}`")
                if bad:
                    dead.append(bad)

            for m in _BASE_ANCHOR.finditer(line):
                checked += 1
                bad = _check_anchor(doc, i, base, m.group(1), tracked, f"`::{m.group(1)}`")
                if bad:
                    dead.append(bad)

            for rx, label in ((_LINE_REF, "줄번호"), (_BARE_REF, "맨 줄번호"),
                              (_PAREN_REF, "괄호 줄번호"), (_SINGLE_COLON, "단일 콜론")):
                for m in rx.finditer(line):
                    line_refs.append(f"{doc}:{i}  {label}: {m.group(0)!r}")

    return dead, line_refs, checked



def main() -> int:
    tracked = tracked_files()
    dead, line_refs, checked = scan(tracked)

    print("=== 문서 코드 앵커 점검 / Doc Code-Anchor Check ===\n")
    print(f"검사한 앵커: {checked}건")

    # 🔴 계기 자기검증 — 앵커가 0건이면 이 가드는 아무것도 재지 않았다.
    #    "초록" 과 "안 쟀음" 을 구별하지 못하면 이 파일 자체가 거짓 집행자가 된다.
    if checked == 0 and not line_refs:
        print(
            "🔴 앵커도 줄번호 참조도 0건 — 이 가드는 **아무것도 재지 않았다**.\n"
            "   문서 규약이 바뀌었거나 정규식이 깨졌다. 초록이 아니다.",
            file=sys.stderr,
        )
        return 1

    if line_refs:
        print(f"\n🔴 줄번호 참조 {len(line_refs)}건 — 앵커(`path::문자열`)로 바꿔라:")
        for r in line_refs:
            print(f"   {r}")
        print(
            "\n   줄번호는 위에 코드가 삽입되면 **조용히** 거짓이 된다.\n"
            "   2026-08-26 실측: 머지 3건이 하루 만에 24건을 무효화했고 red 는 0건이었다."
        )

    if dead:
        print(f"\n🔴 앵커가 자리를 특정하지 못한다 {len(dead)}건:")
        for r in dead:
            print(f"   {r}")

    if not dead and not line_refs:
        print("\n✅ 모든 코드 좌표가 앵커이고, 앵커가 전건 **유일하게** 실재한다")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
