"""정적 분석 출처 — 분석 행이 어느 빌드 · 어느 분석기 판 · 어느 고정 룰로 만들어졌는지 (회고 원장 L03 P2-104).

분석 행에 이것이 없으면 «분석기를 올린 배포 전후로 운영 분포를 대조» 하는 검증은 행을 분석기 판으로
나눌 수 없어 답을 못 낸다. 빌드 커밋만으로는 모자라다 — Dockerfile 은 apt 분석기(shellcheck · cppcheck)와
Node · Python 의 패치 판을 핀하지 않고, Railway 는 배포마다 이미지를 새로 빌드한다. 그래서 실제로 부른
바이너리의 `--version` 도 함께 남긴다.

🔴 판 읽기(바이너리 실행)는 프로세스마다 도구당 한 번, 이벤트 루프 밖에서 한다(`ensure_probed` —
   파이프라인이 `asyncio.to_thread` 로 부른다). 행에 싣는 쪽(`static_provenance`)은 메모리만 읽는다 —
   정적 분석 제한 시간을 쓰지 않고, 저장을 막지 않는다. 못 읽은 판은 None(모름)이다.
   점수 · 게이트는 이 기록을 읽지 않는다.

Static-analysis provenance (retro ledger L03 P2-104). The build commit alone cannot say which analyzer
versions ran — apt analyzers and Node/Python patch releases are unpinned and every deploy rebuilds the
image — so the `--version` of each binary actually invoked is recorded too. Versions are read once per
tool per process, off the event loop; building the record only reads memory and never blocks the save.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess  # nosec B404
import threading
from collections.abc import Iterable

from src.analyzer.io.static import analyzer_binary
from src.analyzer.pure.registry import REGISTRY

logger = logging.getLogger(__name__)

# `--version` 의 앞 두 줄 — 결과를 바꾸는 하위 판이 둘째 줄에 있다(pylint 의 astroid · tflint 의 룰셋).
# 실물 꼴은 CI docker 잡이 운영 이미지 안에서 같은 함수로 핀과 대조한다(ci.yml «pinned versions» 스텝).
# The first two lines carry the sub-versions that change output (pylint's astroid, tflint's ruleset).
_VERSION_LINES = 2
_VERSION_CHARS = 200
# 도구 하나의 판 읽기 상한(초). 실측 가장 느린 것은 semgrep(로컬 1.9 s) — 넉넉히 둔다.
# Per-tool probe timeout; the slowest measured probe (semgrep) took 1.9 s.
_PROBE_TIMEOUT = 20
# Railway 가 GitHub 에서 시작한 배포에 넣어 주는 커밋 — 이 꼴이 아니면 싣지 않는다.
# The commit Railway sets for GitHub-triggered deploys; anything else is not recorded.
_COMMIT = re.compile(r"[0-9a-f]{7,64}")

# 도구 이름 → 이 프로세스가 읽은 판(못 읽었으면 None). 실패도 기억한다 — 깨진 바이너리를
# 분석마다 다시 부르지 않는다. 다음 배포(새 프로세스)가 다시 읽는다.
# tool -> version this process read (None when unreadable). Failures are remembered too.
_VERSIONS: dict[str, str | None] = {}
_LOCK = threading.Lock()


def invoked_tools(analysis_results: Iterable[object]) -> list[str]:
    """이 분석에서 파일마다 부른 분석기의 합집합(정렬). / Union of analyzers invoked across files, sorted."""
    return sorted({
        tool for result in analysis_results
        for tool in (getattr(result, "invoked_tools", None) or ())
    })


def read_version(tool: str) -> str | None:
    """`<바이너리> --version` 앞 두 줄을 공백 하나로 이은 글자(200자까지). 못 읽으면 None.

    stdout 이 비었을 때만 stderr 를 본다 — 둘을 섞으면 «새 판이 나왔다» 같은 경고가 뜨는 날 같은
    바이너리의 판 글자가 바뀐다.
    First two lines of `--version` joined by one space (capped), or None. stderr is read only when
    stdout is empty, so a transient warning never changes the recorded version text.
    """
    binary = shutil.which(analyzer_binary(tool))
    if binary is None:
        return None
    try:
        # 인자는 which 가 찾은 경로와 고정 플래그뿐이다 / argv is the resolved path plus a fixed flag
        proc = subprocess.run(  # nosec B603
            [binary, "--version"], capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=_PROBE_TIMEOUT, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    lines = [line for line in (proc.stdout or "").splitlines() if line.strip()]
    if not lines:
        lines = [line for line in (proc.stderr or "").splitlines() if line.strip()]
    text = " ".join(" ".join(lines[:_VERSION_LINES]).split())
    return text[:_VERSION_CHARS] or None


def ensure_probed(tools: Iterable[str]) -> None:
    """아직 안 읽은 도구의 판을 읽어 둔다. 바이너리를 부르므로 이벤트 루프 밖에서 부른다.

    읽는 동안 잠금을 쥐지 않는다 — 루프 위의 `static_provenance` 가 그동안 기다리면 안 된다.
    두 분석이 같은 도구를 동시에 읽으면 먼저 쓴 쪽이 남는다(같은 바이너리라 값도 같다).
    Blocking (spawns binaries): call it off the event loop. The lock is never held while probing.
    """
    wanted = sorted(set(tools))
    read_now: list[str] = []
    for tool in wanted:
        with _LOCK:
            if tool in _VERSIONS:
                continue
        version = read_version(tool)
        with _LOCK:
            _VERSIONS.setdefault(tool, version)
        read_now.append(f"{tool}={version}")
    if read_now:
        # 새로 읽은 판만 한 줄 — 운영 로그로 «이 배포(빌드 커밋)가 어떤 판을 썼나» 를 본다
        # (관측 역할은 `result` 를 못 읽는다). 판 · 커밋은 비밀값이 아니다(공개 리포의 Dockerfile · git).
        # One line with the versions read just now and the build commit, visible in the deploy logs.
        logger.info("analyzer versions read (build %s): %s", _build_commit() or "unknown", "; ".join(read_now))
    # 룰 출처도 여기서 한 번 읽어 둔다(선언이 캐시한다) — 루프 위에서 파일을 열지 않게.
    # Read the declared rulesets here once (the declarations cache) so the loop never opens a file.
    _rulesets(wanted)


def probed_versions() -> dict[str, str | None]:
    """이 프로세스가 읽은 판의 사본. / A copy of the versions this process has read."""
    with _LOCK:
        return dict(_VERSIONS)


def static_provenance(analysis_results: Iterable[object]) -> dict:
    """분석 행(`Analysis.result`)에 싣는 출처 — 메모리만 읽는다.

    🔴 세 키를 늘 낸다. 조건부로 넣으면 «키 없음» 이 «부른 도구 없음» 과 «이 필드 이전의 옛 행» 두 가지를
    뜻하게 된다. 아직 안 읽은 도구의 판은 None 이다 — 여기서 바이너리를 부르지 않는다.
    Always emits build / tools / rulesets; reads memory only and never spawns a binary.
    """
    tools = invoked_tools(analysis_results)
    known = probed_versions()
    return {
        "build": _build_commit(),
        "tools": {tool: known.get(tool) for tool in tools},
        "rulesets": _rulesets(tools),
    }


def _rulesets(tools: list[str]) -> dict[str, str | None]:
    """부른 분석기 중 고정 룰을 **선언한** 것(`ruleset()`)의 출처. 도구 이름을 여기 적지 않는다 —
    선언에서 파생하므로 고정 룰을 쓰는 분석기가 늘면 선언 한 줄로 따라온다(`is_generic` 과 같은 방식).

    Rulesets of the invoked analyzers that *declare* one (`ruleset()`); derived from declarations,
    never from a list of tool names here.
    """
    found: dict[str, str | None] = {}
    for analyzer in REGISTRY:
        declared = getattr(analyzer, "ruleset", None)
        if analyzer.name in tools and callable(declared):
            try:
                found[analyzer.name] = declared()
            except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
                # 이 기록은 루프 위에서 저장 직전에 만든다 — 선언 하나의 결함이 분석 저장을 막지 않게 None(모름)으로.
                # Built on the loop right before the save: one faulty declaration records None, never blocks.
                found[analyzer.name] = None
    return dict(sorted(found.items()))


def _build_commit() -> str | None:
    """분석한 빌드의 커밋 — Railway 는 GitHub 에서 시작한 배포에만 준다. 그 밖(로컬 · 업로드 배포)은 None."""
    value = os.environ.get("RAILWAY_GIT_COMMIT_SHA", "").strip().lower()
    return value if _COMMIT.fullmatch(value) else None
