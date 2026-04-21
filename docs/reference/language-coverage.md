# 언어 커버리지 레퍼런스

> 각 파일이 어떤 분석을 받는지 한눈에 확인할 수 있는 단일 참조 문서.
> 정적분석 도구가 **미설치** 상태이면 `is_enabled()=False`로 조용히 skip — 오류 없이 AI 리뷰만 실행됨.

## 동작 방식

```
파일 도착
  → language.py: detect_language(filename, content)  # 확장자·파일명·shebang 순
  → review_prompt.py: 언어별 가이드 조립 (토큰 예산 8000)
  → REGISTRY 순회: supports(ctx) & is_enabled(ctx) → run(ctx)
  → calculate_score: category="code_quality"|"security" 집계
```

`ANTHROPIC_API_KEY` 미설정 시 AI 리뷰 항목은 기본값(커밋13+방향21+테스트10)으로 fallback, 최대 89점(B).

---

## 언어별 커버리지 매트릭스 (50개)

### Tier 1 — 상세 체크리스트 + 전용 도구

| # | 언어 | 감지 확장자 | AI 가이드 | 정적분석 도구 | Phase D 후보 |
|---|-----|----------|---------|------------|------------|
| 1 | Python | `.py` `.pyi` | Full | pylint, flake8, bandit, semgrep | — (완전) |
| 2 | JavaScript | `.js` `.mjs` `.cjs` `.jsx` | Full | eslint, semgrep | — (완전) |
| 3 | TypeScript | `.ts` `.tsx` | Full | eslint, semgrep | — (완전) |
| 4 | Java | `.java` | Full | semgrep | PMD 🔴 |
| 5 | Go | `.go` | Full | semgrep | golangci-lint 🟡 |
| 6 | Rust | `.rs` | Full | semgrep (실험) | cargo clippy 🔴 |
| 7 | C | `.c` `.h` | Full | semgrep, **cppcheck** | — (Phase D.1 완료) |
| 8 | C++ | `.cpp` `.cc` `.cxx` `.hpp` `.hxx` | Full | semgrep, **cppcheck** | — (Phase D.1 완료) |
| 9 | C# | `.cs` | Full | semgrep | — |
| 10 | Ruby | `.rb` `Rakefile` `Gemfile` | Full | semgrep | RuboCop 🟡 |

### Tier 2 — 표준 체크리스트 + Semgrep (가능 시)

| # | 언어 | 감지 확장자 | AI 가이드 | 정적분석 도구 | 비고 |
|---|-----|----------|---------|------------|-----|
| 11 | PHP | `.php` | Standard | semgrep | — |
| 12 | Swift | `.swift` | Standard | semgrep (부분) | — |
| 13 | Kotlin | `.kt` `.kts` | Standard | semgrep | detekt 🟠 Phase D |
| 14 | Scala | `.scala` `.sc` | Standard | semgrep | — |
| 15 | Shell | `.sh` `.bash` `.zsh` / shebang | Standard | shellcheck, semgrep | Phase C 완료 |
| 16 | PowerShell | `.ps1` `.psm1` | Standard | — | 체크리스트만 |
| 17 | SQL | `.sql` | Standard | semgrep (부분) | injection 주의 |
| 18 | Dart | `.dart` | Standard | — | Flutter |
| 19 | Lua | `.lua` / shebang | Standard | — | — |
| 20 | Perl | `.pl` `.pm` / shebang | Standard | — | — |
| 21 | R | `.r` | Standard | — | 대소문자 무시 |
| 22 | Elixir | `.ex` `.exs` | Standard | semgrep | — |
| 23 | Haskell | `.hs` | Standard | — | — |
| 24 | Clojure | `.clj` `.cljs` | Standard | semgrep | — |
| 25 | Groovy | `.groovy` `.gradle` | Standard | — | Gradle |
| 26 | HTML | `.html` `.htm` | Standard | semgrep (XSS) | — |
| 27 | CSS/SCSS | `.css` `.scss` `.sass` `.less` | Standard | — | — |
| 28 | Solidity | `.sol` | Standard | semgrep | slither 🟢 Phase D |
| 29 | Objective-C | `.m` `.mm` | Standard | — | — |
| 30 | F# | `.fs` `.fsi` | Standard | — | .NET |

### Tier 3 — 경량 체크리스트 (AI 리뷰만)

| # | 언어/포맷 | 감지 방법 | AI 가이드 | 정적분석 |
|---|---------|---------|---------|--------|
| 31 | Erlang | `.erl` `.hrl` | Light | — |
| 32 | OCaml | `.ml` `.mli` | Light | — |
| 33 | Julia | `.jl` | Light | — |
| 34 | Zig | `.zig` | Light | — |
| 35 | Nim | `.nim` | Light | — |
| 36 | Crystal | `.cr` | Light | — |
| 37 | Gleam | `.gleam` | Light | — |
| 38 | Elm | `.elm` | Light | — |
| 39 | Vimscript | `.vim` | Light | — |
| 40 | GDScript | `.gd` | Light | — |
| 41 | Dockerfile | `Dockerfile` `Dockerfile.*` | Light | semgrep |
| 42 | Makefile | `Makefile` `GNUmakefile` | Light | — |
| 43 | Terraform (HCL) | `.tf` `.hcl` | Light | semgrep |
| 44 | YAML | `.yml` `.yaml` | Light | semgrep |
| 45 | TOML | `.toml` | Light | — |
| 46 | GraphQL | `.graphql` `.gql` | Light | — |
| 47 | Protocol Buffers | `.proto` | Light | — |
| 48 | XML | `.xml` | Light | — |
| 49 | LaTeX | `.tex` | Light | — |
| 50 | Unknown | — | Generic fallback | — |

---

## AI 가이드 토큰 예산 (review_prompt.py)

| 파일 수 | 적용 정책 |
|-------|---------|
| 감지 언어 ≤ 3개 | 전체 Full 가이드 |
| 4~6개 | Tier 1 Full + 나머지 Compact (1줄 요약) |
| 7~10개 | 상위 3개 Full + 나머지 Compact |
| 11개 이상 | 상위 5개 Compact만, 나머지 언어명만 나열 |

**전체 프롬프트 상한**: 8000 토큰 (diff 포함).

---

## 언어 감지 우선순위

```
1. 파일명 패턴: Dockerfile, Makefile, Dockerfile.prod, Rakefile, Gemfile
2. 확장자 매핑: .py → python, .js → javascript 등 (대소문자 무시)
3. Shebang 파싱: #!/usr/bin/env python3, #!/bin/bash 등
4. Fallback: "unknown" → Generic 가이드 적용, 정적분석 skip
```

감지 로직: [src/analyzer/language.py](../../src/analyzer/language.py)

---

## Phase D 리스크 요약

| 리스크 | 도구 | 이미지 증가 |
|-------|-----|----------|
| 🟢 낮음 | ~~cppcheck (C/C++)~~ ✅ 완료, slither (Solidity) | +30~100MB |
| 🟡 중간 | golangci-lint (Go), RuboCop (Ruby) | +80~200MB |
| 🟠 높음 | detekt (Kotlin), PHPStan (PHP) | +150~350MB |
| 🔴 최상위 | PMD (Java), cargo clippy (Rust) | +300~700MB, Docker 전환 필요 |
