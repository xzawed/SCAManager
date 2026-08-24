"""심어지는 `install-hook.sh` **산출물**이 실제로 실행 가능한지 검사한다.

🔴 왜 부분문자열 assert 로는 안 되는가: `_INSTALL_HOOK_SH` 를 다루는 기존 테스트는 전부
「이 문자열이 들어 있는가」만 본다. 그래서 템플릿이 **논-raw** 삼중따옴표라 소스의 `\\n`·`\\"`
가 값에서 진짜 개행·맨 따옴표로 풀려도 전부 초록이었고, 그 상태로 사용자 리포에 커밋돼
pre-push 훅이 `set -euo pipefail` 아래에서 죽어 **push 를 막았다**.

`bash -n` 도 이 결함을 못 잡는다 — 파이썬 코드가 셸 이중따옴표 인자 안이라 bash 가 파싱하지
않기 때문이다. 그래서 **bash 가 하는 것과 같은 방식으로 인자를 풀어 `compile()`** 한다.

Substring asserts cannot see this class of defect, and `bash -n` cannot either (the Python lives
inside a double-quoted argument). Unquote the argument the way bash does, then compile it.
"""
import re
import shutil
import subprocess

import pytest

from src.github_client.repos import _INSTALL_HOOK_SH

BACKSLASH = chr(92)
DQUOTE = '"'
# bash 이중따옴표 안에서 백슬래시가 **실제로 이스케이프하는** 문자만.
# 그 외에는 백슬래시가 문자 그대로 남는다 (`\n` 은 개행이 아니라 두 글자다).
_BASH_DQ_ESCAPABLE = set(DQUOTE + BACKSLASH + "$`" + chr(10))


def _bash_dquote_unescape(raw: str) -> str:
    """bash 이중따옴표 규칙으로 인자 본문을 푼다."""
    out, i = [], 0
    while i < len(raw):
        ch = raw[i]
        if ch == BACKSLASH and i + 1 < len(raw):
            nxt = raw[i + 1]
            if nxt in _BASH_DQ_ESCAPABLE:
                if nxt != chr(10):  # 줄 이음은 두 글자 모두 사라진다
                    out.append(nxt)
                i += 2
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def _python_c_arguments(script: str) -> list[str]:
    """스크립트에서 `python3 -c "<...>"` 인자 본문을 전부 뽑아 bash 규칙으로 푼다."""
    args = []
    for m in re.finditer(r'python3 -c ' + DQUOTE, script):
        i = m.end()
        body = []
        while i < len(script):
            ch = script[i]
            if ch == BACKSLASH and i + 1 < len(script):
                body.append(script[i:i + 2])
                i += 2
                continue
            if ch == DQUOTE:
                break
            body.append(ch)
            i += 1
        args.append(_bash_dquote_unescape("".join(body)))
    return args


def test_script_contains_python_c_invocations():
    """계기 자기검증 — 인자를 하나도 못 뽑으면 아래 검사가 공허하다."""
    args = _python_c_arguments(_INSTALL_HOOK_SH)
    assert len(args) >= 5, f"python3 -c 인자를 {len(args)}개만 추출했다 — 추출기가 고장났다"


def test_extractor_detects_a_deliberately_broken_snippet():
    """계기 자기검증(반대 방향) — 깨진 코드를 넣으면 실제로 잡아야 한다."""
    broken = 'echo x\npython3 -c "x = (' + chr(39) + 'a' + chr(10) + chr(39) + '"\n'
    args = _python_c_arguments(broken)
    assert args, "고의 파손 샘플에서 인자 추출 실패"
    with pytest.raises(SyntaxError):
        compile(args[0], "<broken>", "exec")


def _compile_error(source: str, label: str) -> str | None:
    """컴파일 실패 사유를 문자열로 돌려준다(성공이면 None) — 테스트 본문을 단언 한 줄로 유지."""
    try:
        compile(source, label, "exec")
    except SyntaxError as exc:
        return f"{label} 이 컴파일되지 않는다: {exc.msg} (line {exc.lineno}) — {(exc.text or '').rstrip()!r}"
    return None


@pytest.mark.parametrize("index", range(len(_python_c_arguments(_INSTALL_HOOK_SH))))
def test_every_embedded_python_snippet_compiles(index):
    """🔴 emit 되는 각 `python3 -c` 스니펫이 실제로 컴파일돼야 한다.

    실패하면 사용자 머신에서 `SyntaxError` → non-zero exit → `set -e` → **push 차단**이다.
    """
    arg = _python_c_arguments(_INSTALL_HOOK_SH)[index]
    assert _compile_error(arg, f"python3 -c 블록 #{index + 1}") is None


def test_no_bare_double_quote_inside_python_c_arguments():
    """맨 `\"` 는 bash 이중따옴표 인자를 조기 종료시킨다 — emit 시 반드시 `\\\"` 여야 한다.

    추출기가 첫 비이스케이프 `\"` 에서 멈추므로, 인자가 `python3` 호출 한 줄보다 짧게
    잘렸다면 그 안에 맨 따옴표가 있었다는 뜻이다.
    """
    args = _python_c_arguments(_INSTALL_HOOK_SH)
    prompt_args = [a for a in args if "prompt = (" in a]
    assert prompt_args, "프롬프트 빌더 블록을 찾지 못했다 — 추출기 점검 필요"
    assert "file_feedbacks" in prompt_args[0], (
        "프롬프트 블록이 중간에서 잘렸다 — 맨 따옴표가 bash 인자를 조기 종료시킨다"
    )


def _bash_actually_runs() -> bool:
    """`shutil.which` 만으로는 부족하다 — Windows 에는 실행 불가한 WSL 릴레이 스텁이 잡힌다.

    which() alone is not enough: Windows can surface a WSL relay stub that cannot exec.
    """
    if shutil.which("bash") is None:
        return False
    try:
        return subprocess.run(
            ["bash", "-c", "exit 0"], capture_output=True, check=False, timeout=15
        ).returncode == 0
    except OSError:
        return False


@pytest.mark.skipif(
    not _bash_actually_runs(),
    reason="bash 를 실제로 실행할 수 없는 환경 — CI(Linux) 가 이 축을 담당한다",
)
def test_script_passes_bash_syntax_check(tmp_path):
    """`bash -n` 은 파이썬 스니펫을 못 보지만 셸 층의 회귀는 잡는다."""
    p = tmp_path / "install-hook.sh"
    p.write_text(_INSTALL_HOOK_SH, encoding="utf-8", newline=chr(10))
    r = subprocess.run(
        ["bash", "-n", str(p)], capture_output=True, text=True, check=False, timeout=30
    )
    assert r.returncode == 0, f"bash -n 실패: {r.stderr}"


def test_prompt_snippet_has_no_literal_newline_inside_string_literal():
    """프롬프트 빌더가 여러 줄로 끊기지 않았는지 — `\\n` 이 진짜 개행이 되면 여기서 잡힌다."""
    args = _python_c_arguments(_INSTALL_HOOK_SH)
    prompt = next(a for a in args if "prompt = (" in a)
    tree = compile(prompt, "<prompt>", "exec")  # 컴파일 자체가 1차 방어
    assert tree is not None
    # 프롬프트 문자열이 실제로 개행을 **포함**해야 한다(의도된 `\n` 이 살아 있는지).
    ns: dict = {}
    exec(  # noqa: S102 - 신뢰된 리포 소스, 컴파일 검증 후 실행
        compile(
            prompt.replace("os.environ.get(" + chr(39) + "SCA_COMMIT_MSG" + chr(39) + ", " + chr(39) + chr(39) + ")", repr("MSG"))
                  .replace("os.environ.get(" + chr(39) + "SCA_DIFF" + chr(39) + ", " + chr(39) + chr(39) + ")", repr("DIFF"))
                  .replace("sys.stdout.write(prompt)", "pass"),
            "<prompt-exec>",
            "exec",
        ),
        ns,
    )
    assert chr(10) in ns["prompt"], "프롬프트에 개행이 없다 — `\\n` 이 소실됐다"
    assert "MSG" in ns["prompt"], "커밋 메시지가 프롬프트에 실리지 않았다"
    assert "DIFF" in ns["prompt"], "diff 가 프롬프트에 실리지 않았다"


def test_stdin_derived_vars_use_default_expansion():
    """🔴 `set -u` 아래에서 `read` 의 리다이렉트가 실패하면 변수가 **미설정**으로 남는다.

    실측: stdin 이 비기만 하면 `read` 는 빈 문자열을 넣지만, `/dev/stdin` 자체가 없어
    리다이렉트가 실패하면 `read` 가 실행되지 않아 `unbound variable` 로 훅이 죽고
    pre-push non-zero → **push 차단**이 된다. 그래서 `${VAR:-}` 형태여야 한다.
    """
    for var in ("LOCAL_SHA", "REMOTE_SHA"):
        bare = '[ -n "${' + var + '}" ]'
        assert bare not in _INSTALL_HOOK_SH, (
            f"{var} 를 `:-` 없이 참조한다 — read 리다이렉트 실패 시 set -u 로 훅이 죽는다"
        )
        assert '[ -n "${' + var + ':-}" ]' in _INSTALL_HOOK_SH
