"""LaTeX review guide — Tier 3."""

FULL = """\
## LaTeX 검토 기준
- **패키지**: 불필요한 패키지 제거, 패키지 충돌 순서 주의(`hyperref` 마지막 로드)
- **참조**: `\\label{}`/`\\ref{}`/`\\cite{}` 미해결 참조 없음, BibTeX/BibLaTeX 일관성
- **수식**: `$...$` vs `\\(...\\)` 일관성, `equation` 환경 번호 필요 여부
- **이식성**: 절대 경로 이미지 금지 → 상대 경로, 이미지 형식(PDF/EPS/PNG) 컴파일러 호환
- **빌드**: `latexmk` 자동화, 임시 파일(`.aux`, `.log`) `.gitignore` 포함
- **보안**: `\\write18`(셸 탈출) 비활성화 권장(`-no-shell-escape`)
"""

COMPACT = "## LaTeX: hyperref 마지막, 미해결 참조 없음, 상대 경로 이미지, latexmk, shell-escape 비활성"
