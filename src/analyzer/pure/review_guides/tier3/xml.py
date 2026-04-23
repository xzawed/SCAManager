"""XML review guide — Tier 3."""

FULL = """\
## XML 검토 기준
- **보안**: XXE(XML External Entity) 공격 — 외부 DTD/엔티티 파서 비활성화 필수
- **스키마**: XSD/DTD 검증 활용, namespace 명시적 선언
- **인코딩**: `<?xml version="1.0" encoding="UTF-8"?>` 선언 필수
- **파싱**: SAX(스트리밍) vs DOM(전체 로드) 선택 — 대용량은 SAX/StAX
- **XSLT**: 신뢰할 수 없는 XSLT 실행 금지(코드 실행 가능), 사용자 입력 파라미터 검증
- **네임스페이스**: 접두사 충돌 방지, `xmlns:` 선언 최상위 집중
"""

COMPACT = "## XML: XXE 방어(외부 엔티티 비활성), XSD 검증, encoding 선언, SAX vs DOM, XSLT 신뢰 입력만"
