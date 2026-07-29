// ESLint flat config — 구 `.eslintrc.json` + `.eslintignore` 대체 (eslint 10 bump, #1222)
// ESLint flat config — replaces the legacy `.eslintrc.json` + `.eslintignore` (eslint 10 bump, #1222).
//
// 🔴 왜 이식이 필수인가: eslint 10 은 eslintrc 형식을 **로드하지 않는다**. 설정을 찾지 못하면
//    "couldn't find an eslint.config.(js|mjs|cjs)" 로 즉시 중단하는데, `make lint-js` 가 `|| true`
//    로 감싸여 있어 **아무 파일도 검사하지 않은 채 통과처럼 보인다**(가드 공허화).
//    `.eslintignore` 도 지원 종료 — 무시 목록은 아래 `ignores` 가 유일한 출처다.
// 🔴 Why this migration is mandatory: ESLint 10 does not load eslintrc at all. Without a flat config
//    it aborts, and since `make lint-js` swallows failures with `|| true`, the target would silently
//    lint nothing. `.eslintignore` is also gone — `ignores` below is the only source of truth.
//
// 🔴 `processor` 키를 쓰지 말 것: eslint-plugin-html 은 프로세서를 eslint 프로세스 **내부에서**
//    등록하므로 flat config 에서 `processor: "html/html"` 로 명시하면
//    `Could not find "html" in plugin "html"` 로 죽는다 (2026-07-27 실측). `plugins: { html }` 만
//    선언하면 플러그인이 알아서 HTML 을 처리한다.
// 🔴 Do NOT add a `processor` key: eslint-plugin-html registers its processor from inside the ESLint
//    process, so naming it explicitly fails with `Could not find "html" in plugin "html"` (measured).
//    Declaring `plugins: { html }` is enough.
import html from "eslint-plugin-html";
import globals from "globals";

export default [
  {
    // Jinja2 보간(`{{ }}`)이 <script> 안에 있는 템플릿은 JS 파서가 깨진다 — 구 `.eslintignore` 승계
    // Templates with Jinja2 interpolation inside <script> break the JS parser — carried from `.eslintignore`
    //
    // 🔴 이 목록의 기준은 **임의가 아니다**: "`<script>` 안에 Jinja2 구문이 있는 템플릿" 정확히
    //    그 집합이며, `tests/unit/scripts/test_eslint_ignores_sync.py` 가 **양방향으로 강제**한다
    //    (누락 = 파싱 오류 방치 / 과잉 = 근거 없는 검사 범위 축소). 항목을 손으로 추가하기 전에
    //    Jinja 값을 `<script>` 밖(예: `data-*` 속성·`<script type="application/json">`)으로
    //    옮길 수 있는지 먼저 검토할 것 — `ignores` 는 **검사 범위를 줄이는 선택**이다.
    // 🔴 This list is NOT an arbitrary set: it is exactly "templates carrying Jinja2 syntax inside a
    //    <script> block", enforced in both directions by tests/unit/scripts/test_eslint_ignores_sync.py
    //    (a missing entry leaves a parse error unnoticed; a surplus entry silently shrinks coverage).
    //    Before adding an entry, check whether the Jinja value can move out of <script> instead.
    ignores: [
      "src/templates/analysis_detail.html",
      "src/templates/base.html",
      "src/templates/dashboard.html",
      "src/templates/repo_detail.html",
      "src/templates/repo_insights.html",
      // 2026-07-29 추가 (#1227) — `<script>` 안 Jinja2 보간 **17개**로 전 템플릿 중 최다인데도
      // 목록 밖이라 `make lint-js` 의 유일한 error(`1289:15 Parsing error: Unexpected token {`)로
      // 남아 있었고, 그 error 는 `|| true` 에 삼켜져 관측되지 않았다. eslint 8·10 양쪽 동일 재현.
      // Added 2026-07-29 (#1227): 17 Jinja2 interpolations inside <script> — the most of any
      // template — yet it was missing here, leaving the sole `make lint-js` error unobserved
      // because the target swallows failures with `|| true`. Reproduced on both eslint 8 and 10.
      "src/templates/settings.html",
      "src/static/vendor/**",
    ],
  },
  {
    files: ["**/*.html"],
    plugins: { html },
    languageOptions: {
      ecmaVersion: 2017,
      // 인라인 <script> 는 모듈이 아니다 (구 `env.browser` + `es2017` 동등)
      // Inline <script> blocks are scripts, not modules (equivalent to the old `env.browser` + `es2017`).
      sourceType: "script",
      globals: {
        // 🔴 flat config 에는 `env: browser` 가 없다 — #1222 이식 때 그 선언이 사라지면서
        //    `document`·`window`·`fetch` 등이 전부 `no-undef` 경고가 됐다(실측 23건 = 당시
        //    전체 경고의 100%). 손으로 나열하면 새 브라우저 API 를 쓸 때마다 다시 새는 클래스라
        //    표준 `globals` 패키지로 한 번에 덮는다.
        // 🔴 Flat config has no `env: browser`; the #1222 migration dropped it, turning every
        //    `document`/`window`/`fetch` reference into a no-undef warning (23 = 100% of all
        //    warnings at the time). Hand-listing leaks again with each new browser API, so use
        //    the standard `globals` package.
        ...globals.browser,
        // 앱 고유 전역 — CDN/템플릿에서 주입되므로 browser 집합에 없다
        // App-specific globals injected by CDN/templates, absent from the browser set.
        htmx: "readonly",
        Chart: "readonly",
      },
    },
    rules: {
      "no-debugger": "error",
      "no-dupe-args": "error",
      "no-dupe-keys": "error",
      "no-duplicate-case": "error",
      "no-unreachable": "error",
      "no-undef": "warn",
    },
  },
];
