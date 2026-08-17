## 지형

페이지 = `src/ui/routes/<도메인>.py` → `TemplateResponse(request, "<x>.html", {..., "locale": get_locale(request)})`. `src/ui/router.py` 에서 `/repos/{name}`(catch-all)은 마지막. `landing.html` 만 독립 head, 나머지는 `base.html` 상속.
CSS 순서 = `base.html:34~41` — tokens → themes → illustrations → dist/tailwind → components → pages.

## 설정 토글을 추가한다

체크박스 마크업만 넣으면 **저장되지 않고, 어떤 가드도 잡지 않는다**
(`check_config_5way_sync.py` 는 `settings.html` 을 범위 밖에 둔다). 5곳을 같은 PR 에 넣는다.

1. `src/models/repo_config.py` — `Column(Boolean, default=False, nullable=False)` + 마이그레이션([db.md](db.md))
2. `src/config_manager/manager.py:13` `RepoConfigData` — 같은 이름 필드. 빠지면 저장할 때마다 기본값으로 덮인다
3. `src/api/repos.py` `RepoConfigUpdate` — 같은 이름 필드. 1~3 불일치는 pre-commit `check-config-5way-sync` 가 red
4. `src/ui/routes/settings.py:218` `upsert_repo_config(db, RepoConfigData(` 에 `<name>=form.get("<name>") == "on",`
5. `src/templates/settings.html` `.toggle-row` 복제 (`{% if config.<name> %}checked{% endif %}`).
   프리셋이 지배하면 `PRESETS` 3개·`labels`·`currentFormValues()` 에도 넣는다

문구 키: 제목·설명은 `settings_page.<섹션>.<name>_title/_desc`, 프리셋 diff 라벨만 `settings.field_<name>` — `_KEYS` 대상은 후자뿐이다.

## 문구

1. `src/i18n/translations/` `en/ko/ja.json` 3개 동시 — 키 집합 불일치 = `tests/unit/i18n/test_loader.py:143` red.
2. 템플릿 = `{{ 'ns.key' | i18n_args(locale | default('ko')) }}`(생략형 금지). 변수는 kwarg — `| safe` 엔 사용자 입력 금지(미이스케이프).
3. `settings.*` 키는 `_KEYS`(`tests/unit/test_i18n_settings.py:24`)도 = 템플릿 참조와 set 동등. Python 은 `get_text("ns.key", locale)`.

## 화면

1. 색·간격·반경 = `var(--...)`. 새 토큰은 `src/static/css/tokens.css` `[data-theme]` 4블록(84·184·272·357) 전부.
2. 스타일: `components.css`(공용) · `pages.css` · `admin.css`(관리자) · `repo_insights.css`.
3. 인라인 `<script>` top-level 은 `var`, 리스너는 named handler + `removeEventListener`/`AbortController`(hx-boost swap 이 재실행).
4. `new Chart` 앞 `if (typeof Chart === 'undefined') return;`.
5. `input`/`select` = i18n `aria-label`, `.field-label` = `for`.
6. 외부 CDN 금지(CSP `src/main.py:90` = `'self'`) — `src/static/vendor/` 참조.
7. Tailwind 유틸 신규 시 `npm run build`. `dist/tailwind.css` = gitignore(커밋 금지).

## 검증

```
py -3 -m pytest tests/unit/ui tests/unit/i18n tests/unit/templates
py -3 -m pytest e2e/ -p no:asyncio
uvicorn src.main:app --reload --port 8000
```

4테마(dark·light·pastel·catppuccin) × 모바일/데스크탑 확인. 테마 = 헤더 드롭다운 → `localStorage['sca-theme']`.
언어 = `POST /api/users/me/preferred-language` → DB + Cookie `preferred_language`(httponly) → `LocaleMiddleware`. 없으면 `Accept-Language` → `DEFAULT_LOCALE`(`en`).
