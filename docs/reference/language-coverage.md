# 언어 커버리지 레퍼런스

> 각 파일이 어떤 분석을 받는지 한눈에 확인할 수 있는 단일 참조 문서.
> 🔴 **도구 미설치의 결과는 3-way 다** (이전 "조용히 skip" 서술은 거짓):
>
> | 상황 | 결과 | auto-merge |
> |---|---|---|
> | **조달 계약**(`PROVISIONED_ANALYZERS`) 안 도구 부재 + 실행 0개 | `incomplete` | 🔴 **차단** (실제 배포 회귀) |
> | 계약 **밖** 도구만 부재 | `uncovered_language` 로 가시화 | 통과 (제품 미제공) |
> | 일부만 부재 (다른 도구가 실행됨) | 그 도구만 skip | 통과 |
>
> 계약 정본 = `src/analyzer/io/static.py::PROVISIONED_ANALYZERS` · 대조 가드 =
> `tests/unit/analyzer/test_procurement_contract.py`.

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

## 언어별 커버리지 매트릭스 (49개 언어 + Unknown)

> **표 읽는 법** — 「정적분석 도구」 열은 배포 이미지에 **조달돼 운영에서 실제로 실행되는** 것만
> 적는다(`PROVISIONED_ANALYZERS` 16종). **굵게** = 그 언어 전용 도구.
> 🟡 = 레지스트리에 등록됐으나 **미조달**(운영 미실행 · 부재해도 차단 안 함) ·
> 🔴 = 아직 등록조차 안 된 후보. 정본은 §등록·조달 현황 요약의 재파생 명령이다.

### Tier 1 — 상세 체크리스트 + 전용 도구

| # | 언어 | 감지 확장자 | AI 가이드 | 정적분석 도구 (조달됨) | 등록·미조달 🟡 / 미등록 후보 🔴 |
|---|-----|----------|---------|--------------------|------------------------------|
| 1 | Python | `.py` `.pyi` | Full | pylint, flake8, bandit, semgrep | — (완전) |
| 2 | JavaScript | `.js` `.mjs` `.cjs` `.jsx` | Full | eslint, semgrep | — (완전) |
| 3 | TypeScript | `.ts` `.tsx` | Full | eslint, **tsc**, semgrep | — (완전) |
| 4 | Java | `.java` | Full | semgrep | PMD 🔴 |
| 5 | Go | `.go` | Full | semgrep, **golangci-lint** | — (조달됨) |
| 6 | Rust | `.rs` | Full | semgrep (실험) | clippy 🟡 |
| 7 | C | `.c` `.h` | Full | semgrep, **cppcheck** | — (조달됨) |
| 8 | C++ | `.cpp` `.cc` `.cxx` `.hpp` `.hxx` | Full | semgrep, **cppcheck** | — (조달됨) |
| 9 | C# | `.cs` | Full | semgrep | dotnet_format 🟡 |
| 10 | Ruby | `.rb` `Rakefile` `Gemfile` | Full | semgrep, **RuboCop** | — (조달됨) |

### Tier 2 — 표준 체크리스트 + Semgrep (가능 시)

| # | 언어 | 감지 확장자 | AI 가이드 | 정적분석 도구 (조달됨) | 등록·미조달 🟡 / 비고 |
|---|-----|----------|---------|--------------------|---------------------|
| 11 | PHP | `.php` | Standard | semgrep | phpstan 🟡 |
| 12 | Swift | `.swift` | Standard | semgrep (부분) | swiftlint 🟡 |
| 13 | Kotlin | `.kt` `.kts` | Standard | semgrep, **ktlint** | detekt 🔴 후보 |
| 14 | Scala | `.scala` `.sc` | Standard | semgrep | — |
| 15 | Shell | `.sh` `.bash` `.zsh` / shebang | Standard | shellcheck, semgrep | — |
| 16 | PowerShell | `.ps1` `.psm1` | Standard | — | psscriptanalyzer 🟡 |
| 17 | SQL | `.sql` | Standard | **sqlfluff** | injection 주의 · semgrep 미지원 |
| 18 | Dart | `.dart` | Standard | — | dart_analyze 🟡 · Flutter |
| 19 | Lua | `.lua` / shebang | Standard | — | — |
| 20 | Perl | `.pl` `.pm` / shebang | Standard | — | — |
| 21 | R | `.r` | Standard | — | 대소문자 무시 |
| 22 | Elixir | `.ex` `.exs` | Standard | semgrep | — |
| 23 | Haskell | `.hs` | Standard | — | — |
| 24 | Clojure | `.clj` `.cljs` | Standard | semgrep | — |
| 25 | Groovy | `.groovy` `.gradle` | Standard | — | Gradle |
| 26 | HTML | `.html` `.htm` | Standard | semgrep (XSS) | htmlhint 🟡 |
| 27 | CSS/SCSS | `.css` `.scss` `.sass` `.less` | Standard | — | stylelint 🟡 |
| 28 | Solidity | `.sol` | Standard | semgrep, **slither** | — (조달됨) |
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
| 41 | Dockerfile | `Dockerfile` `Dockerfile.*` | Light | semgrep, **hadolint** |
| 42 | Makefile | `Makefile` `GNUmakefile` | Light | — |
| 43 | Terraform (HCL) | `.tf` `.hcl` | Light | semgrep, **tflint** |
| 44 | YAML | `.yml` `.yaml` | Light | semgrep, **yamllint** |
| 45 | TOML | `.toml` | Light | — |
| 46 | GraphQL | `.graphql` `.gql` | Light | — |
| 47 | Protocol Buffers | `.proto` | Light | — (buf_lint 🟡) |
| 48 | XML | `.xml` | Light | — |
| 49 | LaTeX | `.tex` | Light | — |
| 50 | Unknown | — | Generic fallback | — |

---

## AI 가이드 토큰 예산 (review_prompt.py)

| 감지 언어 수 | 적용 정책 |
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

감지 로직: [src/analyzer/pure/language.py](../../src/analyzer/pure/language.py)

---

## 등록·조달 현황 요약

등록 분석기 **25종** 중 조달 계약(`PROVISIONED_ANALYZERS` — `src/analyzer/io/static.py:54`)
안은 **16종**, 나머지 **9종**은 레지스트리에 있으나 배포 이미지 어디에도 없다.
계약 ↔ 조달 파일 양방향 대조 가드 = `tests/unit/analyzer/test_procurement_contract.py`.

| 구분 | 도구 | 비고 |
|-----|-----|-----|
| 🟡 등록·미조달 9종 | clippy(Rust) · phpstan(PHP) · swiftlint(Swift) · dotnet_format(C#) · psscriptanalyzer(PowerShell) · dart_analyze(Dart) · stylelint(CSS/SCSS) · htmlhint(HTML) · buf_lint(Protobuf) | 조달 계약 **밖**이라 부재해도 차단하지 않는다 |
| 🔴 미등록 후보 | detekt(Kotlin) +150~350MB · PMD(Java) +300~700MB | Kotlin 은 **ktlint 조달됨** — detekt 우선순위 하향 · PMD 는 Docker 전환 필요 |

> 🔴 **등록 ≠ 조달, 그리고 미조달 ≠ 가시화.**
> **이전 서술 정정(2026-08-17 실측)** — 이 자리에 「clippy·phpstan 은 조달되지 않아 운영에서
> 실행되지 않고 `uncovered_language` 로 가시화된다」고 적혀 있었다. 뒷절이 **거짓**이다.
> `uncovered_language` 는 그 언어를 지원하는 분석기가 **하나도 실행되지 않았을 때만** 붙는다
> (`src/analyzer/io/static.py:244-245` · `:275,296`). Rust·PHP·Swift·C#·HTML 은 semgrep 이
> 함께 돌아 `ran ≥ 1` 이므로 위 3-way 표의 **3행**(「그 도구만 skip · 통과」)에 해당하고
> 어디에도 표면화되지 않는다 — 실측 `analyze_file("a.php", "<?php echo 1; ?>")` →
> `unavailable=['phpstan'] incomplete=False uncovered=None`.
> 가시화가 실제로 붙는 것은 **유일 지원 분석기가 미조달인 언어**뿐이다 — Dart · PowerShell ·
> CSS/SCSS · Protobuf (실측 `analyze_file("a.dart", …)` → `uncovered='dart'`).

Tier 표의 정본은 레지스트리(`REGISTRY`)와 조달 계약이지 이 문서가 아니다. 이 문서를 읽는
가드는 **없으므로**(`grep -rn "language-coverage" scripts/ tests/ .github/` → 0건) 표가 낡았는지는
아래로 재파생해 대조한다 — 손으로 세지 않는다:

```bash
py -3 -c "import src.analyzer.io.static as S; from src.analyzer.pure.registry import REGISTRY; [print(a.name, a.name in S.PROVISIONED_ANALYZERS, sorted(getattr(a,'SUPPORTED_LANGUAGES',{'python'}))) for a in REGISTRY]"
```
