# SCAManager 운영 이미지 — Railway 가 저장소 루트의 이 파일을 자동 감지해 빌드한다.
# 분석기 버전의 정본은 여기다. CI(.github/workflows/ci.yml)는 같은 버전을 설치해야 한다
# — tests/unit/scripts/test_ci_provisions_the_contract.py 가 대조한다.
# Production image, auto-detected by Railway. Analyzer pins live here; CI must match them.

# Ubuntu 24.04 = 옛 Nixpacks 이미지와 CI 러너(ubuntu-latest)의 OS 다.
# shellcheck·cppcheck·ruby·go 가 운영·CI 와 같은 apt 버전으로 온다.
# Same OS as the former Nixpacks image and the CI runner, so apt analyzers match both.
FROM ubuntu:24.04

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# PATH 앞의 venv — pre-deploy `alembic upgrade head` 는 exec 형이라 PATH 로만 풀린다.
# VIRTUAL_ENV 는 solc-select 가 컴파일러를 venv 아래(/opt/venv/.solc-select)에 두게 한다
# — root 가 빌드 때 깔고 비-root 런타임이 읽는다.
# The venv leads PATH so the exec-form pre-deploy resolves alembic. VIRTUAL_ENV makes
# solc-select keep compilers under the venv, where the non-root runtime can read them.
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

# 시스템 패키지 — 옛 nixpacks.toml aptPkgs 전량 + python·curl·gnupg(NodeSource 키).
# apt 버전은 핀하지 않는다: 배포판(noble)이 고정이고, 핀은 보안 갱신을 막는다.
# 런타임 사용자(uid 10001)도 여기서 만든다 — 홈은 semgrep·rubocop·go 캐시용.
# System packages: the former aptPkgs plus python/curl/gnupg. The release pins the versions.
# The runtime user is created here too; its home holds the tools' caches.
# hadolint ignore=DL3008
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl gnupg unzip \
      python3.12 python3.12-venv python3.12-dev \
      shellcheck cppcheck ruby-full golang-go build-essential libyaml-dev \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 app

# Node 20 — NodeSource 공식 저장소(서명 키 검증). CI 의 setup-node 와 같은 major.
# Node 20 from the official NodeSource repo (signed); same major as CI.
# hadolint ignore=DL3008
RUN mkdir -p /etc/apt/keyrings \
 && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
    | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
 && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
    > /etc/apt/sources.list.d/nodesource.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/*

# 분석기 바이너리 — 전부 버전 핀. 🔴 실패를 `|| echo` 로 삼키지 않는다: 삼킨 실패는 이
# 레이어에 **캐시돼** 이후 빌드마다 도구 없는 이미지가 나온다. 빌드가 실패하면 Railway 는
# 이전 배포를 그대로 서비스한다.
# Pinned analyzers. Failures are not swallowed: a swallowed failure would be cached in this
# layer and every later build would ship without the tool. A failed build keeps the old deploy.
# hadolint ignore=DL3016
RUN gem install rubocop-ast -v 1.36.2 --no-document --bindir /usr/bin \
 && gem install rubocop -v 1.57.2 --no-document --bindir /usr/bin \
 && curl -sSfL --retry 3 https://raw.githubusercontent.com/golangci/golangci-lint/master/install.sh \
    | sh -s -- -b /usr/bin v1.55.2 \
 && curl -sSfL --retry 3 https://github.com/hadolint/hadolint/releases/download/v2.15.1/hadolint-Linux-x86_64 \
    -o /usr/bin/hadolint \
 && chmod +x /usr/bin/hadolint \
 && curl -sSfL --retry 3 https://github.com/pinterest/ktlint/releases/download/1.8.0/ktlint \
    -o /usr/bin/ktlint \
 && chmod +x /usr/bin/ktlint \
 && curl -sSfL --retry 3 https://github.com/terraform-linters/tflint/releases/download/v0.64.0/tflint_linux_amd64.zip \
    -o /tmp/tflint.zip \
 && unzip -o /tmp/tflint.zip -d /usr/bin/ \
 && chmod +x /usr/bin/tflint \
 && rm /tmp/tflint.zip \
 && npm install -g eslint@9 @typescript-eslint/parser @typescript-eslint/eslint-plugin \
 && npm install -g 'typescript@>=6.0.3 <6.1.0' \
 && npm install -g eslint-plugin-react eslint-plugin-react-hooks \
 && npm cache clean --force

WORKDIR /app

# Python 의존성 — requirements.txt 만 먼저 복사해 코드 변경이 이 레이어를 깨지 않게 한다.
# Python deps first, so code-only changes reuse this layer.
COPY requirements.txt ./
RUN python3.12 -m venv /opt/venv \
 && pip install --retries 5 --timeout 60 -r requirements.txt

# slither 가 Solidity 를 컴파일할 solc — solc-select 는 slither-analyzer 의 전이 의존이다.
# The solc compiler slither needs; solc-select arrives transitively with slither-analyzer.
RUN solc-select install 0.8.20 \
 && solc-select use 0.8.20

# npm 의존성 — Tailwind 빌드 + 런타임 eslint 분석기 설정이 리포 node_modules 를 읽는다.
# `--ignore-scripts` = 설치 스크립트 미실행(공급망 hardening, CI 와 같다).
# Tailwind build + the runtime eslint config both read the repo node_modules.
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts \
 && npm cache clean --force

# Tailwind 빌드 뒤 🔴 조달 계약 확인 — `PROVISIONED_ANALYZERS` 의 바이너리가 없으면 빌드 실패다.
# 목록을 여기 옮겨 적지 않고 코드에서 읽는다(런타임 판정 `_binary_is_absent` 와 같은 함수).
# Build the CSS, then fail the build if any contracted analyzer binary is missing (runtime's check).
COPY . .
RUN npm run build \
 && python -c "import sys; from src.analyzer.io.static import PROVISIONED_ANALYZERS as P, _binary_is_absent as absent; missing = sorted(t for t in P if absent(t)); print('provisioned analyzers missing:', missing or 'none', '/', len(P)); sys.exit(1 if missing else 0)"

# 비-root 실행 — 분석기는 PR 의 신뢰할 수 없는 코드를 돈다.
# Run as non-root: analyzers process untrusted PR code.
USER 10001:10001

EXPOSE 8000

# 🔴 `sh -c` 로 감싼다 — `$PORT` 는 셸만 확장한다(exec 형 단독은 글자 그대로 넘긴다). `exec` 로
# uvicorn 이 PID 1 이 되어 SIGTERM 을 직접 받는다. PORT 가 없으면(로컬 실행) 8000.
# Wrapped in `sh -c` because only a shell expands $PORT; `exec` makes uvicorn PID 1.
CMD ["/bin/sh", "-c", "exec uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
