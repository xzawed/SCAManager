#!/usr/bin/env python3
"""README 히어로 스크린샷 재생성 — 현재 코드에서 로케일별로 1장씩.

Regenerate the README hero screenshot from the current code, one per locale.

## 왜 이 스크립트가 필요한가

`docs/design/brief/screenshots/` 의 디자인 브리프 덤프는 gitignore 대상이고 실제로
**낡았다**(2026-05-25 캡처 vs 그 뒤로도 바뀐 UI). README 가 렌더링하는 이미지는 git 에
들어가므로 같은 방식으로 낡으면 **문서가 거짓을 그린다**. 재생성 수단을 코드로 남겨
UI 를 바꾼 사람이 한 줄로 다시 찍을 수 있게 한다.

`scripts/capture_design_screenshots.py` 는 이 용도로 쓸 수 없다 — 브라우저 세션 쿠키를
손으로 넣어야 하고, 출력이 gitignore 대상 디렉토리다.

## 무엇을 그리나

빈 대시보드는 히어로로 쓸 수 없다(모든 KPI 가 0, 빈 상태 일러스트). 그래서 7일치
분석 이력을 **시드**한다 — 그 사실은 README 캡션에 명시돼 있어야 한다.
비용 카드는 `$0.0000` 으로 남는다: 시드는 `analyses` 만 만들고 실제 API 호출 기록이
없기 때문이다. **비용을 지어내지 않는다.**

사용법 / Usage:
    py -3 scripts/capture_readme_hero.py            # en + ko 둘 다
    py -3 scripts/capture_readme_hero.py --locale ko
"""
# 🔴 이 스크립트는 리포 루트를 `sys.path` 에 넣은 뒤에야 리포 모듈을 볼 수 있고,
#    playwright·PIL·uvicorn 은 캡처할 때만 필요하다(문서 갱신용 도구가 import 만으로
#    무거운 의존을 끌면 안 된다). 두 패턴 모두 의도된 것이라 여기서 끈다.
# Both patterns are deliberate: path bootstrap precedes repo imports, and the heavy
# capture-only dependencies stay lazy.
# pylint: disable=import-error,wrong-import-position,import-outside-toplevel
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# 🔴 `sys.path` 를 세운 **뒤에야** 리포 모듈을 import 할 수 있다 — E402 는 그 순서의
#    필연적 결과이지 실수가 아니다. 포트/URL 은 e2e 하네스와 하나로 유지한다.
# The path bootstrap must precede this import; E402 here is intentional.
from e2e.conftest import BASE_URL as BASE  # noqa: E402

OUT_DIR = ROOT / "docs" / "readme"

# 대시보드가 비어 보이지 않을 만큼의 7일치 이력. 점수는 A~C 에 걸치게 둔다.
_SCORES = [92, 88, 74, 81, 95, 68, 86, 90, 79, 84, 91, 77, 89, 83, 93]
_MSGS = [
    "feat: add score trend card",
    "fix: webhook retry backoff",
    "refactor: extract gate engine",
    "test: cover merge queue",
    "docs: update runbook",
]
_CAPTION_FILE = {"en": "dashboard.png", "ko": "dashboard.ko.png"}
# README 는 GitHub 의 밝은/어두운 크롬 양쪽에서 읽혀야 해 다크로 고정한다.
# Fixed to dark: the README is read against both GitHub chromes.
THEME = "dark"


def _start_server(db_path: str):
    """앱을 임시 SQLite 로 띄우고 로그인 의존성을 demo 사용자로 우회한다.

    🔴 스키마 생성과 uvicorn 기동은 `e2e/conftest.py` 것을 **재사용**한다. 직접 짜면
    모델 등록 순서(빈 `Base.metadata` 로 create_all → 컬럼 없는 테이블)와 앱 부팅과의
    경합을 다시 밟는다 — 실측으로 둘 다 밟았다.
    Reuse the e2e harness: hand-rolling schema creation reproduces the empty-metadata and
    boot-race failures (both hit while writing this).
    """
    import requests  # noqa: PLC0415

    from e2e.conftest import _setup_e2e_db, _start_uvicorn  # noqa: PLC0415

    _setup_e2e_db(db_path)
    server, thread = _start_uvicorn(db_path)

    from src.auth.session import CurrentUser, get_current_user, require_login  # noqa: PLC0415
    from src.main import app  # noqa: PLC0415

    demo = CurrentUser(id=1, github_login="demo", email="demo@example.com",
                       display_name="demo", plaintext_token="tok")
    app.dependency_overrides[require_login] = lambda: demo
    app.dependency_overrides[get_current_user] = lambda: demo

    for _ in range(60):
        try:
            if requests.get(f"{BASE}/health", timeout=1).status_code == 200:
                return server, thread
        except requests.RequestException:
            # 아직 안 떴을 뿐이다 — 기동 대기 중 연결 거부는 정상이라 재시도한다.
            # Not up yet; connection errors while polling are expected, so retry.
            pass
        time.sleep(0.5)
    server.should_exit = True
    raise RuntimeError("서버가 뜨지 않았다")


def _seed(db_path: str) -> None:
    """대시보드가 비어 보이지 않을 만큼의 7일치 이력.

    🔴 `analyses` 만 만든다. 비용 카드는 `$0.0000` 으로 남는데, 그것이 사실이다 —
    시드는 실제 API 호출을 하지 않았다. 화면을 채우려고 비용을 지어내지 않는다.
    Seeds analyses only; the cost card stays $0.0000 because no API call happened.
    """
    from sqlalchemy import create_engine, text  # noqa: PLC0415

    eng = create_engine(f"sqlite:///{db_path}")
    with eng.connect() as c:
        c.execute(text(
            "INSERT OR IGNORE INTO users (id, github_id, github_login, github_access_token,"
            " email, display_name, created_at) VALUES"
            " (1,'hero','demo','tok','demo@example.com','demo',datetime('now'))"))
        c.execute(text(
            "INSERT OR IGNORE INTO repositories (user_id, full_name, created_at)"
            " VALUES (1,'owner/demo',datetime('now'))"))
        c.execute(text("UPDATE repositories SET user_id=1 WHERE full_name='owner/demo'"))
        rid = c.execute(text(
            "SELECT id FROM repositories WHERE full_name='owner/demo'")).scalar()
        for i, score in enumerate(_SCORES):
            c.execute(text(
                "INSERT OR IGNORE INTO analyses (repo_id, commit_sha, commit_message, score,"
                " grade, result, author_login, pr_number, created_at)"
                " VALUES (:rid,:sha,:msg,:sc,:g,:res,'demo',:pr,datetime('now',:off))"
            ), {
                "rid": rid, "sha": f"demo{i:036d}", "sc": score,
                "g": "A" if score >= 90 else "B" if score >= 75 else "C",
                "msg": _MSGS[i % len(_MSGS)],
                "res": json.dumps({
                    "summary": "Static analysis and AI review completed.",
                    "breakdown": {"code_quality": 23, "security": 20},
                    "ai_review_status": "success",
                }),
                "pr": 100 + i,
                "off": f"-{(len(_SCORES) - i) * 11} hours",
            })
        c.commit()
    eng.dispose()


def _capture(locale: str) -> Path:
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / _CAPTION_FILE[locale]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1400, "height": 980}, base_url=BASE)
        ctx.add_cookies([{"name": "preferred_language", "value": locale,
                          "url": BASE}])
        page = ctx.new_page()
        page.goto(f"{BASE}/dashboard", wait_until="networkidle")
        # 🔴 키는 `sca-theme` 다 (`src/templates/base.html`). 초판은 `theme` 를 써서
        #    **아무 일도 하지 않았고**, 결과가 다크였던 건 그것이 기본값이기 때문이다 —
        #    지정한 척하며 지정하지 않는 줄이었다. 기본값이 바뀌면 조용히 다른 테마가 찍힌다.
        # The app reads `sca-theme`; the original `theme` write was a silent no-op that only
        # looked correct because dark is the default.
        page.evaluate(f"localStorage.setItem('sca-theme','{THEME}')")
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(2000)
        page.screenshot(path=str(out))
        browser.close()
    _shrink(out)
    return out


def _shrink(path: Path) -> None:
    """8-bit 팔레트로 다시 저장 — README 이미지는 수백 KB 를 쓸 이유가 없다."""
    try:
        from PIL import Image  # noqa: PLC0415
    except ImportError:
        print("  PIL 없음 — 최적화 생략")
        return
    before = path.stat().st_size
    with Image.open(path) as im:
        im.convert("P", palette=Image.ADAPTIVE, colors=256).save(path, optimize=True)
    print(f"  {path.name}: {before / 1024:.0f} KB → {path.stat().st_size / 1024:.0f} KB")


def main() -> int:
    # 🔴 `scripts/*.py` 전역 규칙 — 비-ASCII 출력이 cp949 콘솔에서 죽지 않게 한다.
    #    "이 스크립트는 안 쓴다" 는 판단을 두지 않는다(`test_stdout_encoding_guard.py`).
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 캡처된 stream 등 reconfigure 미지원 — 무시 / stream without reconfigure

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--locale", choices=sorted(_CAPTION_FILE), action="append",
                    help="반복 지정 가능. 생략하면 전부.")
    args = ap.parse_args()
    locales = args.locale or sorted(_CAPTION_FILE)

    # 🔴 Windows 는 서버 스레드가 SQLite 파일을 잡고 있어 정리에 실패한다 — 캡처를
    #    끝낸 뒤의 뒷정리 실패가 산출물을 버리게 하면 안 된다.
    # Windows holds the SQLite handle; cleanup failure must not discard the output.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = str(Path(tmp) / "hero.db")
        server, _thread = _start_server(db_path)
        _seed(db_path)
        try:
            for loc in locales:
                print(f"[{loc}] 캡처 중…")
                print(f"  저장: {_capture(loc).relative_to(ROOT).as_posix()}")
        finally:
            server.should_exit = True
            time.sleep(0.5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
