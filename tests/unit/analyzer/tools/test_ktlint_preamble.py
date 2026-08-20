"""ktlint 로그 프리앰블 제거 — 어댑터가 전량 0건이던 결함 (2026-08-19).

## 사고

계약 3종의 `latest` 를 핀으로 바꾸며 신설한 실바이너리 통합 테스트가
**첫 CI 실행에서** 이것을 잡았다. 미래 위험이 아니라 지금 죽어 있었다.

ktlint 1.8.0 은 `--reporter=json` 인데도 stdout **앞에 WARN 로그를 붙인다**.
그리고 `tools/ktlint.py` 는 `raw.startswith("[")` 가 거짓이면 조용히 `[]` 를 반환했다 —
즉 **자동수정 가능한 위반이 있는 모든 Kotlin 파일에서 분석이 0건**이었고
그게 「깨끗함」으로 보였다. 계약 도구가 설치돼 있는데 아무것도 보고하지 않았다.

## 왜 별도 파일인가

`test_ktlint.py` 는 모듈을 `import src.analyzer.io.tools.ktlint` 형태로도 쓴다.
거기에 `from ... import json_array_payload` 를 더하면 **이중 import** 가 되어
`check_dual_import.py` 가 차단한다(CodeQL `py/import-and-import-from` 자초 방지).
"""
import json
import logging

from src.analyzer.io.tools.ktlint import _KtlintAnalyzer, json_array_payload

# 🔴 ktlint 1.8.0 은 `--reporter=json` 인데도 **stdout 앞에 WARN 로그를 붙인다.**
#    구판 어댑터는 `raw.startswith("[")` 가 거짓이면 조용히 `[]` 를 반환했다 —
#    즉 **자동수정 가능한 위반이 있는 모든 Kotlin 파일에서 분석이 0건**이었고
#    그게 「깨끗함」으로 보였다. 계약 도구가 설치돼 있는데 죽어 있었다.
#    통합 테스트(`tests/integration/test_contracted_analyzers_real_binary.py`)가
#    실바이너리로 이것을 잡았다.

_REAL_KTLINT_STDOUT = (
    "14:16:17.124 [main] WARN com.pinterest.ktlint.cli.internal.KtlintCommandLine -- "
    "Lint has found errors than can be autocorrected\n"
    "[\n"
    '    {\n'
    '        "file": "/tmp/Dirty.kt",\n'
    '        "errors": [\n'
    '            {\n'
    '                "line": 2,\n'
    '                "column": 19,\n'
    '                "message": "Unnecessary semicolon",\n'
    '                "rule": "standard:no-semi"\n'
    "            }\n"
    "        ]\n"
    "    }\n"
    "]"
)


class TestKtlintPreambleStripping:
    """실 출력에서 JSON 배열만 꺼내는가."""

    def test_real_output_with_a_log_preamble_is_parsed(self):
        """🔴 이 문자열은 **CI 실측 출력**이다 — 합성이 아니다."""
        payload = json_array_payload(_REAL_KTLINT_STDOUT)

        assert payload.startswith("["), f"배열을 못 꺼냈다: {payload[:80]!r}"
        data = json.loads(payload)
        assert data[0]["errors"][0]["rule"] == "standard:no-semi"

    def test_a_bracket_inside_the_log_line_is_not_mistaken_for_the_array(self):
        """🔴 `raw.index("[")` 로 고치면 로그 줄의 `[main]` 이 먼저 잡힌다.

        그 경로로 가면 `json.loads` 가 터지고 어댑터의 `except` 가 다시 0건을 낸다 —
        증상이 같아서 고쳤다고 착각하게 된다. 줄 **맨 앞**의 `[` 만 배열 시작이다.
        """
        payload = json_array_payload("12:00 [main] WARN something\n[]")

        assert payload == "[]", f"로그 줄의 `[main]` 을 배열로 오인했다: {payload[:60]!r}"

    def test_no_array_yields_empty_string_not_a_crash(self):
        """배열이 아예 없으면 빈 문자열 — 호출부가 조용히 `[]` 로 간다(의도)."""
        assert json_array_payload("WARN: nothing to report") == ""
        assert json_array_payload("") == ""

    def test_a_clean_array_without_preamble_still_works(self):
        """대조군 — 프리앰블이 없는 판(구버전·다른 설정)도 그대로 통과해야 한다."""
        assert json_array_payload('[{"file":"a.kt","errors":[]}]') == '[{"file":"a.kt","errors":[]}]'


class TestUnparseableOutputIsNotSilent:
    """🔴 「못 읽은 출력」이 「깨끗함」과 구별되는가 (Grok claim-review `01a01fb3` K2·K4).

    프리앰블 수정만으로는 절반이다. `json_array_payload` 가 아무것도 못 찾으면
    호출부가 `[]` 를 돌려주는데, 그것은 **이 버그가 내던 값과 같다** — 관측자는
    분석기가 죽었는지 정말 깨끗한지 구별할 수 없다.

    🔴 그리고 이 축이 없으면 **`return "[]"` 뮤턴트가 살아남는다**(Grok K4):
    no-match 에서 빈 배열을 돌려주면 해피패스 테스트는 전부 초록인 채 침묵만 복원된다.
    내가 돌린 두 뮤테이션(`startswith` 복귀 · `find`)은 둘 다 파싱을 깨뜨려서
    **내가 이미 기각한 설계만** 잡고 있었다.
    """

    def _run_with_stdout(self, stdout: str, caplog):
        from unittest.mock import MagicMock, patch  # pylint: disable=import-outside-toplevel

        from src.analyzer.pure.registry import AnalyzeContext  # pylint: disable=import-outside-toplevel

        ctx = AnalyzeContext(
            filename="Dirty.kt", content="fun main() {}", language="kotlin",
            is_test=False, tmp_path="/tmp/Dirty.kt",
        )
        proc = MagicMock(stdout=stdout, stderr="", returncode=1)
        with patch("src.analyzer.io.tools.ktlint.subprocess.run", return_value=proc), \
             caplog.at_level(logging.WARNING, logger="src.analyzer.io.tools.ktlint"):
            issues = _KtlintAnalyzer().run(ctx)
        return issues, caplog.text

    def test_output_we_cannot_parse_is_logged(self, caplog):
        """🔴 뱉었는데 못 읽었다 — 조용히 0건으로 넘기지 않는다."""
        issues, log = self._run_with_stdout("WARN something went sideways, no json here", caplog)

        assert issues == []
        assert "parser contract broken" in log, (
            "계약 도구가 낸 출력을 못 읽었는데 로그가 없다 — 이 버그와 같은 침묵이다"
        )

    def test_truly_empty_output_is_not_logged(self, caplog):
        """대조군 — 빈 출력은 **정상 clean** 이다. 여기서 경고하면 늑대소년이 된다."""
        issues, log = self._run_with_stdout("", caplog)

        assert issues == []
        assert "parser contract broken" not in log

    def test_a_real_array_still_parses(self, caplog):
        """대조군 — 정상 경로가 살아 있어야 위 두 축이 의미를 갖는다."""
        issues, log = self._run_with_stdout(_REAL_KTLINT_STDOUT, caplog)

        assert len(issues) == 1
        assert "no-semi" in issues[0].message
        assert "parser contract broken" not in log
