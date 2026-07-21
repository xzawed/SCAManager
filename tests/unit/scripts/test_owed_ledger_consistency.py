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

    🔴 **알려진 한계 — 자연어 이름은 못 잡는다 (2026-07-20 세션5 회고 P2, 정직한 미봉인).**
    백틱 ENV 키·`#NNNN` 은 잡지만, *"Telegram 봇 토큰은 로테이션 미결"* 처럼 **백틱도 ID 도
    없는 자연어**로 쓴 stale 주장은 여전히 샌다. **일부러 자연어 매처를 만들지 않는다** —
    임의 명사구를 항목에 결속하는 것은 신뢰 불가하고(과탐), '강해 보이지만 아닌 가드' 는 이
    세션이 Grok 에게 반복해 반증당한 형태다. 대신 원장 작성 규율(상태 주장은 `**#NNNN**` 행에)
    로 막고, 여기서는 **한계를 명시**한다. 현재 원장에 이 형태의 live 사례는 없다(실측).
    Natural-language-only aliases are deliberately NOT matched — an unreliable matcher would be
    exactly the "looks-strong-but-isn't" guard this session kept getting refuted on.
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


# ── 안전등급 자기인증 방지 (세션5 회고 P1 — #1129 재위반) ────────────────

_SAFETY_SECTION = "## 🔴 안전/데이터 등급"
# ⏭️(보류)를 정당화하는 인용 — 사용자 결정 또는 moot 근거.
_USER_DECISION = ("사용자 명시 결정", "사용자 회신", "사용자 확인", "사용자 검증", "사용자 결정")
_MOOT_BASIS = ("재분류", "운영 위험 0", "위험 0")
# 🔴 ✅(검증 완료)를 정당화하는 인용 — **긍정적 완료** 만. "사용자 회신 **대기**" 는 완료가
#   아니라 미결이므로 여기 없다. 이 구별이 핵심: #1062 pending 행에 "사용자 회신 대기" 가
#   있다는 이유로 ✅ 를 통과시키면, 산문이 검사를 통과시키는(이 세션 반복 결함) 함정에 빠진다.
# Only affirmative-completion tokens justify ✅; "waiting for user reply" is pending, not done.
_USER_VERIFIED = ("사용자 확인 완료", "사용자 회신 완료", "사용자 검증 완료",
                  "사용자 OK", "사용자 명시 OK")


def _safety_rows(text: str):
    """안전등급 표의 (pid, status, body) 행 — 첫 셀이 `**#NNNN**` 인 것만."""
    start = text.index(_SAFETY_SECTION)
    rest = text[start + len(_SAFETY_SECTION):]
    end = rest.index("\n## ") if "\n## " in rest else len(rest)
    for line in rest[:end].splitlines():
        if not line.startswith("| **#"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        m = re.match(r"^\*\*(#\d+)\*\*$", cells[0])
        if not m:
            continue
        status = next((s for s in (*_TERMINAL, _PENDING_MARK) if s in cells[-1]), None)
        yield m.group(1), status, " ".join(cells[1:])


def test_safety_grade_verified_status_requires_a_user_citation():
    """🔴 안전등급 행의 ✅(검증됨)는 **사용자 검증 인용**이 있어야 한다.

    ## 실제 사고 (2026-07-19 P0 → 세션5 회고 P1 재적발)

    `#1129` 가 `#1062`(NULL-owner IDOR, 안전등급)를 **DB 스냅샷 구조 논증**으로 ✅ 처리해,
    매 세션 loud 경고를 내던 **유일한 안전등급 신호를 소거**했다. 안전등급 검증은 원장이
    "사용자만 할 수 있는 운영 검증" 으로 규정한 영역이라, Claude 가 ✅ 를 찍는 것 자체가
    구조적으로 부당하다. 회고 P0 가 적발해 `#1132` 로 원상복구했으나, **2026-07-19 시정이
    advisory 훅(비차단)뿐이라 재위반을 막지 못했다** — 진단은 있고 집행면이 없던 것.

    🔴 이 가드가 그 집행면이다: 안전등급 ✅ 는 **사용자 검증 인용** 없이 통과할 수 없다.
    `#1129` 형(구조 논증만) 은 인용이 없어 red 가 된다. (⏭️ 는 사용자 결정 또는 moot 근거
    허용 — 아래 별도 단언.)
    Safety-grade ✅ needs a user-verification citation; Claude's structural argument alone fails.
    """
    text = _text()
    rows = list(_safety_rows(text))
    assert rows, "안전등급 행을 못 찾았다 — 표 형식이 바뀌었는지 확인할 것"
    offenders = [
        pid for pid, status, body in rows
        if status == "✅" and not any(k in body for k in _USER_VERIFIED)
    ]
    assert not offenders, (
        f"안전등급 행이 사용자 검증 인용 없이 ✅ 다: {offenders}\n"
        "→ 안전등급 검증은 사용자 전용이다. Claude 구조 논증으로 ✅ 처리 금지(#1129 재위반).\n"
        "   상태를 ⏳ 로 되돌리고 사용자 회신을 기다릴 것."
    )


def test_safety_grade_deferred_status_cites_a_decision_or_moot_basis():
    """🔴 안전등급 ⏭️(보류)는 **사용자 결정** 또는 **moot 근거(재분류·위험 0)** 를 인용해야 한다.

    인용 없는 ⏭️ 는 "사용자 회신 없이 조용히 집행면에서 이탈" 이고, 그건 안전등급이 막으려는
    바로 그 경로다(#1058 SMTP 가 그 축으로 나갈 뻔했다). #1058 은 moot(기능 미활성=위험 0),
    #1104·#1106 은 사용자 명시 결정 — 둘 다 정당한 인용을 갖는다.
    """
    text = _text()
    offenders = [
        pid for pid, status, body in _safety_rows(text)
        if status == "⏭️"
        and not any(k in body for k in (*_USER_DECISION, *_MOOT_BASIS))
    ]
    assert not offenders, (
        f"안전등급 ⏭️ 가 사용자 결정·moot 근거 인용 없이 보류됐다: {offenders}\n"
        "→ 사용자 명시 결정을 받거나, 위험 0 근거(선행조건 부재 등)를 행에 명시할 것."
    )


def test_safety_selfcert_guard_catches_a_synthetic_claude_verification():
    """합성 #1129 재현 — 구조 논증만으로 ✅ 처리한 행을 실제로 잡는가."""
    synthetic = (
        f"{_SAFETY_SECTION}\n\n| 항목 | 근거 | 사유 | 상태 |\n"
        "| **#9999** | IDOR 과잉차단 | 구조 논증으로 도달 불가 증명(DB 스냅샷) | ✅ |\n\n## 다음\n"
    )
    rows = list(_safety_rows(synthetic))
    assert len(rows) == 1 and rows[0][0] == "#9999" and rows[0][1] == "✅", rows
    # 구조 논증만 있고 사용자 인용이 없으므로 위반이어야 한다
    pid, status, body = rows[0]
    assert "사용자" not in body, "합성 입력에 사용자 인용이 들어갔다 — 케이스 무효"
    offenders = [pid for pid, st, body in rows if st == "✅" and not any(k in body for k in _USER_VERIFIED)]
    assert offenders == ["#9999"], "합성 자기인증을 탐지하지 못했다"
