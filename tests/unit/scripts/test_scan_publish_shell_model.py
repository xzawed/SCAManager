"""게시 전 검사의 셸 모형 — 같은 명령이 다시 만든 본문 · 다시 묶은 변수 · 읽기만 하는 gh · gh 없는 heredoc · `$(gh …)` ·
거부 기록 (원장 #1940 M03 P1-12 · P1-13 · P2-12 · P2-13 · P2-14 · P2-15).
The publish scan's shell model: bodies rewritten in the same command, rebound variables, read-only gh, gh-less heredocs,
`$(gh …)` and the denial record.

검사는 명령이 돌기 «전» 의 본문 파일을 잰다. 그래서 같은 명령 안에서 gh 앞에 파일을 쓰거나 변수를 다시 묶을 수 있는 명령이
돌면 그 gh 의 본문 파일 · `<` 파일은 «못 잰 것» 이다 — 본문 파일을 만드는 명령과 게시를 나눠 부르게 한다. 파일을 쓰지 않는
흔한 명령(`git push` · `echo` · `test` · `cd`)은 그대로 둔다(#1935 가 고친 오탐을 되살리지 않는다).
"""
import json

import pytest

from tests.unit.scripts.test_scan_publish import _PLANTED, _denied, _hook, _reason

_EMAIL_TEXT = _PLANTED["email"]


@pytest.fixture
def bodies(tmp_path):
    """깨끗한 본문 · 꼴이 든 본문 · 이름 목록 파일 / a clean body, a dirty body and a names file."""
    (tmp_path / "clean.md").write_text("clean body\n", encoding="utf-8")
    (tmp_path / "dirty.md").write_text(_EMAIL_TEXT + "\n", encoding="utf-8")
    (tmp_path / "names.txt").write_text("dirty.md\n", encoding="utf-8")
    return tmp_path


# --- 1. 같은 명령이 본문을 다시 만든 뒤 게시 (P1-12) -----------------------------------------------------------

_REWRITE_THEN_POST = [
    pytest.param("printf 'x' > clean.md && gh pr comment 1 --body-file clean.md", id="printf-redirect"),
    pytest.param("py -3 gen.py > clean.md; gh pr comment 1 --body-file clean.md", id="script-output"),
    pytest.param("cp dirty.md clean.md && gh pr comment 1 --body-file clean.md", id="copy-over"),
    pytest.param("git show HEAD:README.md > clean.md && gh pr comment 1 --body-file clean.md", id="git-show-redirect"),
    pytest.param("tee clean.md < dirty.md > /dev/null; gh pr comment 1 --body-file clean.md", id="tee"),
    pytest.param("sed -i 's/clean/x/' clean.md && gh pr comment 1 -F clean.md", id="sed-in-place"),
    pytest.param("cp dirty.md clean.md && gh pr comment 1 --body-file - < clean.md", id="stdin-file"),
    pytest.param("git checkout HEAD -- clean.md && gh pr comment 1 --body-file clean.md", id="git-checkout"),
]


@pytest.mark.parametrize("command", _REWRITE_THEN_POST)
def test_a_body_rewritten_in_the_same_command_is_not_measured(command, bodies, monkeypatch, capsys):
    """🔴 gh 앞에서 파일을 바꿀 수 있는 명령이 돌면, 검사가 읽은 것은 옛 본문이다 — 못 잰 것으로 막고 나눠 부르라고 알린다."""
    result = _hook(monkeypatch, capsys, command, bodies)
    assert _denied(result), command
    assert "나눠" in _reason(result), _reason(result)


@pytest.mark.parametrize("between", [
    pytest.param("git push -u origin fix/x && ", id="git-push"),
    pytest.param("git status --short; ", id="git-status"),
    pytest.param("echo done && ", id="echo"),
    pytest.param("test -f clean.md && ", id="test-f"),
    pytest.param("cd . && ", id="cd"),
    pytest.param("echo hi 2>/dev/null && ", id="stderr-to-devnull"),
    pytest.param("if test -f clean.md; then ", id="if-test"),
])
def test_commands_that_write_no_file_keep_the_body_measurable(between, bodies, monkeypatch, capsys):
    """대조군 — 파일을 쓰지 않는 흔한 명령 뒤의 게시는 미리 만든 본문을 그대로 잰다(깨끗하면 통과 · 꼴이면 막힘)."""
    assert _hook(monkeypatch, capsys, f"{between}gh pr comment 1 --body-file clean.md", bodies) is None
    result = _hook(monkeypatch, capsys, f"{between}gh pr comment 1 --body-file dirty.md", bodies)
    assert _denied(result) and "email 1" in _reason(result), result


# --- 2. 사이 명령이 변수를 다시 묶는 꼴 (P1-13) ------------------------------------------------------------------

_REBIND_THEN_POST = [
    pytest.param('S=clean.md; export S=dirty.md; gh pr comment 1 --body-file "$S"', id="export"),
    pytest.param('S=clean.md; declare S=dirty.md; gh pr comment 1 --body-file "$S"', id="declare"),
    pytest.param('S=clean.md; read S < names.txt; gh pr comment 1 --body-file "$S"', id="read"),
    pytest.param("S=clean.md; printf -v S '%s' dirty.md; gh pr comment 1 --body-file \"$S\"", id="printf-v"),
    pytest.param('S=clean.md; for S in dirty.md; do gh pr comment 1 --body-file "$S"; done', id="for-loop"),
    pytest.param('S=clean.md; mapfile -t S < names.txt; gh pr comment 1 --body-file "$S"', id="mapfile"),
]


@pytest.mark.parametrize("command", _REBIND_THEN_POST)
def test_a_path_variable_rebound_in_between_is_not_measured(command, bodies, monkeypatch, capsys):
    """🔴 대입 뒤 사이 명령이 그 변수를 다시 묶으면 검사가 푼 경로는 옛 경로다 — 못 잰 것으로 막는다."""
    assert _denied(_hook(monkeypatch, capsys, command, bodies)), command


# --- 3. 아무것도 게시하지 않는 gh · gh 없는 heredoc (P2-12 · P2-13) ---------------------------------------------

# witness-corpus: 게시하지 않는 gh 읽기 명령 — 글자에 주소 꼴이 있어도 공개 글이 생기지 않는다(쓰기 하위 명령 밖)
_READ_ONLY_GH = [
    f"gh pr view 1 --json body --jq '.body | test(\"{_EMAIL_TEXT}\")'",
    f"gh issue list --search '{_EMAIL_TEXT}' --json number",
    f"gh api repos/xzawed/SCAManager/issues --jq '.[] | select(.body | contains(\"{_EMAIL_TEXT}\")) | .number'",
    f"gh run list --json headSha --jq '.[] | select(.headSha == \"{_EMAIL_TEXT}\")'",
]


@pytest.mark.parametrize("command", _READ_ONLY_GH)
def test_a_read_only_gh_command_is_not_blocked_for_its_text(command, bodies, monkeypatch, capsys):
    """읽기만 하는 gh 는 게시가 아니다 — 명령 글자의 꼴로 막지 않는다(P2-12)."""
    assert _hook(monkeypatch, capsys, command, bodies) is None, command


@pytest.mark.parametrize("command", [
    pytest.param(f"gh issue comment 1 --body '{_EMAIL_TEXT}'", id="comment-body"),
    pytest.param(f"gh api repos/x/y/issues/1/comments -f body='{_EMAIL_TEXT}'", id="api-field-write"),
    pytest.param(f"gh label create bug --description '{_EMAIL_TEXT}'", id="unmodelled-write-keeps-text-scan"),
])
def test_posting_gh_commands_are_still_scanned(command, bodies, monkeypatch, capsys):
    """대조군 — 게시하는(또는 쓰기인지 모르는) gh 는 명령 글자를 그대로 잰다."""
    assert _denied(_hook(monkeypatch, capsys, command, bodies)), command


def test_a_heredoc_command_without_gh_is_not_a_publish(bodies, monkeypatch, capsys):
    """gh 가 없는 명령의 heredoc 본문은 게시될 글이 아니다(P2-13) — gh 가 든 heredoc 게시는 그대로 잰다(대조군)."""
    local = "py -3 - <<'EOF'\nprint('" + _EMAIL_TEXT + "')\nEOF"
    assert _hook(monkeypatch, capsys, local, bodies) is None
    posting = "gh issue comment 1 --body-file - <<'EOF'\n" + _EMAIL_TEXT + "\nEOF"
    assert _denied(_hook(monkeypatch, capsys, posting, bodies))


# --- 4. `$(gh …)` 의 끝 (P2-15) ----------------------------------------------------------------------------------

@pytest.mark.parametrize("command", [
    pytest.param('echo "$(gh pr view 1 --json title -q .title)"', id="double-quoted-substitution"),
    pytest.param("N=$(gh pr view 1 --json number -q .number); echo $N", id="assignment-substitution"),
    pytest.param('git log -1 --format=%s "$(gh pr view 1 --json headRefName -q .headRefName)"', id="argument-substitution"),
])
def test_a_gh_read_inside_command_substitution_is_not_blocked(command, bodies, monkeypatch, capsys):
    """🔴 `$(gh …)` 의 닫는 괄호 · 바깥 큰따옴표를 gh 인자로 읽어 정직한 읽기가 막혔다 — 치환의 끝에서 자른다."""
    assert _hook(monkeypatch, capsys, command, bodies) is None, command


def test_a_gh_post_inside_command_substitution_is_still_scanned(bodies, monkeypatch, capsys):
    """대조군 — 치환 안의 게시도 잰다."""
    command = f"""echo "$(gh issue comment 1 --body '{_EMAIL_TEXT}')" """
    assert _denied(_hook(monkeypatch, capsys, command, bodies))


# --- 5. 거부 기록 (P2-14) ----------------------------------------------------------------------------------------

def test_a_denial_is_recorded_without_values(bodies, monkeypatch, capsys, tmp_path):
    """🔴 막은 게시는 값 없는 한 줄로 남는다(시각 · 종류 · 사유 범주 · 명령 sha256 · 길이) — 회고의 정밀도 계기가 본다."""
    log = tmp_path / "denials.jsonl"
    monkeypatch.setenv("SCAMANAGER_HOOK_LOG", str(log))
    command = f"gh issue comment 1 --body '{_EMAIL_TEXT}'"
    assert _denied(_hook(monkeypatch, capsys, command, bodies))
    records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1 and records[0]["kind"] == "publish", records
    assert {"ts", "kind", "reason", "sha256", "len"} <= set(records[0])
    assert _EMAIL_TEXT not in log.read_text(encoding="utf-8"), "기록에 값이 실렸다"


def test_a_pass_writes_no_record(bodies, monkeypatch, capsys, tmp_path):
    log = tmp_path / "denials.jsonl"
    monkeypatch.setenv("SCAMANAGER_HOOK_LOG", str(log))
    assert _hook(monkeypatch, capsys, "gh pr comment 1 --body-file clean.md", bodies) is None
    assert not log.exists()
