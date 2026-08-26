"""`check_memory_refs.py` 행동 가드 — 이 가드가 **조용히 죽지 않는가**.

## 왜 만드나 (2026-07-31 회고 P0-6 · P1 #55)

이 스크립트는 저장소의 check 가드 중 **유일하게 행동 테스트가 0건**이었다. 그 사이
`MEMORY_DIR` 이 구 PC 슬러그(`d--Source-SCAManager`)에 하드코딩된 채 PC 가 바뀌었고,
부재-skip 분기가 **항상** 타서 이 가드는 이 머신에서 **한 번도 검사한 적이 없다**.
초록이었지만 아무것도 보지 않았다 — 회고가 "관측자가 자기 범위를 관측하지 않는다" 로 명명한 클래스다.

🔴 그래서 이 파일의 본체는 **부정 통제**다. "정상일 때 통과" 보다 **"드리프트했을 때 red 인가"** 가
이 가드의 존재 이유다. 경로가 다시 어긋나면 여기가 빨개져야 한다.

Behaviour guard: the script had zero behavioural tests while its hardcoded memory path went stale,
so it silently passed forever. The negative controls below are the point of this file.
"""
import pytest

# 🔴 단일 import 형태 — `import X as mod` 와 `from X import ...` 공존은
#   CodeQL `py/import-and-import-from` 을 자초하고 CI `check_dual_import` 가 차단한다
#   (`docs/workflow/testing.md` — 모듈 패치 시 이중 import 회피).
# Single import form: the dual shape self-inflicts a CodeQL alert and is CI-blocked.
import scripts.check_memory_refs as mod


# ── 슬러그 유도 ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(("path", "expected"), [
    (r"f:\DEVELOPMENT\SOURCE\CLAUDE\SCAManager", "f--DEVELOPMENT-SOURCE-CLAUDE-SCAManager"),
    ("/home/dev/SCAManager", "-home-dev-SCAManager"),
    (r"D:\Source\SCAManager", "D--Source-SCAManager"),
])
def test_repo_slug_matches_claude_code_convention(path, expected):
    """🔴 드라이브 콜론과 경로 구분자가 각각 `-` 로 → `f:\\` 가 `f--` 가 된다."""
    from pathlib import PureWindowsPath, PurePosixPath
    p = PureWindowsPath(path) if ":" in path or "\\" in path else PurePosixPath(path)
    assert mod.repo_slug(p) == expected


# ── 🔴 부정 통제 — drift 는 조용히 통과하면 안 된다 (이 파일의 본체) ────


def test_main_fails_loudly_when_slug_drifts(tmp_path, monkeypatch, capsys):
    """🔴 프로젝트 루트는 있는데 대응 후보가 없으면 **exit 1** — 이게 2026-07-31 P0 그 자체다.

    이전 판은 이 상황을 '부재=정상' 으로 읽어 exit 0 을 냈고, 그래서 PC 이전 후 영구 무동작이 됐다.
    The old version returned 0 here, which is exactly how it went dead after the machine move.
    """
    projects = tmp_path / "projects"
    (projects / "some--other--project" / "memory").mkdir(parents=True)
    monkeypatch.setattr(mod, "PROJECTS_ROOT", projects)
    monkeypatch.delenv("CLAUDE_PROJECT_MEMORY_DIR", raising=False)

    assert mod.main() == 1, "슬러그 drift 를 조용히 통과시켰다 — 가드가 다시 죽었다"
    assert "슬러그" in capsys.readouterr().err or "slug drift" in capsys.readouterr().err


def test_main_skips_when_not_a_claude_machine(tmp_path, monkeypatch):
    """대조군 — 프로젝트 루트 **자체**가 없으면 skip(0). CI·타 개발자 환경은 정상이다.

    🔴 이 분기와 위 분기를 합치면 안 된다. 합쳤던 것이 P0 의 기전이었다.
    """
    monkeypatch.setattr(mod, "PROJECTS_ROOT", tmp_path / "nope")
    monkeypatch.delenv("CLAUDE_PROJECT_MEMORY_DIR", raising=False)
    assert mod.main() == 0


def test_resolve_prefers_env_override(tmp_path, monkeypatch):
    """`CLAUDE_PROJECT_MEMORY_DIR` 가 최우선 — 슬러그 규약이 바뀌어도 탈출구가 있다."""
    monkeypatch.setenv("CLAUDE_PROJECT_MEMORY_DIR", str(tmp_path))
    assert mod.resolve_memory_dir(tmp_path / "irrelevant") == tmp_path


def test_env_override_reaches_main_without_projects_root(tmp_path, monkeypatch, capsys):
    """🔴 env 는 **진입점에서도** 최우선 (Grok claim-review F1 — 실측 재현된 residual).

    초판은 `main()` 이 `PROJECTS_ROOT` 부재를 먼저 보고 skip(0) 해서, env 를 지정해도 검사가
    돌지 않았다. 문서가 광고한 탈출구가 진입점에서 막혀 있었던 것 — **탈출구가 진입점에서
    막혀 있으면 탈출구가 아니다**.
    The escape hatch was unreachable: main() skipped on a missing projects root before reading env.
    """
    memory = tmp_path / "mem"
    memory.mkdir()
    (memory / f"{_FIX_UNDER}.md").write_text("x", encoding="utf-8")
    root = tmp_path / "repo"
    root.mkdir()
    (root / "CLAUDE.md").write_text(f"메모리 `{_FIX_UNDER}.md` 참조\n", encoding="utf-8")

    monkeypatch.setattr(mod, "PROJECTS_ROOT", tmp_path / "no-such-root")
    monkeypatch.setenv("CLAUDE_PROJECT_MEMORY_DIR", str(memory))
    monkeypatch.setattr(mod, "DOC_FILES", ["CLAUDE.md"])

    rc = mod.main(project_root=root)
    out = capsys.readouterr().out
    assert "점검 skip" not in out, "env 를 지정했는데도 진입점에서 skip 됐다 — 탈출구가 막혀 있다"
    assert str(memory) in out, "env 로 지정한 디렉토리를 실제로 검사하지 않았다"
    assert rc == 0


def test_main_fails_when_doc_files_is_empty(tmp_path, monkeypatch, capsys):
    """🔴 `DOC_FILES` 가 **빈 목록**이어도 실패 — '부재 0건' 이라 부재 검사를 통과하던 구멍.

    스코프를 비우면 통과하는 검사는 그 자체로 fail-open 이다(위 F3 테스트를 쓰다 발견).
    An empty list trivially satisfies an "any missing?" check; that is fail-open by construction.
    """
    memory = tmp_path / "mem"
    memory.mkdir()
    monkeypatch.setattr(mod, "PROJECTS_ROOT", tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_MEMORY_DIR", str(memory))
    monkeypatch.setattr(mod, "DOC_FILES", [])

    assert mod.main() == 1, "스코프를 비웠는데 성공을 보고했다 — 공허 통과"
    assert "DOC_FILES" in capsys.readouterr().err


def test_resolve_does_not_auto_bind_a_near_miss(tmp_path, monkeypatch):
    """🔴 접미사만 같은 후보를 **자동 채택하지 않는다** (Grok claim-review F2 — 실측 재현).

    드라이브 문자나 상위 경로가 바뀐 경우는 정확히 우리가 loud 로 잡아야 할 drift 인데,
    초판의 fallback 이 그것을 조용히 봉합해 **무관한 프로젝트의 메모리를 검사**할 수 있었다.
    A changed drive letter is the drift we must shout about; the old fallback silently bound it.
    """
    projects = tmp_path / "projects"
    (projects / "completely--unrelated-SCAManager" / "memory").mkdir(parents=True)
    monkeypatch.setattr(mod, "PROJECTS_ROOT", projects)
    monkeypatch.delenv("CLAUDE_PROJECT_MEMORY_DIR", raising=False)

    from pathlib import PureWindowsPath
    target = PureWindowsPath(r"Z:\elsewhere\SCAManager")
    assert mod.resolve_memory_dir(target) is None, "무관한 접미사 후보를 자동 채택했다"
    # 대신 힌트로는 노출해야 한다 — 사람이 판단할 정보는 주되 추측하지 않는다.
    assert mod.near_miss_slugs(target) == ["completely--unrelated-SCAManager"]


def test_main_fails_when_scanned_docs_are_absent(tmp_path, monkeypatch, capsys):
    """🔴 검사 대상 문서가 없으면 exit 1 (Grok claim-review F3 — 실측 재현).

    초판은 부재 문서를 조용히 건너뛰어 참조 0건 → "모든 참조 존재" → exit 0 이었다.
    입력이 비었는데 성공을 보고하는 것이 이 회고가 명명한 "관측자가 자기 범위를 관측하지 않는다".
    An empty scope reported success; that is the observer-blind-to-its-own-scope class.
    """
    memory = tmp_path / "mem"
    memory.mkdir()
    monkeypatch.setattr(mod, "PROJECTS_ROOT", tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_MEMORY_DIR", str(memory))
    monkeypatch.setattr(mod, "DOC_FILES", ["NOPE.md"])

    assert mod.main() == 1, "스코프가 비었는데 성공을 보고했다"
    assert "NOPE.md" in capsys.readouterr().err


def test_collect_stale_normalizes_separators(tmp_path, monkeypatch):
    """🔴 stale 탐지도 정규화한다 (Grok claim-review F5 — 실측 재현).

    초판은 여기만 exact `slug in actual` 이라, 문서가 하이픈·파일이 언더스코어면
    '(현재 미생성)' 잔존을 놓쳤다.
    """
    doc = tmp_path / "CLAUDE.md"
    doc.write_text(f"메모리 `{_FIX_HYPHEN}.md` (현재 미생성) 참조\n", encoding="utf-8")
    monkeypatch.setattr(mod, "DOC_FILES", ["CLAUDE.md"])

    actual = {f"{_FIX_UNDER}.md"}  # 같은 슬러그, 다른 표기 / same slug, other separator style
    assert mod.collect_stale(tmp_path, actual) == [("CLAUDE.md", f"{_FIX_HYPHEN}.md")]


def test_resolve_finds_exact_slug_case_insensitively(tmp_path, monkeypatch):
    """양성 통제 — 대소문자만 다른 실제 디렉토리를 찾아낸다(Windows 드라이브 문자 변형)."""
    projects = tmp_path / "projects"
    (projects / "f--DEV-SCAManager" / "memory").mkdir(parents=True)
    monkeypatch.setattr(mod, "PROJECTS_ROOT", projects)
    monkeypatch.delenv("CLAUDE_PROJECT_MEMORY_DIR", raising=False)

    from pathlib import PureWindowsPath
    assert mod.resolve_memory_dir(PureWindowsPath(r"F:\DEV\SCAManager")) == \
        projects / "f--DEV-SCAManager" / "memory"


def test_resolve_returns_none_when_ambiguous(tmp_path, monkeypatch):
    """🔴 리포 이름이 같은 후보가 2개면 **추측하지 않는다** — 틀린 디렉토리를 검사하면 전건 오탐."""
    projects = tmp_path / "projects"
    for name in ("a--SCAManager", "b--SCAManager"):
        (projects / name / "memory").mkdir(parents=True)
    monkeypatch.setattr(mod, "PROJECTS_ROOT", projects)
    monkeypatch.delenv("CLAUDE_PROJECT_MEMORY_DIR", raising=False)

    from pathlib import PureWindowsPath
    assert mod.resolve_memory_dir(PureWindowsPath(r"Z:\elsewhere\SCAManager")) is None


# ── 표기 정규화 ─────────────────────────────────────────────────────────


def test_normalize_absorbs_separator_style():
    """🔴 문서는 하이픈, 파일은 언더스코어 — 정규화 없으면 전건 오탐/전건 미탐이 갈린다."""
    assert mod.normalize("feedback-test-patterns.md") == mod.normalize("feedback_test_patterns.md")


def test_normalize_is_not_constant():
    """대조군 — 정규화가 서로 다른 슬러그까지 같게 만들면 안 된다(공허한 통과 차단)."""
    assert mod.normalize("feedback-a.md") != mod.normalize("feedback-b.md")


# ── 참조 수집 ───────────────────────────────────────────────────────────


# 🔴 픽스처 슬러그는 **조립해서** 만든다 — 소스에 완성된 리터럴이 남으면
#   리포 전역 dangling 스캐너(`test_lint_gate_wiring`)가 이 파일 자신을 위반으로 잡는다(실측).
#   테스트가 자기 검사 대상이 되는 것을 피하되, 스캐너를 약화시키지는 않는다.
# Build fixture slugs from parts so no complete literal remains for the repo-wide scanner to flag.
_FIX_HYPHEN = "feedback-" + "some-thing"
_FIX_UNDER = "feedback_" + "some_thing"


def test_collect_picks_up_wiki_links(tmp_path, monkeypatch):
    """🔴 이중 대괄호 wiki-link 는 현행 메모리 규약인데 이전 판은 통째로 무시했다."""
    doc = tmp_path / "CLAUDE.md"
    doc.write_text(f"본문 [[{_FIX_HYPHEN}]] 참조\n", encoding="utf-8")
    monkeypatch.setattr(mod, "DOC_FILES", ["CLAUDE.md"])
    assert f"{_FIX_HYPHEN}.md" in mod.collect_referenced(tmp_path)


def test_collect_picks_up_backtick_form(tmp_path, monkeypatch):
    """백틱 표기도 계속 인식 — 두 표기가 같은 키 공간에 들어간다."""
    doc = tmp_path / "CLAUDE.md"
    doc.write_text(f"메모리 `{_FIX_UNDER}.md` 참조\n", encoding="utf-8")
    monkeypatch.setattr(mod, "DOC_FILES", ["CLAUDE.md"])
    assert f"{_FIX_UNDER}.md" in mod.collect_referenced(tmp_path)


def test_collect_is_not_vacuous(tmp_path, monkeypatch):
    """🔴 대조군 — 참조가 없는 문서에서 빈 결과가 나오는가(항상-비어있음 탐지기 차단은 위 2건)."""
    doc = tmp_path / "CLAUDE.md"
    doc.write_text("메모리 언급이 전혀 없는 본문\n", encoding="utf-8")
    monkeypatch.setattr(mod, "DOC_FILES", ["CLAUDE.md"])
    assert mod.collect_referenced(tmp_path) == {}


# --- 스캔 범위 (2026-08-05 문서 감사 P2 — 3파일 → 처방적 표면 전체) ---


def test_scan_scope_covers_rules_and_runbooks():
    """🔴 `docs/workflow/**` 와 `docs/runbooks/**` 가 범위에 들어와야 한다.

    확대 전에는 3파일(전체 188 md 의 **1.6%**)만 봤다. 그 범위 밖에서 죽은 슬러그가
    생기면 가드가 **"✅ 전부 존재"** 를 인쇄한다 — 좁은 범위 위의 초록은 fail-open 이다.
    """
    files = set(mod.DOC_FILES)
    assert "CLAUDE.md" in files and "CLAUDE.md" in files
    assert any(f.startswith("docs/workflow/") for f in files), files
    assert any(f.startswith("docs/runbooks/") for f in files), files
    # 개수 하한을 두지 않는다 — 문서를 줄이면 red 가 되는 계약이라 축소를 막는다.
    assert files, "스캔 범위가 0개다 — 붕괴"


def test_scan_scope_excludes_point_in_time_records():
    """🔴 퇴역한 이력 트리는 스캔에 다시 넣지 않는다.

    그 트리는 디스크에 없다. 글롭에 되살리거나 리터럴로 넣으면 빈 분모를 채점한다.
    """
    for f in mod.DOC_FILES:
        assert "_archive" not in f, f"아카이브가 범위에 들어왔다: {f}"
        assert not f.endswith("cycle-history.md"), f"시점 기록이 범위에 들어왔다: {f}"


def test_scan_scope_is_derived_not_hardcoded(tmp_path):
    """범위가 **글롭 파생**임을 단언 — 새 workflow/runbook 이 자동 포함돼야 한다.

    하드코딩 목록이면 파일을 추가할 때마다 손으로 등재해야 하고, 빠뜨리면 조용히 무관측이다.
    """
    (tmp_path / "docs" / "workflow").mkdir(parents=True)
    (tmp_path / "docs" / "runbooks").mkdir(parents=True)
    (tmp_path / "docs" / "workflow" / "brandnew.md").write_text("x", encoding="utf-8")
    (tmp_path / "docs" / "runbooks" / "brandnew.md").write_text("x", encoding="utf-8")

    files = mod._doc_files(tmp_path)
    assert "docs/workflow/brandnew.md" in files, files
    assert "docs/runbooks/brandnew.md" in files, files


def test_doc_literals_do_not_include_retiring_ledgers():
    """원장 두 파일은 스캔 리터럴이 아니다 — 묶여 있으면 삭제가 범위를 조용히 줄인다."""
    assert "docs/backlog.md" not in mod._DOC_LITERALS
    assert "docs/cycle-history.md" not in mod._DOC_LITERALS


def test_doc_files_keeps_missing_literals(tmp_path):
    """부재 리터럴을 목록에서 빼면 스코프가 조용히 줄어든다.

    예전 판은 `(project_root / f).is_file()` 로 걸러 `docs/backlog.md` 가 없어도
    DOC_FILES 가 그 이름을 잊고, main() 의 부재 검사가 그 이름을 보지 못했다.
    """
    files = mod._doc_files(tmp_path)
    for lit in mod._DOC_LITERALS:
        assert lit in files, f"{lit} 이 부재인데 목록에서 빠졌다 — 조용한 범위 축소"


def test_main_fails_when_a_literal_doc_is_missing(tmp_path, monkeypatch, capsys):
    """리터럴 문서가 없으면 exit 1 — `.is_file()` 필터를 되돌려도 진입점에서 걸린다."""
    memory = tmp_path / "mem"
    memory.mkdir()
    monkeypatch.setenv("CLAUDE_PROJECT_MEMORY_DIR", str(memory))
    monkeypatch.setattr(mod, "PROJECTS_ROOT", tmp_path)
    monkeypatch.setattr(mod, "DOC_FILES", list(mod._DOC_LITERALS))
    assert mod.main(project_root=tmp_path) == 1
    err = capsys.readouterr().err
    assert any(lit in err for lit in mod._DOC_LITERALS), err


# ─── 스캔 범위 — 「안 쟀음」은 초록이 아니다 ───────────────────────────────────
#
# 🔴 실측. 이 가드는 `CLAUDE.md` + `docs/workflow/*.md` + `docs/runbooks/*.md`
# **13파일**만 봤고, 그 범위에서 슬러그 인용이 0건이라 스스로
# 「이 축은 아무것도 검증하지 않았다」고 보고했다(정직하다).
#
# 그런데 **범위 밖에 진짜 인용이 4건 있었고, 그중 1건이 dangling** 이었다:
#
#     .github/dependabot.yml:9   feedback-log-first-debugging.md    -> 파일 없음 (이 PR 이 교체)
#     tests/unit/migrations/test_alembic_url_interpolation.py:108    -> 존재
#     tests/unit/scripts/test_generate_illustrations.py:5            -> 존재
#     tests/unit/scripts/test_plans_are_not_executable.py:99         -> 존재
#
# 이 파일 자신의 헤더가 「범위가 좁으면 …가드가 "✅ 전부 존재" 를 인쇄한다 —
# 빈/좁은 범위 위의 초록은 fail-open 이다」라고 적고 있었는데, 바로 그 상태였다.
# 감사 B7(#1519) — B3(stdout 가드 비재귀)와 같은 클래스다.


def _repo_root():
    from pathlib import Path  # noqa: PLC0415

    return Path(__file__).resolve().parents[3]


def test_scan_scope_covers_where_slugs_actually_appear():
    """🔴 슬러그 인용이 실제로 있는 파일이 스캔 범위 안인가.

    밖이면 그 인용이 dangling 이어도 가드가 초록을 인쇄한다.
    """
    import io  # noqa: PLC0415

    import scripts.check_memory_refs as M  # noqa: PLC0415

    root = _repo_root()
    scope = set(M._doc_files(root))  # noqa: SLF001

    cited = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in (".md", ".py", ".yml", ".yaml", ".json"):
            continue
        rel = path.relative_to(root).as_posix()
        if any(x in rel for x in (".git/", "node_modules", "__pycache__", "worktrees", "venv")):
            continue
        try:
            text = io.open(path, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        if M.SLUG_PATTERN.search(text) or M.WIKI_PATTERN.search(text):
            cited.append(rel)

    # 가드 자신은 정규식 정의를 담고 있어 제외한다(자기 참조).
    cited = [c for c in cited if c != "scripts/check_memory_refs.py"]
    outside = sorted(c for c in cited if c not in scope)
    assert not outside, (
        f"슬러그를 인용하는데 스캔 범위 밖인 파일: {outside} — "
        "그 인용이 dangling 이어도 가드가 초록을 인쇄한다. _DOC_GLOBS 를 넓혀라"
    )


def test_the_scope_is_not_empty_of_subjects():
    """🔴 스캔 범위에 슬러그 인용이 **하나라도** 있어야 한다.

    0건이면 이 가드는 아무것도 검증하지 않는다 — 초록이 아니라 '안 쟀음' 이다.
    가드 자신이 그렇게 보고하지만, 그 상태가 영원히 조용히 유지되는 것을 막는다.
    """
    import io  # noqa: PLC0415

    import scripts.check_memory_refs as M  # noqa: PLC0415

    root = _repo_root()
    total = 0
    for rel in M._doc_files(root):  # noqa: SLF001
        path = root / rel
        if not path.is_file():
            continue
        text = io.open(path, encoding="utf-8", errors="ignore").read()
        total += len(M.SLUG_PATTERN.findall(text)) + len(M.WIKI_PATTERN.findall(text))
    assert total > 0, (
        "스캔 범위 안에 슬러그 인용이 0건이다 — 이 가드는 아무것도 검증하지 않는다. "
        "참조를 되살리거나 범위를 넓히거나, 축을 폐기하라"
    )
