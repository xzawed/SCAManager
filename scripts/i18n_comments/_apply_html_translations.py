#!/usr/bin/env python3
"""One-shot script to add English translations to Korean HTML developer comments."""
from pathlib import Path
import re

# Map: file_rel_path -> list of (korean_comment, english_comment)
# Replaces <!-- Korean --> with <!-- Korean --> (on same line, slash format) or two-line
TRANSLATIONS: dict[str, list[tuple[str, str]]] = {

"src/templates/analysis_detail.html": [
    ("<!-- 헤더 -->", "<!-- 헤더 / Header -->"),
    ("<!-- 이전/다음 내비게이션 -->", "<!-- 이전/다음 내비게이션 / Prev/Next navigation -->"),
    ("<!-- 메타 정보 -->", "<!-- 메타 정보 / Meta info -->"),
    ("<!-- 커밋 메시지 -->", "<!-- 커밋 메시지 / Commit message -->"),
    ("<!-- 점수 배너 -->", "<!-- 점수 배너 / Score banner -->"),
    ("<!-- Phase E.3 — 이 점수가 맞나요? thumbs up/down 피드백 -->",
     "<!-- Phase E.3 — 이 점수가 맞나요? thumbs up/down 피드백 / Is this score accurate? thumbs up/down feedback -->"),
    ("<!-- 점수 추이 트렌드 차트 -->", "<!-- 점수 추이 트렌드 차트 / Score trend chart -->"),
    ("<!-- AI 기본값 적용 경고 배너 -->", "<!-- AI 기본값 적용 경고 배너 / AI defaults applied warning banner -->"),
    ("<!-- 점수 상세 -->", "<!-- 점수 상세 / Score breakdown -->"),
    ("<!-- AI 요약 -->", "<!-- AI 요약 / AI summary -->"),
    ("<!-- 개선 제안 -->", "<!-- 개선 제안 / Improvement suggestions -->"),
    ("<!-- 카테고리별 피드백 -->", "<!-- 카테고리별 피드백 / Category feedback -->"),
    ("<!-- 파일별 피드백 -->", "<!-- 파일별 피드백 / Per-file feedback -->"),
    ("<!-- 정적 분석 이슈 -->", "<!-- 정적 분석 이슈 / Static analysis issues -->"),
    ("<!-- result는 있지만 모든 AI 필드가 비어있는 경우 -->",
     "<!-- result는 있지만 모든 AI 필드가 비어있는 경우 / result exists but all AI fields are empty -->"),
    ("<!-- result가 없는 경우 -->", "<!-- result가 없는 경우 / result is missing -->"),
    ("<!-- result도 없고 score도 없는 구버전 분석 -->",
     "<!-- result도 없고 score도 없는 구버전 분석 / legacy analysis with no result and no score -->"),
    ("<!-- score는 있지만 result가 없는 경우 -->",
     "<!-- score는 있지만 result가 없는 경우 / score exists but result is missing -->"),
],

"src/templates/repo_detail.html": [
    ("<!-- 헤더 -->", "<!-- 헤더 / Header -->"),
    ("<!-- 점수 차트 -->", "<!-- 점수 차트 / Score chart -->"),
    ("<!-- 분석 이력 -->", "<!-- 분석 이력 / Analysis history -->"),
    ("  <!-- 필터 바 -->", "  <!-- 필터 바 / Filter bar -->"),
],

"src/templates/settings.html": [
    ("  <!-- 저장 결과 토스트 -->", "  <!-- 저장 결과 토스트 / Save result toast -->"),
    ("  <!-- 헤더 -->", "  <!-- 헤더 / Header -->"),
    ("  <!-- Phase E.4 — Simple/Advanced 모드 토글 -->",
     "  <!-- Phase E.4 — Simple/Advanced 모드 토글 / Simple/Advanced mode toggle -->"),
    ("    <!-- ① 빠른 설정 (프리셋) -->", "    <!-- ① 빠른 설정 (프리셋) / Quick settings (presets) -->"),
    ("          <!-- 🌱 최소 -->", "          <!-- 🌱 최소 / Minimal -->"),
    ("          <!-- ⚙️ 표준 -->", "          <!-- ⚙️ 표준 / Standard -->"),
    ("          <!-- 🛡️ 엄격 -->", "          <!-- 🛡️ 엄격 / Strict -->"),
    ("    <!-- 고급 설정 (프리셋 외 세부 조정) -->",
     "    <!-- 고급 설정 (프리셋 외 세부 조정) / Advanced settings (fine-tuning beyond presets) -->"),
    ("      <!-- ② PR 들어왔을 때 -->", "      <!-- ② PR 들어왔을 때 / When a PR arrives -->"),
    ("          <!-- PR 코드리뷰 댓글 -->", "          <!-- PR 코드리뷰 댓글 / PR code review comment -->"),
    ("          <!-- 기준점 슬라이더 (disabled 시 숨김) -->",
     "          <!-- 기준점 슬라이더 (disabled 시 숨김) / Threshold slider (hidden when disabled) -->"),
    ("          <!-- semi-auto 안내 힌트 (Telegram Chat ID는 ④ 알림 채널에서 설정) -->",
     "          <!-- semi-auto 안내 힌트 (Telegram Chat ID는 ④ 알림 채널에서 설정) / semi-auto hint (Telegram Chat ID configured in ④ notification channels) -->"),
    ("          <!-- Merge 임계값 (auto_merge OFF 시 숨김) -->",
     "          <!-- Merge 임계값 (auto_merge OFF 시 숨김) / Merge threshold (hidden when auto_merge is OFF) -->"),
    ("          <!-- Auto-merge 실패 시 Issue 생성 (auto_merge OFF 시 숨김) -->",
     "          <!-- Auto-merge 실패 시 Issue 생성 (auto_merge OFF 시 숨김) / Create issue on auto-merge failure (hidden when auto_merge is OFF) -->"),
    ("      <!-- ③ 이벤트 후 피드백 -->", "      <!-- ③ 이벤트 후 피드백 / Post-event feedback -->"),
    ("    <!-- ④ 알림 채널 (항상 표시 — 고급 설정 아코디언 밖) -->",
     "    <!-- ④ 알림 채널 (항상 표시 — 고급 설정 아코디언 밖) / Notification channels (always visible — outside advanced settings accordion) -->"),
    ("  <!-- ⑤ 시스템 & 토큰 (CLI Hook + Webhook + Railway API 토큰 + 위험 구역 — 메인 form 외부) -->",
     "  <!-- ⑤ 시스템 & 토큰 (CLI Hook + Webhook + Railway API 토큰 + 위험 구역 — 메인 form 외부) / System & tokens (CLI Hook + Webhook + Railway API token + danger zone — outside main form) -->"),
    ("  <!-- ⑥ 위험 구역 (메인 form 외부, 페이지 최하단) -->",
     "  <!-- ⑥ 위험 구역 (메인 form 외부, 페이지 최하단) / Danger zone (outside main form, page bottom) -->"),
    ("  <!-- CLI Hook / Webhook 재등록 hidden form -->",
     "  <!-- CLI Hook / Webhook 재등록 hidden form / CLI Hook / Webhook re-registration hidden form -->"),
],

}


def apply_translations(base: Path, translations: dict[str, list[tuple[str, str]]]) -> int:
    total = 0
    for rel_path, pairs in translations.items():
        fp = base / rel_path
        if not fp.exists():
            print(f"SKIP (not found): {rel_path}")
            continue
        text = fp.read_text(encoding="utf-8")
        changed = False
        for korean, english in pairs:
            if korean in text and english not in text:
                text = text.replace(korean, english, 1)
                changed = True
                total += 1
        if changed:
            fp.write_text(text, encoding="utf-8")
            print(f"UPDATED: {rel_path}")
    return total


if __name__ == "__main__":
    base = Path("f:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager")
    n = apply_translations(base, TRANSLATIONS)
    print(f"\nTotal HTML translations applied: {n}")
