"""Kotlin review guide — Tier 2."""

FULL = """\
## Kotlin 검토 기준
- **null 안전**: `!!` 강제 non-null 최소화, `?.`/`?:` 활용, `lateinit` 적절성
- **코루틴**: `GlobalScope` 금지 → `CoroutineScope` + 구조적 동시성, `Dispatchers.IO` I/O 전환
- **함수형**: 확장 함수, 람다, `let`/`run`/`apply`/`also`/`with` 적절 선택
- **데이터 클래스**: `data class` 불변 필드(`val`), `copy()` 활용, `equals`/`hashCode` 자동 생성
- **봉인 클래스**: `sealed class`로 when 완전성 보장, `else` 분기 최소화
- **Android**: Lifecycle 인식 컴포넌트, Context leak, `viewModelScope`/`lifecycleScope`
- **보안**: 하드코딩 시크릿 금지, Webview `JavascriptInterface` 입력 검증
"""

COMPACT = "## Kotlin: !! 금지, GlobalScope 금지→구조적 동시성, sealed class, data class val, Context leak"
