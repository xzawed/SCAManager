"""credential 훅 — find 가 찾은 파일을 읽게 넘기면, find 의 규칙으로 .env 를 집는지 본다 (회고 원장 R-3).

find 의 이름 패턴(`-name '*.env'`)에서 `*` 는 점 파일도 집고, find 는 아래 폴더까지 내려간다 — 경로 낱말의 Bash 점
규칙과 다르다(사용자 11-17 결정 «find 꼴만 조이고 닫기»).

계약: find 가 찾은 파일을 실행 술어(-exec · -execdir · -ok · -okdir)로 넘기거나, 이름만 다루는 명령이 아닌 뒤
단계로 넘길 때, 시작 경로 아래의 실제 .env 꼴 파일에 find 의 이름 · 경로 패턴을 find 처럼 대 보고 고르면 막는다.
이름만 내보내는 find · .env 와 무관한 패턴은 통과한다.
"""
import pytest

from tests.unit.hooks.test_block_credential_dump import _decide


@pytest.fixture(name="root_env")
def _root_env(tmp_path):
    """맨 위에 점 파일 .env 하나 · 보통 파일 하나."""
    (tmp_path / ".env").write_text("PLANT=1\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("x\n", encoding="utf-8")
    return tmp_path


@pytest.fixture(name="nested_env")
def _nested_env(tmp_path):
    """.env 꼴 파일이 아래 폴더에만 있다 — 맨 위 폴더만 대 보면 못 본다."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("X = 1\n", encoding="utf-8")
    (tmp_path / "nested" / "deep").mkdir(parents=True)
    (tmp_path / "nested" / "deep" / ".env.local").write_text("PLANT=2\n", encoding="utf-8")
    return tmp_path


_DENIED = [
    pytest.param("root_env", "find . -name '*.env' -exec cat {} +", id="star-matches-a-dot-file"),
    pytest.param("root_env", "find . -name '*.env' | xargs cat", id="names-fed-to-xargs"),
    pytest.param("root_env", "find . -iname '*.ENV' -print0 | xargs -0 cat", id="case-insensitive"),
    pytest.param("root_env", "find . -type f -exec grep KEY {} +", id="no-name-pattern-matches-everything"),
    pytest.param("root_env", "find . ! -name '*.md' -exec cat {} +", id="negated-pattern"),
    pytest.param("root_env", "find . -name '*.env' | while read f; do cat \"$f\"; done", id="names-into-a-loop"),
    pytest.param("nested_env", "find . -name '.env*' -exec cat {} +", id="only-in-a-subfolder"),
    pytest.param("nested_env", "find . -path '*/deep/*' -execdir cat {} +", id="path-pattern"),
]

_ALLOWED = [
    pytest.param("root_env", "find . -name '*.env'", id="names-only"),
    pytest.param("root_env", "find . -name '*.env' | wc -l", id="names-counted"),
    pytest.param("root_env", "find . -name '*.md' -exec grep -n TODO {} +", id="pattern-misses-dotenv"),
    pytest.param("root_env", "find . -name '*.md' | xargs wc -l", id="xargs-on-other-files"),
    pytest.param("nested_env", "find src -name '*' -exec cat {} +", id="start-path-without-dotenv"),
]


@pytest.mark.parametrize(("fixture", "command"), _DENIED)
def test_find_feeding_a_reader_with_a_dotenv_match_is_denied(request, fixture, command):
    """🔴 find 의 규칙으로 .env 꼴 파일을 집고, 그 파일을 읽게 넘기면 막는다."""
    decision, _ = _decide(command, cwd=request.getfixturevalue(fixture))
    assert decision == "deny", f"find 가 .env 를 읽게 넘기는데 통과했다: {command!r}"


@pytest.mark.parametrize(("fixture", "command"), _ALLOWED)
def test_find_that_cannot_hand_over_a_dotenv_passes(request, fixture, command):
    """이름만 내보내거나 .env 를 못 집는 find 는 통과한다 — 판정식 뒤집기의 반대편."""
    decision, reason = _decide(command, cwd=request.getfixturevalue(fixture))
    assert decision != "deny", f"find 가 .env 를 넘기지 않는데 막혔다: {command!r}\n{reason}"


# witness-corpus: 받은 이름을 글자로만 다루지만 «이름만 다루는 뒤 단계» 목록에 없는 명령 — 목록 밖은 막는 쪽이어야 한다
_UNLISTED_NAME_CONSUMERS = ("nl", "fold", "rev", "column", "paste")


@pytest.mark.parametrize("consumer", _UNLISTED_NAME_CONSUMERS)
def test_an_unlisted_consumer_after_a_matching_find_is_denied(root_env, consumer):
    """목록은 닫힌 허용 목록이다 — 목록 밖 뒤 단계는 읽을 수 있다고 보고 막는다(막는 쪽)."""
    decision, _ = _decide(f"find . -name '*.env' | {consumer}", cwd=root_env)
    assert decision == "deny", f"목록 밖 뒤 단계({consumer})를 이름만 다룬다고 봤다"
