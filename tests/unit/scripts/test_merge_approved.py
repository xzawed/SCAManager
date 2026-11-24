"""사용자가 승인한 head 로만 머지하는 스크립트 (회고 원장 L06).
Merge only at the head the user approved (retro ledger L06).

판정(`decide`)은 표로 돌리고 — 막는 값과 통과하는 값을 같은 표에 심는다 — `main` 은 가짜 실행기로 «조건이 하나라도
안 맞으면 댓글도 머지도 나가지 않는다» 와 «맞으면 승인 기록 댓글 뒤 승인한 head 로 정확히 한 번 머지한다» 를 잰다.
실제 gh · git 은 부르지 않는다.
decide() is table-tested; main() is wired against a fake runner (no real gh/git calls).
"""
import json
import sys

import pytest

from scripts import merge_approved as ma

_HEAD = "9c01d5c2" + "0" * 32
_TREE = "1" * 40
_MERGE = "f" * 40
_REQUIRED = ["E2E (Playwright)", "pytest + Codecov + SonarCloud"]
_GREEN = [{"name": "E2E (Playwright)", "bucket": "pass"},
          {"name": "pytest + Codecov + SonarCloud", "bucket": "pass"},
          {"name": "codecov/patch", "bucket": "skipping"}]


def _state(**over):
    state = {
        "state": "OPEN", "draft": False, "base": "main", "head": _HEAD,
        "files": ["src/services/x.py", "tests/unit/test_x.py"], "changed_files": 2,
        "checks": [dict(c) for c in _GREEN], "required": list(_REQUIRED),
        "head_tree": _TREE, "merged_tree": _TREE,
    }
    state.update(over)
    return state


def _decide(state, *, head=_HEAD[:8], approval="머지 승인합니다", visual=None, tested_tree=None):
    return ma.decide(state, head=head, approval=approval, visual=visual, tested_tree=tested_tree)


def _with_bucket(name, bucket):
    return [dict(c, bucket=bucket) if c["name"] == name else dict(c) for c in _GREEN]


# --- 1. 판정 — 머지해도 되는 때 ---------------------------------------------------


def test_approved_head_with_green_checks_may_merge():
    """승인한 head(짧은 SHA) = 지금 head · 검사 전부 통과 · 시각 변경 없음 · 합친 트리 = 시험한 트리."""
    assert _decide(_state()) == []


def test_full_sha_head_is_accepted():
    assert _decide(_state(), head=_HEAD) == []


def test_combined_tree_tested_separately_may_merge():
    """main 이 앞서 합친 트리가 head 트리와 다를 때 — 그 합친 트리를 돌렸으면(`--tested-tree`) 머지한다."""
    combined = "2" * 40
    assert _decide(_state(merged_tree=combined), tested_tree=combined) == []


# --- 2. 판정 — 막아야 하는 때 (값 하나만 바꾼다 — 나머지는 위의 통과 상태) --------------


@pytest.mark.parametrize("over,kwargs,needle", [
    # 승인 뒤 push — 승인은 그 순간의 head 에 묶인다
    ({"head": "a" * 40}, {}, "승인 뒤 바뀌었다"),
    ({"head": ""}, {}, "승인 뒤 바뀌었다"),
    # 닫힘 · 머지됨 · 초안 · 초안 여부를 못 읽음 · base 가 main 이 아님
    ({"state": "MERGED"}, {}, "열린 비초안"),
    ({"state": "CLOSED"}, {}, "열린 비초안"),
    ({"draft": True}, {}, "열린 비초안"),
    ({"draft": None}, {}, "열린 비초안"),
    ({"base": "develop"}, {}, "base"),
    # 검사 — 진행 중 · 실패 · 취소 · 비어 있음 · 못 읽음 · required 가 통과 목록에 없음 · required 목록을 못 읽음
    ({"checks": _with_bucket("E2E (Playwright)", "pending")}, {}, "pending"),
    ({"checks": _with_bucket("codecov/patch", "fail")}, {}, "fail"),
    ({"checks": _with_bucket("E2E (Playwright)", "cancel")}, {}, "cancel"),
    ({"checks": []}, {}, "하나도"),
    ({"checks": None}, {}, "하나도"),
    ({"checks": {"name": "E2E (Playwright)", "bucket": "pass"}}, {}, "하나도"),
    ({"checks": [*_GREEN, "E2E (Playwright)"]}, {}, "꼴을 못 읽었다"),
    ({"checks": [c for c in _GREEN if c["name"] != "E2E (Playwright)"]}, {}, "required 검사 «E2E"),
    ({"required": []}, {}, "required 검사 목록"),
    ({"required": None}, {}, "required 검사 목록"),
    # 승인 발화 · head 꼴
    ({}, {"approval": "   "}, "승인 발화"),
    ({}, {"head": "9c01d5"}, "16진수"),
    ({}, {"head": "zzzzzzzz"}, "16진수"),
    ({}, {"head": ""}, "16진수"),
    # 트리 — 합친 트리 ≠ 시험한 트리 · 충돌 · 시험한 트리를 모름
    ({"merged_tree": "2" * 40}, {}, "합친 트리"),
    ({"merged_tree": ""}, {}, "(충돌)"),
    ({"head_tree": ""}, {}, "시험한 트리를 모른다"),
    ({}, {"tested_tree": "2" * 40}, "합친 트리"),
    # 끝 줄바꿈 — `$` 는 그 앞에서도 맞는다(Grok da1b75aa 반례 그대로)
    ({"merged_tree": "a" * 40 + "\n"}, {"tested_tree": "a" * 40 + "\n"}, "시험한 트리를 모른다"),
    ({}, {"head": _HEAD[:8] + "\n"}, "16진수"),
])
def test_refuses_when_one_condition_fails(over, kwargs, needle):
    problems = _decide(_state(**over), **kwargs)
    assert problems, f"막아야 하는데 통과했다: {over} {kwargs}"
    assert any(needle in p for p in problems), problems


# --- 3. 시각 변경 — 위임으로 덮지 않는다 ------------------------------------------------


# witness-corpus: 시각 결함 사고 PR 이 실제로 바꾼 화면 파일 — #1791(375px 줄바꿈 · 원인은 한국어 문구 길이) · #1792 · #1755 · #1795
_INCIDENT_VISUAL_PATHS = [
    "src/i18n/translations/ko.json",   # #1791 — 머지 뒤 처음 본 375px 줄바꿈의 원인이 문구 길이
    "src/templates/dashboard.html",    # #1791
    "src/static/css/components.css",   # #1792 — 그 줄바꿈의 수정
    "src/templates/overview.html",     # #1755
    "src/templates/settings.html",     # #1795 — 승인 뒤 더한 시각 변경
]


@pytest.mark.parametrize("path", _INCIDENT_VISUAL_PATHS)
def test_visual_change_needs_the_users_visual_confirmation(path):
    state = _state(files=["src/services/x.py", path], changed_files=2)
    assert any("시각 변경" in p for p in _decide(state)), "화면 확인 발화 없이 시각 변경 PR 이 통과했다"
    assert _decide(state, visual="화면 확인했습니다") == []
    assert any("시각 변경" in p for p in _decide(state, visual="  ")), "빈 발화가 화면 확인으로 읽혔다"


# witness-corpus: 화면 데이터를 바꾸지만 시각 변경으로 치지 않는 경계 — 라우트 로직(#1755 · #1840 이 실제로 바꿨다)
_UI_LOGIC_PATHS = ["src/ui/routes/overview.py", "src/ui/error_page.py"]


@pytest.mark.parametrize("path", _UI_LOGIC_PATHS)
def test_ui_route_logic_is_the_visual_boundary(path):
    """데이터 로직만 바꾼 PR 은 화면 확인을 요구하지 않는다 — 넓히려면 이 경계를 일부러 옮긴다."""
    assert _decide(_state(files=[path], changed_files=1)) == []


def test_visual_prefix_is_anchored_to_the_src_directories():
    """`docs/templates/` 처럼 같은 이름의 다른 폴더는 시각 변경이 아니다 — 앞에서부터 맞춘다."""
    state = _state(files=["docs/templates/pr.md", "tests/unit/static/x.py"], changed_files=2)
    assert _decide(state) == []


@pytest.mark.parametrize("changed", [150, None, "2", True])
def test_unreadable_file_list_counts_as_a_visual_change(changed):
    """바꾼 파일 수와 읽은 목록이 다르거나 수를 못 읽으면 — 못 잰 것은 시각 변경으로 본다.
    목록이 한 개라 `True == 1` 이 «다 읽음» 으로 새는지도 함께 본다(bool 은 int 가 아니다)."""
    state = _state(changed_files=changed, files=["src/services/x.py"])
    assert any("다 못 읽었다" in p for p in _decide(state)), changed
    assert _decide(state, visual="화면 확인했습니다") == []


# --- 4. main — 가짜 실행기 ---------------------------------------------------------


class _Fake:
    """명령 앞머리로 답을 고르는 가짜 실행기 — 부른 명령을 모두 적는다 / a fake runner that records every call."""

    def __init__(self, *, view=None, checks=None, merged_tree=_TREE, merge_commit_tree=_TREE, fail=None):
        self.view = view or {"state": "OPEN", "isDraft": False, "baseRefName": "main", "headRefOid": _HEAD,
                             "changedFiles": 1, "files": [{"path": "src/services/x.py"}]}
        self.checks = _GREEN if checks is None else checks
        self.merged_tree, self.merge_commit_tree, self.fail = merged_tree, merge_commit_tree, fail
        self.calls = []

    def __call__(self, args, ok_codes=frozenset({0})):
        self.calls.append(list(args))
        if self.fail and args[:3] == self.fail:
            raise ma.CommandFailed(args, 1)
        head = args[:3]
        if head == ["gh", "pr", "view"]:
            return json.dumps({"mergeCommit": {"oid": _MERGE}} if args[-1] == "mergeCommit" else self.view)
        if head == ["gh", "pr", "checks"]:
            assert 8 in ok_codes, "진행 중(8)일 때도 JSON 을 읽어야 한다"
            return json.dumps(self.checks)
        if head[:2] == ["gh", "api"]:
            return json.dumps(_REQUIRED)
        if head == ["git", "rev-parse", f"{_HEAD}^{{tree}}"]:
            return _TREE + "\n"
        if head == ["git", "rev-parse", f"{_MERGE}^{{tree}}"]:
            return self.merge_commit_tree + "\n"
        if head == ["git", "merge-tree", "--write-tree"]:
            return self.merged_tree + "\n"
        return ""

    def sent(self, verb):
        return [c for c in self.calls if c[:3] == ["gh", "pr", verb]]


def _main(fake, *extra, approval="머지 승인합니다"):
    lines = []
    code = ma.main(["1836", "--head", _HEAD[:8], "--approval", approval, *extra], run=fake, out=lines.append)
    return code, "\n".join(lines)


@pytest.mark.parametrize(("files", "needle"), [
    ([".claude/settings.json", "src/x.py"], "세션을 다시 시작"),
    ([".claude/hooks/block_credential_dump.py"], "git pull --ff-only"),
    (["scripts/check_main_red.py"], "git pull --ff-only"),
])
def test_after_merge_notes_point_at_the_main_checkout(files, needle):
    """🔴 훅 표면을 바꾼 머지는 주 체크아웃을 당겨야 적용된다 — 11-15~21 10 PR 이 4~6일 꺼져 있었다(원장 #1917 M01)."""
    notes = ma.after_merge_notes(files)
    assert len(notes) == 1 and needle in notes[0]


# witness-corpus: 11-15~21 창에서 실제로 바뀐 경로 — 주 체크아웃이 낡아 꺼져 있던 훅 표면(원장 #1917 P1-2 증거 diff)과 같은 창의 세션 무관 경로(CI · 운영 이미지 · 앱 · 문서)
_WINDOW_PATHS = [
    (".claude/hooks/block_credential_dump.py", True),
    (".claude/workflows/retrospective.mjs", True),
    (".claude/hooks/posttool_pytest_smoke.py", True),
    ("scripts/retro_scope.py", True),
    ("CLAUDE.md", True),
    ("requirements-semgrep.txt", False),
    ("src/config.py", False),
    (".github/workflows/ci.yml", False),
    ("docs/workflow/verify.md", False),
]


@pytest.mark.parametrize(("path", "needs_note"), _WINDOW_PATHS)
def test_window_paths_get_a_note_exactly_when_they_feed_the_session(path, needs_note):
    """🔴 경계를 사건 쪽에서 잰다 — 세션에 먹히는 경로는 안내가 나오고, 같은 창의 세션 무관 경로는 조용하다."""
    assert bool(ma.after_merge_notes([path])) is needs_note, path


def test_claude_md_needs_a_restart_not_only_a_pull():
    """CLAUDE.md 는 세션 시작 때 읽힌다 — 당기기만으로는 지금 세션에 안 들어온다."""
    assert "세션을 다시 시작" in ma.after_merge_notes(["CLAUDE.md"])[0]


def test_after_merge_notes_are_silent_outside_the_hook_surface():
    """부정 통제 — 앱 · 문서만 바꾼 머지는 주 체크아웃을 당길 이유가 없다(소음이 되면 아무도 안 읽는다)."""
    assert ma.after_merge_notes(["src/services/x.py", "docs/workflow/verify.md", "tests/unit/scripts/test_x.py"]) == []


def test_main_prints_the_restart_note_after_merging_a_hook_registration_change():
    fake = _Fake(view={"state": "OPEN", "isDraft": False, "baseRefName": "main", "headRefOid": _HEAD,
                       "changedFiles": 1, "files": [{"path": ".claude/settings.json"}]})
    code, out = _main(fake)
    assert code == 0, out
    assert out.index("✅") < out.index("세션을 다시 시작"), "머지 성공 줄 뒤에 와야 한다"


def test_main_comments_then_merges_once_at_the_approved_head():
    fake = _Fake()
    code, out = _main(fake)
    assert code == 0, out
    comments, merges = fake.sent("comment"), fake.sent("merge")
    assert len(comments) == 1 and len(merges) == 1, fake.calls
    assert fake.calls.index(comments[0]) < fake.calls.index(merges[0]), "승인 기록보다 머지가 먼저 나갔다"
    assert merges[0][merges[0].index("--match-head-commit") + 1] == _HEAD, "승인한 head 전체로 묶지 않았다"
    assert "--squash" in merges[0]
    body = comments[0][comments[0].index("--body") + 1]
    assert "«머지 승인합니다»" in body and _HEAD in body and "시각 변경 없음" in body


@pytest.mark.parametrize("fake_kwargs", [
    {"view": {"state": "OPEN", "isDraft": False, "baseRefName": "main", "headRefOid": "a" * 40,
              "changedFiles": 1, "files": [{"path": "src/services/x.py"}]}},
    {"checks": _with_bucket("E2E (Playwright)", "pending")},
    {"view": {"state": "OPEN", "isDraft": False, "baseRefName": "main", "headRefOid": _HEAD,
              "changedFiles": 1, "files": [{"path": "src/templates/base.html"}]}},
    {"merged_tree": "2" * 40},
])
def test_main_sends_nothing_when_a_condition_fails(fake_kwargs):
    fake = _Fake(**fake_kwargs)
    code, out = _main(fake)
    assert code == 1, out
    assert not fake.sent("comment") and not fake.sent("merge"), fake.calls


def test_merge_tree_conflict_refuses():
    """merge-tree 가 충돌(종료 1)이면 합친 트리가 없다 — 막는다."""
    fake = _Fake(fail=["git", "merge-tree", "--write-tree"])
    code, out = _main(fake)
    assert code == 1 and "(충돌)" in out, out
    assert not fake.sent("merge")


def test_check_mode_sends_nothing():
    fake = _Fake()
    code, out = _main(fake, "--check")
    assert code == 0, out
    assert not fake.sent("comment") and not fake.sent("merge"), fake.calls


def test_unreadable_facts_refuse_before_anything_is_sent():
    fake = _Fake(fail=["gh", "pr", "view"])
    code, out = _main(fake)
    assert code == 2, out
    assert not fake.sent("comment") and not fake.sent("merge")


def test_merge_commit_tree_mismatch_is_reported_loudly():
    fake = _Fake(merge_commit_tree="3" * 40)
    code, out = _main(fake)
    assert code == 3 and "≠ 시험한 트리" in out, out


def test_visual_confirmation_is_recorded_in_the_comment():
    view = {"state": "OPEN", "isDraft": False, "baseRefName": "main", "headRefOid": _HEAD,
            "changedFiles": 1, "files": [{"path": "src/templates/base.html"}]}
    fake = _Fake(view=view)
    code, out = _main(fake, "--visual", "스크린샷 확인했습니다")
    assert code == 0, out
    body = fake.sent("comment")[0][fake.sent("comment")[0].index("--body") + 1]
    assert "화면 확인: «스크린샷 확인했습니다»" in body


# --- 5. 반례 코퍼스 — gh 문서가 적은 값 중 검사 목록 밖의 것 ------------------------------------

# witness-corpus: gh pr checks --help 가 적은 bucket 값 중 통과가 아닌 것 — 머지를 막아야 한다
_GH_NOT_PASSED_BUCKETS = ["fail", "pending", "cancel"]


@pytest.mark.parametrize("bucket", _GH_NOT_PASSED_BUCKETS)
def test_gh_documented_non_passing_buckets_refuse(bucket):
    assert _decide(_state(checks=_with_bucket("E2E (Playwright)", bucket))) == [
        f"검사 «E2E (Playwright)» = {bucket}", "required 검사 «E2E (Playwright)» 가 통과 목록에 없다"]


# witness-corpus: gh help exit-codes 의 코드 중 JSON 을 믿을 수 없는 것 — 2 취소 · 4 인증 필요
_GH_UNTRUSTED_EXIT_CODES = [2, 4]


@pytest.mark.parametrize("code", _GH_UNTRUSTED_EXIT_CODES)
def test_gh_exit_codes_without_trustworthy_json_raise(code):
    probe = [sys.executable, "-c", f"import sys; print('[]'); sys.exit({code})"]
    with pytest.raises(ma.CommandFailed):
        ma._run(probe, ma._CHECKS_EXIT_OK)  # noqa: SLF001


# --- 6. 실행기 — 종료 코드 -------------------------------------------------------------


def test_run_accepts_listed_exit_codes_and_rejects_others():
    """gh pr checks 는 진행 중이면 8 로 끝나도 JSON 을 찍는다 — 허용한 코드만 받고 나머지는 실패로."""
    probe = [sys.executable, "-c", "import sys; print('[]'); sys.exit(8)"]
    assert ma._run(probe, frozenset({0, 1, 8})).strip() == "[]"  # noqa: SLF001
    with pytest.raises(ma.CommandFailed):
        ma._run(probe)  # noqa: SLF001
