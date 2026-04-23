"""Lua review guide — Tier 2."""

FULL = """\
## Lua 검토 기준
- **전역 변수**: `local` 선언 필수 — 전역 누출은 디버깅 어렵고 성능 저하
- **nil 체크**: 함수 인자 nil 검증, table 키 접근 전 존재 여부 확인
- **에러 처리**: `pcall`/`xpcall` 감싸기, 에러 객체 타입 일관성
- **테이블**: 배열(1-indexed), 딕셔너리 혼용 주의, `#` 길이 연산자는 시퀀스에만 신뢰
- **모듈**: `return M` 패턴, `require` 결과 로컬 캐싱, 순환 require 위험
- **성능**: 문자열 연결 루프(`..`) → `table.concat`, 클로저 생성 반복 최소화
- **Nginx/OpenResty**: cosocket non-blocking, shared dict 경쟁 조건, phase 제약
"""

COMPACT = "## Lua: local 선언 필수, pcall 에러 처리, #은 시퀀스만, table.concat, require 캐싱"
