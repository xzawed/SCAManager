// 런타임 eslint 분석기 설정 — 비-JSX 파일(.js/.mjs/.cjs/.ts) 전용 (#1226)
// Runtime eslint analyzer config — non-JSX files (.js/.mjs/.cjs/.ts) only (#1226).
//
// 🔴 왜 `.json` 이 아니라 `.mjs` 인가: eslint 9+ flat config 로더는 설정 파일을 **ESM 으로 import**
//    한다. `.json` 을 넘기면 Node 가 `ERR_IMPORT_ATTRIBUTE_MISSING`(needs import attribute
//    "type: json")로 죽고, 분석기는 비-JSON stdout 을 보고 조용히 `[]` 를 반환했다 = JS/TS 이슈
//    항상 0 → 점수 인플레. 구 `eslint.config.json` 은 배열 형식만 맞았을 뿐 **로드 자체가 불가**했다.
// 🔴 Why `.mjs` and not `.json`: the ESLint 9+ flat-config loader imports the config as an ES module.
//    Handing it a `.json` file dies with ERR_IMPORT_ATTRIBUTE_MISSING, and the analyzer silently
//    returned `[]` — JS/TS issues were always zero, inflating scores. The old `eslint.config.json`
//    had the right array shape but could never actually be loaded.
//
// 🔴 `files` glob 은 생략 금지: flat config 의 기본 매칭은 `**/*.js|mjs|cjs` 뿐이라, glob 없이는
//    `.ts` 가 "File ignored because no matching configuration was supplied" **경고 1건**을 만든다.
//    그 가짜 경고는 code_quality 이슈로 집계돼 점수를 부당하게 깎는다(침묵보다 나쁨).
// 🔴 Never omit the `files` glob: flat config only matches `**/*.js|mjs|cjs` by default, so without it
//    a `.ts` file yields a bogus "File ignored..." warning that counts as a real issue and wrongly
//    deducts points — worse than silence.
import tsParser from "@typescript-eslint/parser";

// 두 설정 파일이 규칙·전역을 공유하지 않고 각자 보유한다 — 사용처 2곳이라 추상화 미도입 (정책 16).
// The two config files each carry their own rules/globals — only 2 call sites, so no shared module (policy 16).
const globals = {
  console: "readonly",
  process: "readonly",
  window: "readonly",
  document: "readonly",
  require: "readonly",
  module: "readonly",
  exports: "readonly",
  __dirname: "readonly",
  __filename: "readonly",
};

const rules = {
  "no-unused-vars": "warn",
  "no-eval": "error",
  "no-implied-eval": "error",
  "no-new-func": "error",
  "no-console": "warn",
  eqeqeq: "warn",
  "no-var": "warn",
  "prefer-const": "warn",
  "no-undef": "warn",
  "no-redeclare": "error",
};

export default [
  {
    files: ["**/*.js", "**/*.mjs", "**/*.cjs"],
    languageOptions: { ecmaVersion: "latest", sourceType: "module", globals },
    rules,
  },
  {
    // TypeScript 는 espree 로 파싱 불가 — 타입 주석에서 fatal "Parsing error: Unexpected token :"
    // (severity 2 = ERROR)가 나 점수를 크게 깎는다. @typescript-eslint/parser 필수.
    // TypeScript cannot be parsed by espree — type annotations raise a fatal parsing error
    // (severity 2) that heavily deducts points. @typescript-eslint/parser is required.
    files: ["**/*.ts"],
    languageOptions: { parser: tsParser, ecmaVersion: "latest", sourceType: "module", globals },
    rules,
  },
];
