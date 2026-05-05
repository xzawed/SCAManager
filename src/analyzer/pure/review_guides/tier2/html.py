"""HTML review guide — Tier 2.

Phase 4 PR-14 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## HTML review checklist
- **Security**: Don't inject raw user input (XSS); add SRI (`integrity`) on external CDN `<script src>`
- **Accessibility**: `alt` required on images; `<label>` + `for` / `aria-label`; semantic tags (`<nav>`, `<main>`, `<button>`)
- **Semantics**: Use semantic elements instead of overusing `<div>`; no `<table>` for layout
- **Performance**: Set image `width` / `height` (prevent CLS); `loading="lazy"`; `<script defer>` / `async`
- **Forms**: Choose `<form method>` GET vs POST; CSRF tokens; `autocomplete` attribute
- **Meta**: `<meta charset="UTF-8">`, viewport, `lang` attribute required
"""

COMPACT = "## HTML: XSS prevention, alt/aria-label, semantic tags, SRI integrity, <script defer>, lang"

FULL_KO = """\
## HTML 검토 기준
- **보안**: 사용자 입력 직접 삽입 금지(XSS), `<script src>` 외부 CDN SRI(`integrity`) 속성
- **접근성**: `alt` 속성 필수(이미지), `<label>` + `for`/`aria-label`, 시맨틱 태그(`<nav>`, `<main>`, `<button>`)
- **시맨틱**: `<div>` 남용 대신 시맨틱 요소, `<table>` 레이아웃 금지
- **성능**: 이미지 `width`/`height` 명시(CLS 방지), `loading="lazy"`, `<script defer>`/`async`
- **폼**: `<form method>` GET vs POST 선택, CSRF 토큰, `autocomplete` 속성
- **메타**: `<meta charset="UTF-8">`, viewport 설정, `lang` 속성 필수
"""

COMPACT_KO = "## HTML: XSS 방지, alt/aria-label, 시맨틱 태그, SRI integrity, <script defer>, lang 속성"

FULL_JA = """\
## HTML レビュー基準
- **セキュリティ**: ユーザー入力の直接挿入禁止 (XSS)、外部 CDN `<script src>` には SRI (`integrity`) 属性
- **アクセシビリティ**: 画像に `alt` 必須、`<label>` + `for` / `aria-label`、セマンティックタグ (`<nav>`、`<main>`、`<button>`)
- **セマンティクス**: `<div>` の濫用ではなくセマンティック要素、レイアウト目的の `<table>` 禁止
- **パフォーマンス**: 画像 `width` / `height` 明示 (CLS 防止)、`loading="lazy"`、`<script defer>` / `async`
- **フォーム**: `<form method>` GET vs POST 選択、CSRF トークン、`autocomplete` 属性
- **メタ**: `<meta charset="UTF-8">`、viewport 設定、`lang` 属性必須
"""

COMPACT_JA = "## HTML: XSS 防止、alt/aria-label、セマンティックタグ、SRI integrity、<script defer>、lang 属性"
