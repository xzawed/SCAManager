"""XML review guide — Tier 3.

Phase 4 PR-15 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## XML review checklist
- **Security**: XXE (XML External Entity) attacks — disable external DTD/entity in parsers
- **Schema**: Use XSD/DTD validation; explicit namespace declaration
- **Encoding**: `<?xml version="1.0" encoding="UTF-8"?>` declaration required
- **Parsing**: SAX (streaming) vs DOM (load all) — use SAX/StAX for large files
- **XSLT**: Don't run untrusted XSLT (can execute code); validate user-provided params
- **Namespaces**: Avoid prefix collisions; concentrate `xmlns:` declarations at the top
"""

COMPACT = "## XML: XXE defense, XSD validation, encoding declaration, SAX vs DOM, trusted XSLT only"

FULL_KO = """\
## XML 검토 기준
- **보안**: XXE(XML External Entity) 공격 — 외부 DTD/엔티티 파서 비활성화 필수
- **스키마**: XSD/DTD 검증 활용, namespace 명시적 선언
- **인코딩**: `<?xml version="1.0" encoding="UTF-8"?>` 선언 필수
- **파싱**: SAX(스트리밍) vs DOM(전체 로드) 선택 — 대용량은 SAX/StAX
- **XSLT**: 신뢰할 수 없는 XSLT 실행 금지(코드 실행 가능), 사용자 입력 파라미터 검증
- **네임스페이스**: 접두사 충돌 방지, `xmlns:` 선언 최상위 집중
"""

COMPACT_KO = "## XML: XXE 방어(외부 엔티티 비활성), XSD 검증, encoding 선언, SAX vs DOM, XSLT 신뢰 입력만"

FULL_JA = """\
## XML レビュー基準
- **セキュリティ**: XXE (XML External Entity) 攻撃 — パーサーで外部 DTD/エンティティを無効化必須
- **スキーマ**: XSD/DTD 検証を活用、namespace を明示的に宣言
- **エンコーディング**: `<?xml version="1.0" encoding="UTF-8"?>` 宣言必須
- **パース**: SAX (ストリーミング) vs DOM (全ロード) 選択 — 大容量は SAX/StAX
- **XSLT**: 信頼できない XSLT 実行禁止 (コード実行可能)、ユーザー入力パラメータを検証
- **ネームスペース**: プレフィックス衝突防止、`xmlns:` 宣言を最上位に集中
"""

COMPACT_JA = "## XML: XXE 防御、XSD 検証、encoding 宣言、SAX vs DOM、信頼 XSLT のみ"
