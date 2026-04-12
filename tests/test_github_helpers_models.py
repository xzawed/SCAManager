"""Tests for src/github_client/helpers.py and src/github_client/models.py.

이 두 모듈은 외부 의존성이 없으므로 mock 없이 직접 검증한다.
"""
import dataclasses

from src.github_client.helpers import github_api_headers
from src.github_client.models import ChangedFile


# --- github_api_headers ---

def test_github_api_headers_authorization():
    # Authorization 헤더가 "Bearer <token>" 형식인지 검증
    headers = github_api_headers("mytoken")
    assert headers["Authorization"] == "Bearer mytoken"


def test_github_api_headers_accept():
    # Accept 헤더가 GitHub JSON 미디어 타입인지 검증
    headers = github_api_headers("anytoken")
    assert headers["Accept"] == "application/vnd.github+json"


def test_github_api_headers_version():
    # X-GitHub-Api-Version 헤더가 지정된 버전 문자열인지 검증
    headers = github_api_headers("anytoken")
    assert headers["X-GitHub-Api-Version"] == "2022-11-28"


def test_github_api_headers_returns_dict():
    # 반환값이 dict 타입인지 검증
    result = github_api_headers("anytoken")
    assert isinstance(result, dict)


# --- ChangedFile ---

def test_changed_file_creation():
    # ChangedFile dataclass 를 올바른 인자로 생성할 수 있는지 검증
    cf = ChangedFile(filename="a.py", content="code", patch="@@ -1 +1 @@")
    assert cf is not None


def test_changed_file_fields():
    # filename, content, patch 속성이 생성 시 전달한 값과 일치하는지 검증
    cf = ChangedFile(filename="a.py", content="x = 1\n", patch="@@ -1 +1 @@\n+x = 1")
    assert cf.filename == "a.py"
    assert cf.content == "x = 1\n"
    assert cf.patch == "@@ -1 +1 @@\n+x = 1"


def test_changed_file_is_dataclass():
    # ChangedFile 이 dataclass 로 선언되었는지 검증
    assert dataclasses.is_dataclass(ChangedFile)


def test_changed_file_equality():
    # 동일한 값으로 생성한 두 ChangedFile 인스턴스가 == 비교에서 True 인지 검증
    # (dataclass 는 __eq__ 를 필드 기반으로 자동 생성한다)
    cf1 = ChangedFile(filename="b.py", content="pass\n", patch="@@ -0,0 +1 @@\n+pass")
    cf2 = ChangedFile(filename="b.py", content="pass\n", patch="@@ -0,0 +1 @@\n+pass")
    assert cf1 == cf2
