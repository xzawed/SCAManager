# 시크릿 유출 방지 (3계층)

로컬 훅(차단) → CI 스캔(탐지) → 유출 대응.

## 1) 로컬 훅 설치 — 새 머신 1회

```bash
py -3 -m pip install pre-commit
git config --unset-all core.hooksPath   # 설정돼 있으면 설치가 거부된다
py -3 -m pre_commit install             # 확인: py -3 scripts/check_precommit_installed.py
```

- `--hook-type` 을 붙이지 않는다. **맨 `install` 이 두 타입(pre-commit·commit-msg)을 함께 설치한다** —
  근거는 `.pre-commit-config.yaml:22` 의 `default_install_hook_types` 이고, `--hook-type` 은 그 값을 덮어 한 타입만 남긴다.
- `pre-push` 타입은 설치하지 않는다 — 리포 자체 push 게이트를 밀어낸다.

담당 축(`.pre-commit-config.yaml`):

| 축 | 훅 |
|---|---|
| 코드 diff | `gitleaks`(:30) · `check-secrets-in-diff`(:56) |
| 커밋 메시지 본문 | `check-commit-msg-secrets`(:38) — Telegram 토큰 형식 1종만 |
| `.env` staged | `check-env-not-staged`(:48) |

실제 값 대신 `<REDACTED>` 를 쓴다. 위 3축 밖(내부 URL+인증정보 등)은 기계가 못 막는다.

## 2) CI 탐지 — `.github/workflows/ci.yml` `secret-scan`

PR 은 `base..head`(:48-49), push 는 `before..after`(:70-71) **diff 범위만** 스캔한다(`--only-verified --exclude-detectors=lob`, :59·:81). 첫 push·force-push 는 skip 되고 과거 커밋은 안 본다.

이력 전수·알림은 손으로 확인한다:

```bash
docker run --rm -v "$(pwd):/pwd" trufflesecurity/trufflehog:latest \
  git file:///pwd --only-verified --exclude-detectors=lob
gh api repos/xzawed/SCAManager/secret-scanning/alerts \
  --jq '[.[] | select(.state=="open")] | length'
```

## 3) 유출 발견 시

1. 토큰 폐기 — Telegram `@BotFather` → `/revoke` · GitHub Settings → Developer settings → Tokens · console.anthropic.com → API Keys.
2. 재발급 후 Railway 환경변수 교체.
3. 범위 확인 — 커밋 **메시지까지** 스캔:
   `git log --all --format="%H%n%B" -p | grep -oE "[0-9]{8,12}:[A-Za-z0-9_-]{30,}"`
   (`--format=""` 나 `-S` 는 메시지를 건너뛴다. squash 된 PR 원본 커밋은 로컬에 없으니 `gh api repos/xzawed/SCAManager/commits/<sha> --jq .commit.message` 로 본다.)
4. 제거 — main 이력이면 `git filter-repo --message-callback` 으로 치환 후 `git push origin main --force-with-lease`(전원 재clone 공지). 도달 불가 커밋은 GitHub Support → "Data removal request" 에 저장소 URL·SHA·폐기 사실을 적어 요청한다.

## 관련

[env-vars.md](../reference/env-vars.md) · [railway.md](railway.md)
