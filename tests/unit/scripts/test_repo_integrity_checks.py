"""repo-integrity 체커 스크립트 회귀 가드 — check_docs_sync / check_toc_anchors.

현재 repo 에서 통과(pre-commit 이 현 상태를 막지 않음) + 합성 위반 적발(실제 drift 차단)을
양방향 고정한다. WF-2(docs 수치 정합) / WF-3(TOC 앵커 slug) 자동화의 회귀 가드.
"""
import re
import sys
from pathlib import Path

# 스크립트 임포트 경로 설정 / Script import path setup (기존 test_extract_design_tokens 패턴)
_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "scripts"))

import check_docs_sync  # noqa: E402
import check_toc_anchors  # noqa: E402


# --- check_docs_sync (WF-2) ---

def test_docs_sync_passes_on_current_repo():
    ok, msgs = check_docs_sync.check_consistency(_ROOT)
    assert ok, msgs


def test_docs_sync_flags_count_mismatch(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "STATE.md").write_text(
        "**종합 수치**: 전체 **5196** 수집 (단위 **5042** + 통합 154)\n"
        "| 전체 테스트 | **5196 수집** *(...)* | 단위 5042 + 통합 154 (현재). 이력 → 아래 절\n"
        # 이력 절은 이제 **필수**다(fail-closed) — 없으면 그 자체로 red 라 픽스처도 갖춘다.
        # The history section is now mandatory (fail-closed), so the fixture carries one.
        "\n## 테스트 수 추적 이력\n\n"
        "- **시드 항목** (5000→**5042** 단위 — 통합 154 = **5196** 수집).\n",
        encoding="utf-8",
    )
    # README 배지가 STATE 와 다른 수치(5195/5041) → 불일치 적발
    badge = "Tests-5195%2B_total_(5041_unit_%2B_154_integration)"
    (tmp_path / "README.md").write_text(f"[![Tests](x-{badge})](tests/)", encoding="utf-8")
    (tmp_path / "README.ko.md").write_text(f"[![Tests](x-{badge})](tests/)", encoding="utf-8")
    ok, msgs = check_docs_sync.check_consistency(tmp_path)
    assert not ok
    assert any("불일치" in m for m in msgs)


# --- 추적 이력 **꼬리** 축 (2026-08-05 — 구 가드가 원리적으로 못 보던 축) ---
#
# 🔴 왜 필요한가: 이력은 append-only 라 최신값이 꼬리에 있는데 가드는 `_first()` 로 머리만
# 읽었다. 그래서 "꼬리만 갱신하고 머리를 빠뜨림"(실제 발생)도, 그 반대도 탐지 대상이 아니었다.
# 아래 뮤테이션은 **실 리포 파일**을 복사해 마지막 이력 항목만 깨뜨린다(가드 3-불변식 ②).

def _count_fixture(tmp_path: Path) -> Path:
    """수치 검사가 읽는 3개 파일을 실 리포에서 그대로 복사."""
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "STATE.md").write_text(
        (_ROOT / "docs" / "STATE.md").read_text(encoding="utf-8"), encoding="utf-8")
    for rel in ("README.md", "README.ko.md"):
        (tmp_path / rel).write_text((_ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def test_docs_sync_flags_stale_history_tail(tmp_path):
    """이력 **마지막** 항목만 어긋나도 red — 머리 4곳은 전부 정상인 상태에서.

    구 가드(`_first` 단독)는 이 상태를 초록으로 통과시켰다.
    """
    root = _count_fixture(tmp_path)
    state = root / "docs" / "STATE.md"
    text = state.read_text(encoding="utf-8")
    # 이력 절 마지막 줄의 누계만 깨뜨린다 (표 머리·README 배지는 손대지 않는다)
    last = re.findall(r"=\s*\*\*(\d+)\*\* 수집", text)
    assert last, "이력 꼬리 패턴 미발견 — 형식이 바뀌었으면 가드도 함께 갱신할 것"
    tail = f"= **{last[-1]}** 수집"
    idx = text.rindex(tail)
    state.write_text(text[:idx] + "= **99999** 수집" + text[idx + len(tail):], encoding="utf-8")

    ok, msgs = check_docs_sync.check_consistency(root)
    assert not ok, "이력 꼬리가 어긋났는데 통과했다 — 꼬리 축이 관측되지 않는다"
    assert any("이력 마지막" in m for m in msgs), msgs


def test_apply_fix_derives_every_sink_from_the_history_tail(tmp_path):
    """파생 5지점을 전부 훼손해도 `--fix` 가 **이력 꼬리 하나**로부터 복원한다.

    🔴 이것이 P0-3 의 계약이다 — 손으로 유지하는 지점을 5 → 1 로 줄인다.
    복원 결과가 **원본과 바이트 동일**해야 한다: 아니면 파생이 결정적이지 않다는 뜻이고,
    그러면 `--fix` 를 돌릴 때마다 값이 흔들려 가드가 무의미해진다.
    """
    root = _count_fixture(tmp_path)
    before = {n: (root / n).read_text(encoding="utf-8")
              for n in ("docs/STATE.md", "README.md", "README.ko.md")}

    state = root / "docs" / "STATE.md"
    text = state.read_text(encoding="utf-8")
    text = re.sub(r"전체 \*\*\d+\*\* 수집 \(단위 \*\*\d+\*\*", "전체 **1111** 수집 (단위 **2222**", text, count=1)
    text = re.sub(r"\| 전체 테스트 \| \*\*\d+ 수집\*\*", "| 전체 테스트 | **3333 수집**", text, count=1)
    text = re.sub(r"단위 \d+ \+ (통합 \d+ \(현재\))", r"단위 4444 + \1", text, count=1)
    state.write_text(text, encoding="utf-8")
    for name in ("README.md", "README.ko.md"):
        path = root / name
        path.write_text(
            re.sub(r"Tests-\d+%2B_total_\(\d+_unit", "Tests-5555%2B_total_(6666_unit",
                   path.read_text(encoding="utf-8"), count=1),
            encoding="utf-8")

    assert not check_docs_sync.check_consistency(root)[0], "훼손이 red 가 아니면 이 테스트는 무의미"

    ok, msgs = check_docs_sync.apply_fix(root)
    assert ok, msgs
    for name, original in before.items():
        assert (root / name).read_text(encoding="utf-8") == original, (
            f"{name} 이 원본과 다르다 — 파생이 결정적이지 않다")
    assert check_docs_sync.check_consistency(root)[0]


def test_apply_fix_refuses_when_the_ssot_itself_is_malformed(tmp_path):
    """SSOT(이력 꼬리)가 형식을 안 갖추면 **고치지 않고 거부**한다.

    형식 없는 꼬리에서 값을 추측해 파생을 쓰면, 틀린 값을 5곳에 **자동으로 퍼뜨리게** 된다.
    """
    root = _count_fixture(tmp_path)
    state = root / "docs" / "STATE.md"
    state.write_text(state.read_text(encoding="utf-8").rstrip("\n") + "\n- 수치 없는 항목\n",
                     encoding="utf-8")
    before = state.read_text(encoding="utf-8")

    ok, msgs = check_docs_sync.apply_fix(root)
    assert not ok
    assert any("형식" in m for m in msgs), msgs
    assert state.read_text(encoding="utf-8") == before, "거부했는데 파일을 건드렸다"


def test_docs_sync_fails_when_history_section_is_deleted(tmp_path):
    """이력 절을 **통째로 지우면** red — 초판은 `None → 대조 제외` 라 초록이었다.

    🔴 *보호 장치를 삭제해도 여전히 참으로 보이는 것* 의 정확한 사례였고,
    Grok claim-review 가 실측으로 적발했다.
    """
    root = _count_fixture(tmp_path)
    state = root / "docs" / "STATE.md"
    text = state.read_text(encoding="utf-8")
    assert check_docs_sync._STATE_HIST_HEADING in text
    state.write_text(text.split(check_docs_sync._STATE_HIST_HEADING)[0], encoding="utf-8")

    ok, msgs = check_docs_sync.check_consistency(root)
    assert not ok, "이력 절이 사라졌는데 통과했다 — 가드를 지우면 초록이 되는 fail-open"
    assert any("절이 없다" in m for m in msgs), msgs


def test_docs_sync_fails_when_tail_entry_has_no_numbers(tmp_path):
    """수치 없는 항목을 꼬리에 덧붙이면 red — 초판은 직전 값이 계속 last 라 초록이었다.

    형식 계약이 곧 append 계약이다: 새 항목은 누계와 단위를 모두 적어야 한다.
    """
    root = _count_fixture(tmp_path)
    state = root / "docs" / "STATE.md"
    orig = state.read_text(encoding="utf-8")
    state.write_text(orig.rstrip("\n") + "\n- 세션N 임시 메모(수치 없음)\n", encoding="utf-8")
    assert state.read_text(encoding="utf-8") != orig  # 뮤테이션 유효성 (불변식 2)

    ok, msgs = check_docs_sync.check_consistency(root)
    assert not ok, "수치 없는 꼬리 항목이 통과했다 — 꼬리 축이 형식을 강제하지 않는다"
    assert any("형식을 갖추지 않았다" in m for m in msgs), msgs


def test_docs_sync_history_tail_is_not_the_head(tmp_path):
    """꼬리 검사가 머리를 다시 읽는 것이 아님을 증명 — 머리만 깨면 꼬리는 정상으로 보고된다.

    두 축이 같은 값을 두 번 읽는 것이라면 이 가드는 축이 하나뿐인 것과 같다.
    """
    root = _count_fixture(tmp_path)
    state = root / "docs" / "STATE.md"
    _mutate(state, "| 전체 테스트 | **", "| 전체 테스트 | **9")  # 머리만 훼손

    ok, msgs = check_docs_sync.check_consistency(root)
    assert not ok
    joined = " ".join(msgs)
    assert "STATE 추적셀(전체)=9" in joined, joined     # 머리는 훼손값
    assert "STATE 이력 마지막(전체)=9" not in joined, joined  # 꼬리는 원값 — 독립 축


# --- check_docs_sync 의존성 핀 축 (backlog R15 — ground truth 대조) ---
#
# 아래 뮤테이션은 합성 문자열이 아니라 **실 리포 파일 내용**을 복사해 깨뜨린다(가드 3-불변식 ②).
# 기대값은 테스트에 하드코딩하지 않고 현재 핀에서 유도한다 — bump 마다 테스트가 같이 썩지 않도록.
# Mutations copy the real repo files and break them; expectations derive from the current pin.

def _pin_fixture(tmp_path: Path) -> Path:
    """핀 검사가 읽는 4개 파일을 실 리포에서 그대로 복사. / Copy the 4 real files the check reads."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    for rel in ("requirements.txt", "README.md", "README.ko.md", ".claude/rules/deploy.md"):
        (tmp_path / rel).write_text((_ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def _mutate(path: Path, old: str, new: str) -> None:
    """실파일 치환 + 실제로 바뀌었는지 단언 (no-op 뮤테이션은 아무것도 증명하지 않는다)."""
    orig = path.read_text(encoding="utf-8")
    mutated = orig.replace(old, new)
    assert mutated != orig, f"뮤테이션 무효 — {path.name} 에 {old!r} 없음"
    path.write_text(mutated, encoding="utf-8")


def test_dependency_pins_pass_on_current_repo():
    ok, msgs = check_docs_sync.check_dependency_pins(_ROOT)
    assert ok, msgs


def test_dependency_pins_flag_badge_drift(tmp_path):
    """README 배지만 구버전으로 남으면 red — R15 가 두 번 재발한 바로 그 형태."""
    root = _pin_fixture(tmp_path)
    badge = re.search(r"FastAPI-(\d+\.\d+)-", (root / "README.md").read_text(encoding="utf-8"))
    _mutate(root / "README.md", f"FastAPI-{badge.group(1)}-", "FastAPI-0.1-")
    ok, msgs = check_docs_sync.check_dependency_pins(root)
    assert not ok
    assert any("README.md FastAPI 배지" in m for m in msgs)


def test_dependency_pins_flag_prose_drift(tmp_path):
    """deploy.md 산문의 핀 인용이 실핀과 어긋나면 red."""
    root = _pin_fixture(tmp_path)
    pin = re.search(r"^fastapi==(\S+)$", (root / "requirements.txt").read_text(encoding="utf-8"),
                    re.MULTILINE).group(1)
    _mutate(root / ".claude" / "rules" / "deploy.md", f"fastapi=={pin}", "fastapi==0.0.0")
    ok, msgs = check_docs_sync.check_dependency_pins(root)
    assert not ok
    assert any("deploy.md `fastapi==0.0.0`" in m for m in msgs)


def test_dependency_pins_flag_empty_scope(tmp_path):
    """인용을 통째로 지워 검사 범위를 비우면 통과가 아니라 red (빈 범위 위의 ✅ = fail-open)."""
    root = _pin_fixture(tmp_path)
    pin = re.search(r"^fastapi==(\S+)$", (root / "requirements.txt").read_text(encoding="utf-8"),
                    re.MULTILINE).group(1)
    _mutate(root / ".claude" / "rules" / "deploy.md", f"fastapi=={pin}", "fastapi 최신")
    ok, msgs = check_docs_sync.check_dependency_pins(root)
    assert not ok
    assert any("인용 0건" in m for m in msgs)


def test_dependency_pins_flag_missing_ground_truth(tmp_path):
    """기준이 되는 requirements 핀 자체가 사라지면 red — 기대값 소실을 통과로 읽지 않는다."""
    root = _pin_fixture(tmp_path)
    pin = re.search(r"^fastapi==(\S+)$", (root / "requirements.txt").read_text(encoding="utf-8"),
                    re.MULTILINE).group(1)
    _mutate(root / "requirements.txt", f"fastapi=={pin}", "fastapi")
    ok, msgs = check_docs_sync.check_dependency_pins(root)
    assert not ok
    assert any("핀 미발견" in m for m in msgs)


def test_dependency_pins_flag_starlette_prose_drift(tmp_path):
    """fastapi 만이 아니라 `_DOC_PIN_NAMES` 전건이 실제로 검사된다."""
    root = _pin_fixture(tmp_path)
    pin = re.search(r"^starlette==(\S+)$", (root / "requirements.txt").read_text(encoding="utf-8"),
                    re.MULTILINE).group(1)
    _mutate(root / ".claude" / "rules" / "deploy.md", f"starlette=={pin}", "starlette==0.0.0")
    ok, msgs = check_docs_sync.check_dependency_pins(root)
    assert not ok
    assert any("starlette==0.0.0" in m for m in msgs)


def test_dependency_pins_flag_korean_readme_badge_drift(tmp_path):
    """README.ko.md 도 검사 대상 — 한쪽만 고치고 넘어가는 실수를 막는다."""
    root = _pin_fixture(tmp_path)
    badge = re.search(r"FastAPI-(\d+\.\d+)-", (root / "README.ko.md").read_text(encoding="utf-8"))
    _mutate(root / "README.ko.md", f"FastAPI-{badge.group(1)}-", "FastAPI-0.1-")
    ok, msgs = check_docs_sync.check_dependency_pins(root)
    assert not ok
    assert any("README.ko.md FastAPI 배지" in m for m in msgs)


def test_docs_sync_main_fails_when_only_pin_axis_fails(monkeypatch, capsys):
    """🔴 집계 배선 — 수치 축이 통과해도 핀 축이 실패하면 exit 1 이어야 한다.

    Grok claim-review `019fccd5` 가 지적한 구멍: 신규 테스트가 전부
    `check_dependency_pins` 를 **직접** 호출해서, `main()` 이 `return 0 if ok else 1` 로
    퇴화해 핀 축 실패를 삼켜도 전건 green 이었다(live probe 로 실증). 이 테스트가 그 축이다.
    """
    monkeypatch.setattr(check_docs_sync, "check_consistency", lambda _root: (True, []))
    monkeypatch.setattr(
        check_docs_sync, "check_dependency_pins", lambda _root: (False, ["❌ 핀 축 실패"])
    )
    assert check_docs_sync.main() == 1
    assert "핀 축 실패" in capsys.readouterr().out


def test_precommit_hook_watches_every_file_the_check_reads():
    """🔴 배선 — pre-commit `files` 패턴이 스크립트가 읽는 파일 전건을 덮는가.

    좁은 패턴은 훅을 **조용히 안 돌게** 한다(핀만 바꾼 커밋에서 미발화). 산문 대조가 아니라
    실제 `files` 정규식을 뽑아 각 입력 경로에 매칭시킨다.
    """
    config = (_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    block = config.split("- id: check-docs-sync", 1)[1]
    pattern = re.search(r'^\s*files:\s*"(.+)"\s*$', block, re.MULTILINE).group(1)
    compiled = re.compile(pattern.replace("\\\\", "\\"))
    for path in ("docs/STATE.md", "README.md", "README.ko.md",
                 "requirements.txt", ".claude/rules/deploy.md"):
        assert compiled.match(path), f"pre-commit files 패턴이 {path} 를 놓친다"


# --- check_toc_anchors (WF-3) ---

def test_toc_anchors_passes_on_current_repo():
    text = (_ROOT / "docs" / "cycle-history.md").read_text(encoding="utf-8")
    ok, msgs = check_toc_anchors.check_anchors(text)
    assert ok, msgs


def test_toc_anchors_flags_broken():
    md = "## 목차\n- [항목](#nonexistent-anchor)\n\n## 실제 헤딩\n본문\n"
    ok, msgs = check_toc_anchors.check_anchors(md)
    assert not ok
    assert any("nonexistent-anchor" in m for m in msgs)


def test_toc_anchors_ignores_inline_code_outside_toc():
    # 본문 섹션의 인라인 코드 예시(`](#...)`)는 목차 앵커가 아니므로 오탐하지 않아야 함
    md = (
        "## 목차\n- [항목](#실제-헤딩)\n\n"
        "## 실제 헤딩\n본문에서 TOC `](#...)` 앵커 형식을 설명하는 코드 예시.\n"
    )
    ok, msgs = check_toc_anchors.check_anchors(md)
    assert ok, msgs


def test_github_slug_em_dash_double_hyphen():
    # em-dash 가 공백 사이에서 제거되어 더블하이픈 slug 생성 (#958 사고 패턴)
    assert check_toc_anchors.github_slug("A — B", {}) == "a--b"


def test_github_slug_dedup_suffix():
    seen: dict[str, int] = {}
    assert check_toc_anchors.github_slug("동일 제목", seen) == "동일-제목"
    assert check_toc_anchors.github_slug("동일 제목", seen) == "동일-제목-1"
