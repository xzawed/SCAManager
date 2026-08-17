## 지형

페이지 = `src/ui/routes/<도메인>.py` 가 `templates.TemplateResponse(request, "<x>.html", {..., "locale": get_locale(request)})` 를 반환한다. 라우터 조립은 `src/ui/router.py` — `/repos/{name}` 이 catch-all 이라 마지막에 include 한다.
템플릿은 전부 `base.html` 상속. 예외는 `landing.html`(비로그인 전용, 독립 head).
CSS 로드 순서 = `base.html:34~41` — tokens → themes → illustrations → dist/tailwind → components → pages.

## 설정 토글을 추가한다

체크박스 마크업만 넣으면 **저장되지 않고, 어떤 가드도 잡지 않는다**
(`check_config_5way_sync.py` 는 `settings.html` 을 범위 밖에 둔다). 5곳을 같은 PR 에 넣는다.

1. `src/models/repo_config.py` — `Column(Boolean, default=False, nullable=False)` + 마이그레이션([db.md](db.md))
2. `src/config_manager/manager.py:13` `RepoConfigData` — 같은 이름 필드. 빠지면 저장할 때마다 기본값으로 덮인다
3. `src/api/repos.py` `RepoConfigUpdate` — 같은 이름 필드. 1~3 불일치는 pre-commit `check-config-5way-sync` 가 red
4. `src/ui/routes/settings.py:218` `upsert_repo_config(db, RepoConfigData(` 에 `<name>=form.get("<name>") == "on",`
5. `src/templates/settings.html` `.toggle-row` 복제 (`{% if config.<name> %}checked{% endif %}`).
   프리셋이 지배하면 `PRESETS` 3개·`labels`·`currentFormValues()` 에도 넣는다

문구 키: 제목·설명은 `settings_page.<섹션>.<name>_title/_desc`, 프리셋 diff 라벨만 `settings.field_<name>`
— `_KEYS` 대상은 후자뿐이다.

## 문구를 추가·변경한다

1. `src/i18n/translations/` 의 `en.json` `ko.json` `ja.json` **3개에 동시** 추가한다. 키 집합이 어긋나면 `tests/unit/i18n/test_loader.py:143` 이 red.
2. 템플릿에 `{{ 'ns.key' | i18n_args(locale | default('ko')) }}` 로 쓴다. 변수는 kwarg — `i18n_args(locale | default('ko'), name=user.name)`. `default('ko')` 를 뺀 형태는 쓰지 않는다.
3. `| safe` 컨텍스트에는 사용자 입력을 kwarg 로 넘기지 않는다(이스케이프 안 됨).
4. `settings.*` 키면 `tests/unit/test_i18n_settings.py:24` 의 `_KEYS` 도 같이 고친다 — 템플릿 참조 집합과 set 동등이 강제된다.
5. Python 쪽 문구는 `get_text("ns.key", locale)`.
6. `py -3 -m pytest tests/unit/i18n tests/unit/templates`

## 화면을 바꾼다

1. 색·간격·반경은 `var(--...)` 만 쓴다. 새 토큰이 필요하면 `src/static/css/tokens.css` 의 `[data-theme]` 4블록(84·184·272·357)에 **모두** 넣는다.
2. 스타일 위치 — 공용 컴포넌트 `components.css`, 페이지 레이아웃 `pages.css`, 관리자 화면 `admin.css`, 리포 인사이트 `repo_insights.css`.
3. 인라인 `<script>` 의 top-level 선언은 `var` 로 한다 — hx-boost body swap 이 같은 컨텍스트에서 재실행한다.
4. 리스너는 named handler + 선행 `removeEventListener` 또는 `AbortController`.
5. `new Chart` 앞에 `if (typeof Chart === 'undefined') return;` 을 둔다.
6. `input`/`select` 에 i18n 바인딩 `aria-label` 을, `<label class="field-label">` 에 `for` 를 넣는다.
7. 외부 CDN `<link>`·`<script>` 는 넣지 않는다 — CSP(`src/main.py:90`)가 `'self'` 다. 필요하면 `src/static/vendor/` 에 파일을 두고 참조한다.
8. Tailwind 유틸리티 클래스를 새로 썼으면 `npm run build`. 산출물 `dist/tailwind.css` 는 gitignore 대상이라 커밋하지 않는다.

## 검증

```
py -3 -m pytest tests/unit/ui tests/unit/i18n tests/unit/templates
uvicorn src.main:app --reload --port 8000
py -3 -m pytest e2e/ -p no:asyncio
```

브라우저에서 4테마(dark·light·pastel·catppuccin) × 모바일/데스크탑을 눈으로 확인한다. 테마는 헤더 드롭다운으로 전환되고 `localStorage['sca-theme']` 에 저장된다.
언어는 헤더 드롭다운 → `POST /api/users/me/preferred-language` → DB + httponly Cookie `preferred_language` → 다음 요청부터 `LocaleMiddleware` 가 반영한다. Cookie 가 없으면 `Accept-Language`, 그다음 `DEFAULT_LOCALE`(기본 `en`).
