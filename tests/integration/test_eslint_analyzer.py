"""eslint 분석기 실바이너리 통합 테스트 (#1226).

🔴 왜 이 파일이 필요한가 — `tests/unit/analyzer/tools/test_eslint.py` 는 `subprocess.run` 을
전부 mock 하므로 **"argv 에 경로 문자열이 들어갔는가" 만** 검증한다. 그래서 운영 분석기가
JS/TS 파일에 대해 **100% 무동작**인 동안에도 단위 테스트 40건이 전건 통과했고 CI 는 초록이었다
(= 점수 인플레가 게이트까지 전파). mock 이 원리적으로 못 잡는 결함 5종을 여기서 실바이너리로 잡는다:

  결함 1  설정 경로가 존재하지 않는 디렉토리(`src/analyzer/io/configs/`)를 가리킴
  결함 3  `.json` 설정은 eslint 9+ flat-config 로더가 import 불가 (ERR_IMPORT_ATTRIBUTE_MISSING)
  결함 4  `files` glob 부재 → .jsx/.ts/.tsx 미매칭 → 가짜 "File ignored" 경고 = 부당 감점
  결함 5  cwd 미지정 → 임시파일이 base path 밖 → "File ignored because outside of base path"
  (결함 2 `--no-eslintrc` 는 argv 검사로 충분해 단위 테스트가 담당)

Real-binary integration test for the eslint analyzer (#1226). The unit tests mock subprocess.run
entirely, so they only assert that a path *string* reached argv — which is why 40 unit tests stayed
green while the analyzer was 100% dead in production. The five defects above are only observable
against a real eslint binary.
"""
import json
import os
import pathlib
import shutil
import subprocess  # nosec B404
import tempfile

import pytest

from src.analyzer.io.tools.eslint import _CONFIG_PATH, _REACT_CONFIG_PATH, _ESLintAnalyzer
from src.analyzer.pure.registry import AnalyzeContext

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_ESLINT_JS = _REPO_ROOT / "node_modules" / "eslint" / "bin" / "eslint.js"

# 확장자별 (언어, 프로브 코드) — 각 코드는 no-var + eqeqeq 를 반드시 유발한다.
# .ts/.tsx 는 타입 주석을 포함해 @typescript-eslint/parser 가 실제로 물렸는지까지 검증한다.
# Per-extension (language, probe source); every probe must trigger no-var + eqeqeq. The .ts/.tsx
# probes carry type annotations so they also prove @typescript-eslint/parser is actually wired.
_PROBES = {
    ".js":  ("javascript", "var a = 1;\nif (a == 1) { a = 2; }\n"),
    ".mjs": ("javascript", "var a = 1;\nif (a == 1) { a = 2; }\nexport {};\n"),
    ".cjs": ("javascript", "var a = 1;\nif (a == 1) { a = 2; }\n"),
    ".jsx": ("javascript", "var a = 1;\nconst E = () => <b>{a == 1}</b>;\nexport default E;\n"),
    ".ts":  ("typescript", "var a: number = 1;\nif (a == 1) { a = 2; }\n"),
    ".tsx": ("typescript", "var a: number = 1;\nconst E = () => <b>{a == 1}</b>;\nexport default E;\n"),
}


def _config_for(ext: str) -> str:
    """분석기와 **동일한 분기**로 설정 파일을 고른다 (테스트가 독자 규칙을 만들지 않도록)."""
    return _REACT_CONFIG_PATH if ext in {".jsx", ".tsx"} else _CONFIG_PATH


@pytest.mark.slow
@pytest.mark.skipif(not _ESLINT_JS.is_file(), reason="node_modules/eslint 미설치 — `npm install` 필요")
@pytest.mark.parametrize("ext", sorted(_PROBES))
def test_real_eslint_reports_issues_for_every_supported_extension(ext, tmp_path):
    """실 eslint 가 6개 확장자 전부에서 **진짜 이슈**를 낸다 (결함 1·3·4·5 동시 봉인).

    분석기가 쓰는 실제 설정 상수(`_CONFIG_PATH`/`_REACT_CONFIG_PATH`)와 동일한 인자·cwd 계약으로
    호출한다 — 합성 설정을 만들면 실경로를 검증하지 못한다 (AGENTS.md 불변식 2).
    """
    language, source = _PROBES[ext]
    target = tmp_path / f"analyze{ext}"
    target.write_text(source, encoding="utf-8")

    proc = subprocess.run(  # nosec B603
        ["node", str(_ESLINT_JS), "--format=json", "--no-config-lookup",
         "-c", _config_for(ext), str(target)],
        cwd=str(tmp_path),          # 결함 5 — base path 안에서 실행해야 린트된다
        capture_output=True, text=True, timeout=180, check=False,
    )

    assert proc.stdout.strip().startswith("["), (
        f"{ext}: eslint 가 JSON 을 내지 못했다 (분석기는 이 상태에서 조용히 [] 를 반환했다).\n"
        f"exit={proc.returncode}\nstderr={proc.stderr[:400]}"
    )
    messages = json.loads(proc.stdout)[0]["messages"]

    # 결함 4·5 — ruleId 가 없는 비-fatal 메시지 = 파일이 린트되지 않았다는 뜻
    not_linted = [m for m in messages if m.get("ruleId") is None and not m.get("fatal")]
    assert not not_linted, f"{ext}: 파일이 린트되지 않았다 — {not_linted[0]['message']}"

    # 결함 1·3 — 설정이 실제로 로드됐다면 규칙이 발화한다
    fired = {m["ruleId"] for m in messages if m.get("ruleId")}
    assert {"no-var", "eqeqeq"} <= fired, f"{ext}: 설정이 로드되지 않았다 (발화 규칙: {sorted(fired)})"


@pytest.mark.slow
@pytest.mark.skipif(shutil.which("eslint") is None, reason="전역 eslint 미설치")
@pytest.mark.skipif(os.name == "nt", reason="Windows 는 .cmd 를 CreateProcess 로 실행 불가 (CI=Linux 가 담당)")
def test_analyzer_run_end_to_end_with_global_eslint():
    """`_ESLintAnalyzer().run()` 전 경로 — 운영과 동일하게 전역 `eslint` 바이너리를 호출한다.

    위 테스트가 설정·인자 계약을 덮고, 이 테스트는 그것이 **분석기 진입점에서 실제로 도달하는지**
    를 확인한다 (AGENTS.md 불변식 3 — 정의 ≠ 배선).
    """
    with tempfile.TemporaryDirectory() as tmpdir:      # static.py 와 동일한 배치
        tmp_path = os.path.join(tmpdir, "analyze.js")
        with open(tmp_path, "w", encoding="utf-8") as fh:
            fh.write("var a = 1;\nif (a == 1) { a = 2; }\n")
        ctx = AnalyzeContext(
            filename="analyze.js", content="", language="javascript",
            is_test=False, tmp_path=tmp_path,
        )
        issues = _ESLintAnalyzer().run(ctx)

    assert issues, "전역 eslint 로 실행했는데 이슈가 0건 — 분석기가 무동작이다"
    assert all(i.tool == "eslint" and i.category == "code_quality" for i in issues)


@pytest.mark.slow
@pytest.mark.skipif(shutil.which("eslint") is None, reason="전역 eslint 미설치")
@pytest.mark.skipif(os.name == "nt", reason="Windows 는 .cmd 를 CreateProcess 로 실행 불가 (CI=Linux 가 담당)")
def test_unknown_rule_disable_does_not_deduct_score_end_to_end():
    """🔴 실바이너리 — 대상 리포가 **자기 설정의 룰**로 disable 을 달아도 감점되지 않는다 (R22).

    우리는 `--no-config-lookup` + 10-룰 최소 설정이라, 리포 고유 룰명은 eslint 에 미등록이다.
    eslint 는 그것을 `ruleId=<문자열>` · `severity=2` · `Definition for rule '…' was not found.`
    로 보고하는데(Grok `019fbaa0` 실측), 우리 코드가 그걸 **없는 결함**으로 집계해 점수를 깎았다.

    🔴 단위 테스트는 이 payload 를 **손으로 적어** 검증한다 — 그 형태가 eslint 버전에 따라
    바뀌면 단위는 초록인 채 운영만 깨진다. 여기서 **실제 eslint 가 그 형태를 내는지**까지 고정한다
    (`#1226` 이 남긴 교훈: mock 은 이 클래스를 원리적으로 못 잡는다).
    Real-binary counterpart: the unit test hard-codes the measured payload, so only this test can
    catch eslint changing that message shape.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = os.path.join(tmpdir, "analyze.js")
        with open(tmp_path, "w", encoding="utf-8") as fh:
            # 리포 고유 룰(우리 설정에 없음) + 실제 결함 1건(no-var·eqeqeq 발화)
            fh.write(
                "// eslint-disable-next-line some-repo-local-rule\n"
                "var a = 1;\nif (a == 1) { a = 2; }\n"
            )
        ctx = AnalyzeContext(
            filename="analyze.js", content="", language="javascript",
            is_test=False, tmp_path=tmp_path,
        )
        issues = _ESLintAnalyzer().run(ctx)

    assert issues, "실제 결함이 있는데 이슈 0건 — 분석기 무동작"
    meta = [i for i in issues if "was not found" in i.message]
    assert not meta, (
        f"설정 메타 메시지가 이슈로 집계됐다 — 정상 코드가 감점된다: {[i.message for i in meta]}"
    )
    fired = {i.message for i in issues}
    assert any("var" in m or "==" in m for m in fired), (
        f"실제 결함(no-var/eqeqeq)이 사라졌다 — 드롭이 과도하다: {sorted(fired)}"
    )
