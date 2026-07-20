"""owed 원장의 **산문 ↔ 상태 표** 정합 불변식.

## 사고 (2026-07-19 회고 P2 — B3·B4·B5·B6·B7·B12)

원장 안에서 서술 산문과 상태 표가 서로 다른 말을 하고 있었다:

  · `:54` "`INTERNAL_CRON_API_KEY` … 로테이션 **미결**"  ↔  `#1106` 행 = `⏭️ 로테이션 안 함(확정)`
  · `:59` "토큰 로테이션 **필요**(운영자 영역)"        ↔  `#1104` 행 = `⏭️ 로테이션 안 함(확정)`
  · `:102` "#1073·#1075 는 배포 후에야 **검증 가능**"   ↔  두 행 모두 `✅ 종결`

## 🔴 왜 이게 특별히 위험한가 (B12)

stale 산문 중 하나가 **`### 이미 확인된 것 (재확인 불필요)`** 헤더 아래 있었다. 즉 미래
세션은 틀린 내용을 **"재확인하지 말라" 는 명시적 승인과 함께** 승계한다. 헤더가 문자 그대로
조사 중단 장치로 작동한다.

## 🔴 그리고 기계도 못 봤다 (B7)

`check_owed_verification.py` 의 행 파서는 첫 셀이 `**#NNNN**` 인 행만 읽는다. 문제의 `:54`
행은 첫 셀이 `` `INTERNAL_CRON_API_KEY` `` 라 **구조적으로 탐지 불가**였다. 카운터가 green
인 것이 원장 정합성 보증으로 오독됐다 — 인지·기계 **양쪽 관측면 밖**.

## 검사 방식: 종결된 ID 에 대해 미결 어휘를 쓰지 않는다

산문의 진위는 판정할 수 없다. 그러나 **"#NNNN 의 상태 표가 종결(✅/❌/⏭️)인데 산문이 그 ID 를
미결 어휘(미결·필요·대기)로 서술한다"** 는 기계가 판정할 수 있는 모순이다.
Prose truth is undecidable; a terminal-status ID described with pending vocabulary is not.
"""
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_LEDGER = _ROOT / "docs" / "runbooks" / "owed-verification.md"

_TERMINAL = ("✅", "❌", "⏭️")
_PENDING_MARK = "⏳"
# 미결을 뜻하는 어휘 — 종결된 ID 를 이렇게 서술하면 모순이다.
_PENDING_WORDS = ("미결", "로테이션 필요", "검증 가능하다", "회신 대기")


def _text() -> str:
    return _LEDGER.read_text(encoding="utf-8")


def status_by_id(text: str) -> dict:
    """상태 표에서 `#NNNN` → 마지막 셀의 상태 마커. 표 행만 읽는다."""
    out = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        m = re.match(r"^\*{0,2}(#\d+)\*{0,2}$", cells[0])
        if not m:
            continue
        marker = next((s for s in (*_TERMINAL, _PENDING_MARK) if s in cells[-1]), None)
        if marker:
            out[m.group(1)] = marker
    return out


_STRIKE_RE = re.compile(r"~~.*?~~")


def _live_part(line: str) -> str:
    """취소선 **구간만** 제거한 나머지 — 줄 전체를 면제하지 않는다.

    🔴 Grok 적대 검토 C2 (2026-07-20): 이전 판은 `"~~" in line` 이면 그 줄을 통째로
    건너뛰었다. 그래서 stale 주장 뒤에 `~~x~~` 를 붙이기만 해도 검사를 빠져나갔다.
    취소선은 "이 **구간**은 폐기됐다" 는 뜻이지 "이 줄은 검사 대상이 아니다" 가 아니다.
    A whole-line skip let any line opt out by appending a strikethrough anywhere.
    """
    return _STRIKE_RE.sub("", line)


def item_aliases(text: str) -> dict:
    """`#NNNN` → 그 항목을 가리키는 식별 토큰(백틱 인용 대문자 키) 집합.

    🔴 Grok 적대 검토가 지목한 **최고 가치 사각** (2026-07-20): 상태 주장이 `#NNNN` 없이
    **이름만으로** 쓰이면 이전 판은 아무것도 보지 못했다. 실제 사고 문장이 정확히 그 형태에
    가까웠다 — *"`INTERNAL_CRON_API_KEY` … 로테이션 **미결**"*. ID 를 빼고 키 이름만 쓰면
    가드가 눈이 먼다.
    Status claims written by NAME instead of #ID were structurally invisible.
    """
    out = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        m = re.match(r"^\*{0,2}(#\d+)\*{0,2}$", cells[0])
        if not m:
            continue
        # 행 본문의 백틱 인용 중 ENV 키 형태(대문자+언더스코어)만 별칭으로 본다
        tokens = {
            tok for tok in re.findall(r"`([A-Z][A-Z0-9_]{4,})`", " ".join(cells[1:]))
        }
        if tokens:
            out[m.group(1)] = tokens
    return out


def _prose_lines(text: str) -> list:
    """상태 표 행이 아닌 줄 — 서술 산문 + 보조 표(`재확인 불필요` 등)."""
    keep = []
    for i, line in enumerate(text.splitlines(), 1):
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.startswith("|") else []
        if cells and re.match(r"^\*{0,2}#\d+\*{0,2}$", cells[0]):
            continue  # 상태 표 행 자체는 정본이므로 제외
        keep.append((i, line))
    return keep


# ── 핵심 불변식 ─────────────────────────────────────────────────────────


def test_prose_does_not_call_a_terminal_item_pending():
    """🔴 상태 표가 종결한 ID 를 산문이 미결 어휘로 서술하면 안 된다.

    실측 사고 3건이 정확히 이 형태였고, 그중 하나는 '재확인 불필요' 헤더 아래 있었다.
    """
    text = _text()
    statuses = status_by_id(text)
    terminal = {k for k, v in statuses.items() if v in _TERMINAL}
    assert terminal, "종결된 항목이 하나도 없다 — 이 가드의 전제 붕괴"

    aliases = item_aliases(text)
    offenders = []
    for lineno, raw in _prose_lines(text):
        line = _live_part(raw)          # 취소선 구간만 제거 (줄 전체 면제 금지)
        if not any(w in line for w in _PENDING_WORDS):
            continue
        # (a) ID 로 지목한 경우 (b) 🔴 ID 없이 **키 이름만** 쓴 경우 — 둘 다 본다
        hit = {pid for pid in re.findall(r"#\d+", line) if pid in terminal}
        hit |= {
            pid for pid, toks in aliases.items()
            if pid in terminal and any(tok in line for tok in toks)
        }
        for pid in sorted(hit):
            offenders.append(f"{_LEDGER.name}:{lineno} — {pid}({statuses[pid]}) 를 미결로 서술")
    assert not offenders, (
        "종결된 항목을 미결로 서술하는 산문:\n  " + "\n  ".join(offenders) +
        "\n→ 상태 표가 정본이다. 표 셀을 바꿀 때 **같은 커밋에서** 산문도 고칠 것."
    )


def test_already_verified_section_defers_instead_of_restating_status():
    """🔴 '재확인 불필요' 섹션은 상태를 **다시 쓰지 말고 정본을 가리켜야** 한다.

    이 섹션은 조사 중단 장치다 — 여기 있는 내용이 틀리면 미래 세션은 그것을 **명시적
    승인과 함께** 승계한다. 그래서 이 섹션이 상태를 복제하면 복제본이 stale 될 때
    피해가 가장 크다.
    """
    text = _text()
    start = text.index("### 이미 확인된 것 (재확인 불필요)")
    end = text.index("\n## ", start)
    section = text[start:end]
    statuses = status_by_id(text)

    bad = []
    for line in section.splitlines():
        for pid in re.findall(r"#\d+", line):
            if statuses.get(pid) in _TERMINAL and not any(
                k in line for k in ("정본", "행이", "표", "참조")
            ):
                bad.append(f"{pid} 언급이 정본 참조 없이 상태를 서술한다: {line[:70]}")
    assert not bad, (
        "'재확인 불필요' 섹션이 상태를 복제한다:\n  " + "\n  ".join(bad) +
        "\n→ 상태를 다시 쓰지 말고 안전등급 표 행을 가리킬 것(복제본은 반드시 stale 된다)."
    )


def test_parser_blind_rows_do_not_carry_status_claims():
    """🔴 `check_owed_verification.py` 가 못 읽는 행이 상태를 주장하면 안 된다 (B7).

    파서는 첫 셀이 `**#NNNN**` 인 행만 읽는다. 다른 형태의 표 행이 상태를 주장하면
    그 주장은 **기계 관측면 밖**에서 영구히 stale 될 수 있다 — 실제로 그랬다.
    """
    text = _text()
    statuses = status_by_id(text)
    blind = []
    for lineno, line in _prose_lines(text):
        if not line.startswith("|") or "~~" in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        # 🔴 **특정 항목에 대한** 상태 주장만 본다 — 규칙을 서술하는 행은 대상이 아니다.
        #   작성 중 실측: 훅 명세 표의 `| 판정 | 안전등급 ⏳ ≥1건 → breached (운영등급 미결은
        #   카운트만 보고) |` 가 "미결" 을 담았다는 이유로 위반 신고됐다. 그 행은 어떤 항목의
        #   상태도 주장하지 않는다 — 판정 **규칙**을 적은 것이다.
        #   관측 범위를 틀리면 가드가 거짓말을 한다(이 파일이 고치려는 결함과 같은 병).
        # Only claims ABOUT a specific tracked item count; rule descriptions are not claims.
        referenced = [pid for pid in re.findall(r"#\d+", line) if pid in statuses]
        if not referenced:
            continue
        if any(w in line for w in _PENDING_WORDS) and not any(
            k in line for k in ("정본", "행이", "참조", "종결")
        ):
            blind.append(f"{_LEDGER.name}:{lineno} — {cells[0][:34]} ({','.join(referenced)})")
    assert not blind, (
        "파서 사각 행이 미결 상태를 주장한다:\n  " + "\n  ".join(blind) +
        f"\n(현재 파서 가시 항목: {sorted(statuses)})\n"
        "→ 상태 주장은 `**#NNNN**` 표 행에만 두고, 나머지는 그 행을 가리킬 것."
    )


# ── 탐지력 자가 검증 ────────────────────────────────────────────────────


def test_status_parser_matches_the_production_parser_shape():
    """이 테스트의 파서가 실제 원장을 읽는지 — 0건이면 모든 단언이 공허하다."""
    statuses = status_by_id(_text())
    assert len(statuses) >= 5, f"상태 표에서 {len(statuses)}건만 읽혔다 — 형식 확인 필요"
    assert any(v == _PENDING_MARK for v in statuses.values()), "미결(⏳) 항목이 없다"
    assert any(v in _TERMINAL for v in statuses.values()), "종결 항목이 없다"


def test_detector_flags_a_synthetic_contradiction():
    """합성 모순을 실제로 잡는가 — 통과만 하는 가드 차단."""
    synthetic = (
        "| **#9999** | 무엇 | 근거 | 13 | ✅ |\n"
        "설명 산문에서 #9999 는 로테이션 필요 하다고 적는다.\n"
    )
    statuses = status_by_id(synthetic)
    assert statuses == {"#9999": "✅"}
    offending = [
        line for _, line in _prose_lines(synthetic)
        if "#9999" in line and any(w in line for w in _PENDING_WORDS)
    ]
    assert offending, "합성 모순을 탐지하지 못했다"
