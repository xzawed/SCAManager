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

export default [
  {
    // Jinja2 보간(`{{ }}`)이 <script> 안에 있는 템플릿은 JS 파서가 깨진다 — 구 `.eslintignore` 승계
    // Templates with Jinja2 interpolation inside <script> break the JS parser — carried from `.eslintignore`
    ignores: [
      "src/templates/analysis_detail.html",
      "src/templates/base.html",
      "src/templates/dashboard.html",
      "src/templates/repo_detail.html",
      "src/templates/repo_insights.html",
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
        htmx: "readonly",
        Chart: "readonly",
        AbortController: "readonly",
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
