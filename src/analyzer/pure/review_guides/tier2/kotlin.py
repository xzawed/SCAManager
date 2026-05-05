"""Kotlin review guide — Tier 2.

Phase 4 PR-14 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Kotlin review checklist
- **Null safety**: Minimize force `!!`; use `?.` / `?:`; correct `lateinit` use
- **Coroutines**: No `GlobalScope` → `CoroutineScope` + structured concurrency; `Dispatchers.IO` for I/O
- **Functional**: Extension functions, lambdas; pick `let` / `run` / `apply` / `also` / `with` correctly
- **Data classes**: `data class` with immutable fields (`val`); use `copy()`; auto-generated `equals` / `hashCode`
- **Sealed classes**: Use `sealed class` for exhaustive `when`; minimize `else` branch
- **Android**: Lifecycle-aware components; watch Context leaks; `viewModelScope` / `lifecycleScope`
- **Security**: No hardcoded secrets; validate `JavascriptInterface` input on WebViews
"""

COMPACT = "## Kotlin: avoid !!, no GlobalScope→structured, sealed class, data class val, Context leak"

FULL_KO = """\
## Kotlin 검토 기준
- **null 안전**: `!!` 강제 non-null 최소화, `?.`/`?:` 활용, `lateinit` 적절성
- **코루틴**: `GlobalScope` 금지 → `CoroutineScope` + 구조적 동시성, `Dispatchers.IO` I/O 전환
- **함수형**: 확장 함수, 람다, `let`/`run`/`apply`/`also`/`with` 적절 선택
- **데이터 클래스**: `data class` 불변 필드(`val`), `copy()` 활용, `equals`/`hashCode` 자동 생성
- **봉인 클래스**: `sealed class`로 when 완전성 보장, `else` 분기 최소화
- **Android**: Lifecycle 인식 컴포넌트, Context leak, `viewModelScope`/`lifecycleScope`
- **보안**: 하드코딩 시크릿 금지, Webview `JavascriptInterface` 입력 검증
"""

COMPACT_KO = "## Kotlin: !! 금지, GlobalScope 금지→구조적 동시성, sealed class, data class val, Context leak"

FULL_JA = """\
## Kotlin レビュー基準
- **null 安全**: `!!` 強制 non-null を最小化、`?.` / `?:` を活用、`lateinit` の適切性
- **コルーチン**: `GlobalScope` 禁止 → `CoroutineScope` + 構造化並行性、I/O は `Dispatchers.IO`
- **関数型**: 拡張関数、ラムダ、`let` / `run` / `apply` / `also` / `with` の適切な選択
- **データクラス**: `data class` 不変フィールド (`val`)、`copy()` 活用、`equals` / `hashCode` 自動生成
- **シールドクラス**: `sealed class` で `when` の網羅性保証、`else` ブランチを最小化
- **Android**: Lifecycle 対応コンポーネント、Context leak、`viewModelScope` / `lifecycleScope`
- **セキュリティ**: ハードコードされたシークレット禁止、WebView `JavascriptInterface` の入力検証
"""

COMPACT_JA = "## Kotlin: !! 禁止、GlobalScope 禁止→構造化並行、sealed class、data class val、Context leak"
