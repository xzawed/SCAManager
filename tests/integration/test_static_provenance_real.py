"""정적 분석 출처 — 실물 바이너리의 `--version` 을 읽는다 (회고 원장 L03 P2-104).

mock 은 «앞 두 줄» 규칙이 실물 출력에서도 하위 판(astroid · pycodestyle)을 남기는지 못 본다. CI 와 개발 환경에
requirements 로 깔리는 파이썬 분석기 셋을 실물로 부르고, 설치된 배포판의 판과 대조한다. 운영 이미지의
16종 전체는 CI docker 잡이 같은 함수로 핀과 대조한다.

Real binaries: the two-line rule must keep the sub-versions on real output. The image-wide check for all
provisioned analyzers runs in the CI docker job with the same function.
"""
from __future__ import annotations

import importlib.metadata

import pytest

from src.analyzer.io import static_provenance as sp


@pytest.mark.parametrize("tool,parts", [
    ("pylint", ("pylint", "astroid")),
    ("flake8", ("flake8", "pycodestyle", "pyflakes")),
    ("bandit", ("bandit",)),
], ids=["pylint", "flake8", "bandit"])
def test_real_version_names_the_installed_distributions(tool, parts):
    """판 글자에 설치된 배포판의 판이 모두 들어 있다 — 둘째 줄의 하위 판까지. 못 읽으면 red 다(건너뛰지 않는다)."""
    version = sp.read_version(tool)
    assert version, f"{tool} --version 을 못 읽었다 — requirements 로 깔리는 도구다"
    for dist in parts:
        assert importlib.metadata.version(dist) in version, f"{tool}: {dist} 판이 {version!r} 에 없다"
