"""HTML review guide — Tier 2."""

FULL = """\
## HTML 검토 기준
- **보안**: 사용자 입력 직접 삽입 금지(XSS), `<script src>` 외부 CDN SRI(`integrity`) 속성
- **접근성**: `alt` 속성 필수(이미지), `<label>` + `for`/`aria-label`, 시맨틱 태그(`<nav>`, `<main>`, `<button>`)
- **시맨틱**: `<div>` 남용 대신 시맨틱 요소, `<table>` 레이아웃 금지
- **성능**: 이미지 `width`/`height` 명시(CLS 방지), `loading="lazy"`, `<script defer>`/`async`
- **폼**: `<form method>` GET vs POST 선택, CSRF 토큰, `autocomplete` 속성
- **메타**: `<meta charset="UTF-8">`, viewport 설정, `lang` 속성 필수
"""

COMPACT = "## HTML: XSS 방지, alt/aria-label, 시맨틱 태그, SRI integrity, <script defer>, lang 속성"
