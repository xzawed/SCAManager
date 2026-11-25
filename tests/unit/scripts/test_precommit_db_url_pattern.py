"""pre-commit 1층이 «자격이 든 DB 접속 주소» 를 커밋 전에 막는다 (회고 원장 #1917 M02 P2-8) · 훅 판도 갱신 감시 (P2-7).

## 이 파일이 잠그는 것

1. `check-db-url-in-diff`(pygrep)의 정규식은 비밀번호가 든 postgres 접속 주소를 잡는다 — 호스트가 예시 · 로컬 · 자리표시자가
   아니고, 비밀번호 자리가 자리표시자(`${…}` · `{…}` · `<…>` · `***`)가 아니면.
2. 계기 뒤집기 — 같은 꼴의 예시 · 로컬 · 자리표시자 줄은 잡지 않는다(witness corpus). 리포의 자리표시자 줄이 커밋마다
   막히면 훅이 꺼진다.
3. 문서(docs/)는 제외하지 않는다 — 시험(tests/ · e2e/)만 제외한다. 그리고 지금 리포의 제외 밖 추적 파일은 한 줄도 걸리지 않는다.
4. 공급망 — 리포에 있는 의존성 표면마다(pip · npm · Actions · pre-commit) Dependabot 갱신 항목이 있다.
"""
import re
import subprocess
import tomllib
from pathlib import Path

from ruamel.yaml import YAML

_ROOT = Path(__file__).resolve().parents[3]
_FAKE = "Zx9" + "q" * 9  # 합성 비밀번호 — 실제 값이 아니다 / synthetic password, not a real value


def _yaml(path):
    return YAML(typ="safe", pure=True).load((_ROOT / path).read_text(encoding="utf-8"))


def _hook(hook_id):
    for repo in _yaml(".pre-commit-config.yaml")["repos"]:
        for hook in repo.get("hooks", []):
            if hook.get("id") == hook_id:
                return hook
    raise AssertionError(f"{hook_id} 훅이 .pre-commit-config.yaml 에 없다")


# 막아야 할 꼴 — 실제 운영 주소와 같은 모양(합성 비밀번호).
# Shapes that must be blocked: production-like hosts with a synthetic password.
_MUST_BLOCK = [
    f"postgresql://postgres.abcdefghijkl:{_FAKE}@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres",
    f"postgres://app:{_FAKE}@db.internal.corp:6543/app",
    f"DATABASE_URL=postgresql+psycopg2://scam_app:{_FAKE}@prod-db.example.net.evil.io/db",
]

# witness-corpus: 같은 «postgres 주소 + 자격» 꼴이지만 막지 않아야 할 예시 · 로컬 · 자리표시자 줄(검사 집합 밖의 값)
_MUST_PASS = [
    f"postgresql://appuser:{_FAKE}@db.example.com:5432/scadb",
    "postgresql+psycopg2://scatest:scatest@localhost:5432/scatest",
    f"postgresql://user:{_FAKE}@127.0.0.1/db",
    "postgresql://user:<password>@<host>:5432/db",
    "postgresql://user:${DB_PASSWORD}@db.prod.internal/app",
    "postgresql://postgres:postgres@postgres:5432/db",
    'f"postgresql://{ROLE}.{ref}:{password}@{host}:{PORT}/postgres"',
    "postgresql://localhost/db",
]


def test_the_db_url_hook_blocks_credentialed_production_shapes():
    """🔴 비밀번호가 든 운영 모양 주소는 잡힌다."""
    rx = re.compile(_hook("check-db-url-in-diff")["entry"])
    assert [s for s in _MUST_BLOCK if not rx.search(s)] == []


def test_the_db_url_hook_lets_examples_and_placeholders_through():
    """대조군(뒤집기) — 예시 · 로컬 · 자리표시자는 잡지 않는다. «postgres:// 가 있으면 막기» 같은 싼 규칙은 여기서 걸린다."""
    rx = re.compile(_hook("check-db-url-in-diff")["entry"])
    assert [s for s in _MUST_PASS if rx.search(s)] == []


def test_the_db_url_hook_scans_docs_and_skips_only_tests():
    """문서는 제외하지 않는다 — 시험(tests/ · e2e/)만 뺀다. 커밋 단계에서 돈다."""
    hook = _hook("check-db-url-in-diff")
    assert hook["language"] == "pygrep" and hook.get("stages") == ["pre-commit"], hook
    exclude = re.compile(hook["exclude"])
    assert not exclude.search("docs/runbooks/railway.md") and not exclude.search("README.md"), hook["exclude"]
    assert exclude.search("tests/unit/test_database.py") and exclude.search("e2e/conftest.py"), hook["exclude"]


def test_no_tracked_file_outside_the_exclusion_trips_the_hook():
    """지금 리포의 제외 밖 추적 파일은 한 줄도 걸리지 않는다 — 걸리면 그 파일을 고칠 때마다 커밋이 막힌다."""
    hook = _hook("check-db-url-in-diff")
    rx, exclude = re.compile(hook["entry"]), re.compile(hook["exclude"])
    tracked = subprocess.run(["git", "-C", str(_ROOT), "ls-files"], capture_output=True, text=True,
                             check=True, timeout=30).stdout.splitlines()
    assert tracked, "추적 파일 목록이 비었다 — 잴 수 없다"
    hits = []
    for name in tracked:
        if exclude.search(name):
            continue
        try:
            text = (_ROOT / name).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        hits += [f"{name}:{n}" for n, line in enumerate(text.splitlines(), 1) if rx.search(line)]
    assert hits == [], hits


def test_gitleaks_exceptions_are_exact_values_on_top_of_the_default_rules():
    """🔴 `.gitleaks.toml` 은 기본 규칙을 확장하고, 예외는 앞뒤가 고정된 «값» 뿐이다 — 경로 · 규칙 통째 · 넓은 정규식 예외는
    진짜 비밀값까지 지나가게 한다. 대조군: 메타문자가 든 예외(`.*`)는 이 판정에 걸린다."""
    config = tomllib.loads((_ROOT / ".gitleaks.toml").read_text(encoding="utf-8"))
    assert config.get("extend", {}).get("useDefault") is True, config.get("extend")
    allowlists = config.get("allowlists", [])
    assert allowlists, "예외가 없다면 이 파일을 둘 까닭이 없다 — 비었는지부터 본다"

    def exact_value(rx):
        body = rx[1:-1] if rx.startswith("^") and rx.endswith("$") else None
        return body is not None and re.escape(body) == body

    assert not exact_value("^.*SECRET.*$"), "판정식이 넓은 예외를 «값» 으로 읽는다"
    for allow in allowlists:
        assert set(allow) <= {"description", "regexes"}, allow  # 경로 · 규칙 · stopwords 예외는 두지 않는다
        assert allow["regexes"] and all(exact_value(rx) for rx in allow["regexes"]), allow


# 의존성 표면 → Dependabot 생태계 이름. 표면이 리포에 있으면 그 생태계 항목이 있어야 한다.
# Dependency surface → Dependabot ecosystem; a present surface needs an update entry.
_SURFACES = {
    "requirements.txt": "pip",
    "package.json": "npm",
    ".github/workflows": "github-actions",
    ".pre-commit-config.yaml": "pre-commit",
}


def test_every_dependency_surface_has_a_dependabot_entry():
    """🔴 pre-commit 훅 판(gitleaks 등)도 갱신 감시 안에 있다 — 표면마다 Dependabot 항목이 있다."""
    present = {eco for path, eco in _SURFACES.items() if (_ROOT / path).exists()}
    assert "pre-commit" in present, "표면 목록이 리포와 어긋났다"
    configured = {u["package-ecosystem"] for u in _yaml(".github/dependabot.yml")["updates"]}
    assert sorted(present - configured) == [], configured
