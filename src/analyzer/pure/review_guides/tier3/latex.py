"""LaTeX review guide — Tier 3.

Phase 4 PR-15 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## LaTeX review checklist
- **Packages**: Remove unused packages; mind package conflict order (load `hyperref` last)
- **References**: No unresolved `\\label{}` / `\\ref{}` / `\\cite{}`; consistent BibTeX/BibLaTeX
- **Math**: Consistent `$...$` vs `\\(...\\)`; decide if `equation` numbering is needed
- **Portability**: No absolute image paths → relative paths; image formats (PDF/EPS/PNG) by compiler compat
- **Build**: Automate via `latexmk`; include `.aux`, `.log` in `.gitignore`
- **Security**: Disable `\\write18` (shell escape) — recommended `-no-shell-escape`
"""

COMPACT = "## LaTeX: hyperref last, no unresolved refs, relative image paths, latexmk, no shell-escape"

FULL_KO = """\
## LaTeX 검토 기준
- **패키지**: 불필요한 패키지 제거, 패키지 충돌 순서 주의(`hyperref` 마지막 로드)
- **참조**: `\\label{}`/`\\ref{}`/`\\cite{}` 미해결 참조 없음, BibTeX/BibLaTeX 일관성
- **수식**: `$...$` vs `\\(...\\)` 일관성, `equation` 환경 번호 필요 여부
- **이식성**: 절대 경로 이미지 금지 → 상대 경로, 이미지 형식(PDF/EPS/PNG) 컴파일러 호환
- **빌드**: `latexmk` 자동화, 임시 파일(`.aux`, `.log`) `.gitignore` 포함
- **보안**: `\\write18`(셸 탈출) 비활성화 권장(`-no-shell-escape`)
"""

COMPACT_KO = "## LaTeX: hyperref 마지막, 미해결 참조 없음, 상대 경로 이미지, latexmk, shell-escape 비활성"

FULL_JA = """\
## LaTeX レビュー基準
- **パッケージ**: 不要なパッケージを削除、パッケージ競合順序に注意 (`hyperref` を最後にロード)
- **参照**: `\\label{}` / `\\ref{}` / `\\cite{}` の未解決参照なし、BibTeX/BibLaTeX の一貫性
- **数式**: `$...$` vs `\\(...\\)` の一貫性、`equation` 環境の番号付けの必要性
- **可搬性**: 画像の絶対パス禁止 → 相対パス、画像形式 (PDF/EPS/PNG) のコンパイラ互換
- **ビルド**: `latexmk` で自動化、一時ファイル (`.aux`、`.log`) を `.gitignore` に含める
- **セキュリティ**: `\\write18` (シェルエスケープ) 無効化推奨 (`-no-shell-escape`)
"""

COMPACT_JA = "## LaTeX: hyperref 最後、未解決参照なし、相対パス画像、latexmk、shell-escape 無効"
