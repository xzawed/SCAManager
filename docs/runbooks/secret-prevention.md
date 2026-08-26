# 시크릿 유출 방지

## 로컬 훅(새 머신 1회)

```bash
py -3 -m pip install pre-commit
git config --unset-all core.hooksPath  # 설정돼 있으면 설치 거부
py -3 -m pre_commit install  # 확인: check_precommit_installed.py
```

**맨 `install` 이 두 타입(pre-commit·commit-msg)을 함께 설치한다** — `.pre-commit-config.yaml::default_install_hook_types:` `default_install_hook_types`. `--hook-type` 은 그 값을 덮어 한 타입만 남긴다. `pre-push` 타입은 리포 게이트를 밀어내 금지.

같은 파일의 축: 코드 diff `.pre-commit-config.yaml::id: gitleaks`·`.pre-commit-config.yaml::id: check-secrets-in-diff` / 커밋 메시지 `.pre-commit-config.yaml::id: check-commit-msg-secrets`(Telegram 1종만) / `.env` staged `.pre-commit-config.yaml::id: check-env-not-staged`. 3축 밖(내부 URL+인증정보)은 못 막는다.

## CI `ci.yml` secret-scan

PR 은 `base..head`(`.github/workflows/ci.yml::base: ${{ github.event.pull_request.base.sha }}`) · push 는 `before..after`(`.github/workflows/ci.yml::base: ${{ github.event.before }}`) **diff 범위만**(`--only-verified --exclude-detectors=lob`). 첫 push·force-push skip, 과거 커밋 미검사 — 전수는 손으로 trufflehog `git file:///pwd`(동일 플래그) · `gh api .../secret-scanning/alerts`.

## 유출 시

1. 폐기·재발급 → Railway 환경변수 교체(Telegram `@BotFather` `/revoke` · GitHub Tokens · Anthropic Console).
2. 범위는 커밋 **메시지까지**: `git log --all --format="%H%n%B" -p | grep -oE "[0-9]{8,12}:[A-Za-z0-9_-]{30,}"` (`--format=""`·`-S` 는 메시지 건너뜀). squash 원본은 로컬에 없다: `gh api .../commits/<sha> --jq .commit.message`.
3. 제거 — main 이력은 `git filter-repo --message-callback` 후 `push --force-with-lease`(재clone 공지). 도달 불가 커밋은 GitHub Support "Data removal request"(URL·SHA).
