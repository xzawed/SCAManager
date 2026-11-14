// 런타임 eslint 분석기 설정 — JSX/TSX 전용 (#1226)
// Runtime eslint analyzer config — JSX/TSX only (#1226).
//
// 설계 배경(`.mjs` 인 이유 · `files` glob 필수)은 같은 디렉토리의 `eslint.config.mjs` 머리말 참조.
// See the header of `eslint.config.mjs` in this directory for why this is `.mjs` and why the
// `files` glob is mandatory.
//
// 🔴 eslint-plugin-react 는 쓰지 않는다: JSX **구문 파싱**은 `ecmaFeatures.jsx` 만으로 충분하다(실측 확인).
//    React 전용 룰(react/*)이 필요해지면 devDependency 로 편입할 것 — 이 설정의 import 는 리포
//    node_modules 에서만 풀린다(전역 설치는 설정 위치에서 보이지 않는다).
// 🔴 No eslint-plugin-react: `ecmaFeatures.jsx` alone is enough to *parse* JSX (verified). Add it as a
//    devDependency if react/* rules are ever needed — this config's imports resolve only from the
//    repo node_modules (a global install is not visible from the config's location).
import tsParser from "@typescript-eslint/parser";

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
  React: "readonly",
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
    files: ["**/*.jsx"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals,
    },
    rules,
  },
  {
    files: ["**/*.tsx"],
    languageOptions: {
      parser: tsParser,
      ecmaVersion: "latest",
      sourceType: "module",
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals,
    },
    rules,
  },
];
