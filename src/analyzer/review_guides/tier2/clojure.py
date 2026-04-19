"""Clojure review guide — Tier 2."""

FULL = """\
## Clojure 검토 기준
- **불변성**: 영속 자료구조 활용, `atom`/`ref`/`agent` 공유 상태 최소화
- **네임스페이스**: `require`/`use`/`import` 명시, `:refer :all` 금지
- **에러**: `ex-info`/`ex-data` 구조적 에러, `try/catch/finally`, `:cause` 체인
- **시퀀스**: lazy seq 무한 시퀀스 `doall`/`dorun` 실체화 필요 시점, 헤드 보유 누수
- **매크로**: 매크로 vs 함수 선택 기준, gensym `#` 위생 매크로, `defmacro` 최소화
- **동시성**: `future`/`promise`, STM `dosync`, core.async `go` 블록 채널 닫기
- **보안**: SQL `clojure.java.jdbc` 파라미터화, `read-string` → `edn/read-string`
"""

COMPACT = "## Clojure: 불변 자료구조, :refer :all 금지, lazy seq 헤드 누수, STM, edn/read-string"
