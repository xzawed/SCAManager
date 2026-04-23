"""Haskell review guide — Tier 2."""

FULL = """\
## Haskell 검토 기준
- **타입**: 명시적 타입 시그니처(공개 함수 필수), `Maybe`/`Either` 에러 처리
- **순수성**: IO 부작용 최소화 — 순수 함수와 IO 분리, `unsafePerformIO` 금지
- **lazy 평가**: 공간 누수(space leak) 주의, `seq`/`deepseq`/`!` 엄격 평가
- **모나드**: `do` 블록 가독성, 모나드 스택 복잡도 경계, `liftIO` 적절성
- **임포트**: qualified import 권장(`import qualified Data.Map as Map`), 와일드카드 import 주의
- **GHC 확장**: 필요한 확장만 명시(`{-# LANGUAGE ... #-}`), `OverloadedStrings` 기본
"""

COMPACT = "## Haskell: 타입 시그니처 필수, Maybe/Either, IO 분리, lazy space leak, qualified import"
