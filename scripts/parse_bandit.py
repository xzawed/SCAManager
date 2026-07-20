import json, sys
import sys


def _make_stdout_safe():
    """Windows cp949 stdout 에서 이모지/한글 출력 크래시 방지 — UTF-8 재구성(errors=replace).
    Guard against the cp949 emoji/Korean print crash on Windows (UTF-8, replace on miss).

    🔴 이 스크립트가 비-ASCII 를 출력하지 않아 보여도 붙인다 — **탐지를 신뢰하지 않는다**.
    구 가드는 `print()` 인자의 문자열 리터럴만 봤고, `flag = " ⚠"` 처럼 **변수를 경유**하면
    놓쳤다(2026-07-19 회고 P1 · 실제 크래시 재현). 탐지 사각이 결함의 본체이므로
    탐지 자체를 없앤다. 누락 방지는 `tests/unit/scripts/test_stdout_encoding_guard.py`.
    Attached unconditionally: the old detector only saw literals under print(), missing
    non-ASCII arriving via variables. Removing the need to detect removes the class.
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 캡처된 stream 등 reconfigure 미지원 — 무시 / stream without reconfigure


_make_stdout_safe()

with open(sys.argv[1]) as f:
    d = json.load(f)

results = d.get("results", [])
metrics = d.get("metrics", {})
totals = metrics.get("_totals", {})

print("HIGH:", int(totals.get("SEVERITY.HIGH", 0)))
print("MEDIUM:", int(totals.get("SEVERITY.MEDIUM", 0)))
print("LOW:", int(totals.get("SEVERITY.LOW", 0)))
print("---")
for r in results:
    fname = r["filename"].split("src")[-1].lstrip("/").lstrip("\\")
    print(r["issue_severity"], r["test_id"], fname, r["line_number"], r["issue_text"][:70])
