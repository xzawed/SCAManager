# SCAManager — 온프레미스 마이그레이션 가이드

이 문서는 SCAManager를 Railway + Supabase(클라우드) 환경에서 온프레미스 서버로 이전하는 절차를 안내합니다.

> SCAManager 코드 자체는 온프레미스 전환이 완료되어 있습니다 — `DB_FORCE_IPV4`, `DB_SSLMODE`, pool 설정 등 모든 연결 파라미터가 환경변수로 제어됩니다.

---

## 목차

1. [사전 준비사항](#1-사전-준비사항)
2. [PostgreSQL 설정](#2-postgresql-설정)
3. [환경변수 설정](#3-환경변수-설정)
4. [데이터 마이그레이션](#4-데이터-마이그레이션)
5. [애플리케이션 배포](#5-애플리케이션-배포)
6. [DB Failover 설정](#6-db-failover-설정)
7. [검증 체크리스트](#7-검증-체크리스트)
8. [트러블슈팅](#8-트러블슈팅)

---

## 1. 사전 준비사항

### 시스템 요구사항

| 항목 | 최소 버전 | 비고 |
|------|----------|------|
| PostgreSQL | 14+ | 로컬 또는 동일 네트워크 |
| Python | 3.12+ | 가상환경 권장 |
| 운영체제 | Ubuntu 22.04 / RHEL 9 / Debian 12 | 다른 배포판도 가능 |

### 시스템 패키지 설치

**Ubuntu / Debian:**

```bash
sudo apt install -y libpq-dev python3-dev build-essential
```

**RHEL / CentOS / Rocky Linux:**

```bash
sudo dnf install -y postgresql-devel python3-devel gcc
```

### psycopg2 교체 (권장)

온프레미스 프로덕션에서는 컴파일된 `psycopg2`가 더 안정적입니다.

```bash
# requirements.txt에서 psycopg2-binary 주석 처리 후 psycopg2 설치
pip install psycopg2
```

> `requirements.txt`에 이미 관련 주석이 포함되어 있습니다.

### GitHub OAuth App 콜백 URL 변경

Railway 도메인으로 등록된 OAuth App의 **Authorization callback URL**을 온프레미스 도메인으로 변경해야 합니다.

GitHub → **Settings → Developer settings → OAuth Apps → SCAManager** → Edit →  
`Authorization callback URL`: `https://your-domain/auth/callback`

---

## 2. PostgreSQL 설정

### DB 및 사용자 생성

```sql
-- postgres 슈퍼유저로 실행
CREATE DATABASE scamanager;
CREATE USER scamanager WITH PASSWORD 'your-strong-password';
GRANT ALL PRIVILEGES ON DATABASE scamanager TO scamanager;
\c scamanager
GRANT ALL ON SCHEMA public TO scamanager;
```

### pg_hba.conf 설정

로컬 연결 허용 (`/etc/postgresql/{version}/main/pg_hba.conf`):

```
# 로컬 소켓 (systemd 서비스 사용 시)
local   scamanager  scamanager                    md5

# TCP 로컬호스트 (Docker Compose 등 컨테이너 환경)
host    scamanager  scamanager  127.0.0.1/32      md5
host    scamanager  scamanager  ::1/128           md5
```

```bash
sudo systemctl restart postgresql
```

### 연결 확인

```bash
psql -U scamanager -d scamanager -h localhost -c "SELECT version();"
```

---

## 3. 환경변수 설정

### Railway → 온프레미스 변경점 비교

| 변수 | Railway 값 | 온프레미스 값 |
|------|-----------|-------------|
| `DATABASE_URL` | `postgresql://...supabase.co:5432/postgres` | `postgresql://scamanager:pass@localhost:5432/scamanager` |
| `DB_FORCE_IPV4` | `true` | `false` (또는 삭제) |
| `DB_SSLMODE` | (Supabase URL 자동 적용) | 빈 문자열 또는 `disable` |
| `APP_BASE_URL` | `https://xxx.up.railway.app` | `https://your-domain` |
| `SESSION_SECRET` | 기존 값 | **반드시 새로 생성** |

> `DATABASE_URL`에 `supabase.co`가 포함되면 `config.py`가 자동으로 `?sslmode=require`를 추가합니다. 온프레미스 URL에는 이 로직이 적용되지 않습니다.

### .env 파일 작성

```bash
cp .env.example .env
```

```ini
# === 필수 ===
DATABASE_URL=postgresql://scamanager:your-strong-password@localhost:5432/scamanager
TELEGRAM_BOT_TOKEN=123456789:AAF_your_bot_token_here
TELEGRAM_CHAT_ID=-100your_chat_id_here

# === GitHub OAuth (웹 UI 로그인 필수) ===
GITHUB_CLIENT_ID=Ov23li...
GITHUB_CLIENT_SECRET=github_...
SESSION_SECRET=<아래 명령으로 생성한 값>
APP_BASE_URL=https://your-domain

# === 선택 ===
ANTHROPIC_API_KEY=sk-ant-...   # AI 리뷰 (없으면 기본값 적용)
API_KEY=your-api-key            # REST API 인증 (없으면 인증 생략)

# === DB 연결 (온프레미스 기본값) ===
DB_SSLMODE=                    # 빈 값 = SSL 미적용
DB_FORCE_IPV4=false
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=1800
```

### SESSION_SECRET 생성

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

> `SESSION_SECRET`은 세션 쿠키 서명 키입니다. 32자 이상 랜덤 값을 사용하고 외부에 노출하지 마세요.

---

## 4. 데이터 마이그레이션

### 옵션 A — Supabase에서 데이터 이전 (기존 데이터 유지)

```bash
# Supabase에서 덤프 (Supabase 대시보드 → Project Settings → Database → Connection string)
PGPASSWORD=supabase-password pg_dump \
  -h db.xxxxx.supabase.co -U postgres -d postgres \
  --no-owner --no-acl --format=custom \
  -f scamanager_backup.dump

# 온프레미스로 복원
PGPASSWORD=your-strong-password pg_restore \
  -h localhost -U scamanager -d scamanager \
  --no-owner --role=scamanager \
  scamanager_backup.dump
```

복원 후 Alembic 스탬프 확인:

```bash
make migrate  # 또는: alembic upgrade head
```

### 옵션 B — 빈 DB로 새 시작 (히스토리 불필요)

앱 시작 시 `lifespan` 이벤트가 자동으로 마이그레이션을 실행합니다.

```bash
# 의존성 설치
pip install -r requirements.txt

# 마이그레이션 수동 실행 (앱 시작 시 자동 실행되므로 선택사항)
make migrate

# 개발 서버로 확인
make run
```

> `src/main.py`의 `_run_migrations()`가 앱 시작 시 30초 타임아웃으로 `alembic upgrade head`를 실행합니다.

---

## 5. 애플리케이션 배포

### 5-A. systemd 서비스

```ini
# /etc/systemd/system/scamanager.service
[Unit]
Description=SCAManager
After=network.target postgresql.service

[Service]
Type=simple
User=scamanager
WorkingDirectory=/opt/scamanager
EnvironmentFile=/opt/scamanager/.env
ExecStart=/opt/scamanager/venv/bin/uvicorn src.main:app \
    --host 0.0.0.0 --port 8000 --proxy-headers
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now scamanager
sudo systemctl status scamanager
```

### 5-B. nginx 리버스 프록시

```nginx
# /etc/nginx/sites-available/scamanager
server {
    listen 80;
    server_name your-domain;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name your-domain;

    ssl_certificate     /etc/letsencrypt/live/your-domain/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain/privkey.pem;

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/scamanager /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# SSL 인증서 발급 (Let's Encrypt)
sudo certbot --nginx -d your-domain
```

### 5-C. Docker Compose

```yaml
# docker-compose.yml
services:
  db:
    image: postgres:16
    restart: always
    environment:
      POSTGRES_DB: scamanager
      POSTGRES_USER: scamanager
      POSTGRES_PASSWORD: your-strong-password
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U scamanager"]
      interval: 10s
      timeout: 5s
      retries: 5

  app:
    build: .
    restart: always
    env_file: .env
    environment:
      DATABASE_URL: postgresql://scamanager:your-strong-password@db:5432/scamanager
      DB_FORCE_IPV4: "false"
      DB_SSLMODE: ""
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
    command: >
      uvicorn src.main:app
      --host 0.0.0.0 --port 8000 --proxy-headers

volumes:
  pgdata:
```

```bash
docker compose up -d
docker compose logs -f app
```

> Docker Compose 환경에서는 `DATABASE_URL`의 호스트를 `localhost` 대신 서비스명 `db`로 설정하세요.

---

## 6. DB Failover 설정

온프레미스 Primary DB 장애 시 Supabase 클라우드로 자동 전환하려면 `DATABASE_URL_FALLBACK`을 설정합니다.

### 개요

```
Primary 장애 감지 (OperationalError)
  → Fallback DB(Supabase)로 자동 전환
  → probe thread가 30초마다 Primary 복구 확인
  → Primary 복구 감지 시 자동 복귀
  → /health → {"status":"ok","active_db":"fallback"} (장애 중)
              {"status":"ok","active_db":"primary"}  (정상)
```

`DATABASE_URL_FALLBACK`이 비어 있으면 Failover 비활성 — 단일 엔진 모드로 동작합니다.

### .env 설정

```ini
# === DB Failover (온프레미스 장애 시 Supabase 자동 전환) ===
# Supabase 대시보드 → Project Settings → Database → Connection string
DATABASE_URL_FALLBACK=postgresql://postgres.xxxxxxxxxx:password@aws-1-ap-southeast-2.pooler.supabase.com:5432/postgres?sslmode=require
# Primary 복구 확인 주기 (초, 기본 30)
DB_FAILOVER_PROBE_INTERVAL=30
```

> Supabase URL에는 `?sslmode=require`가 필수입니다. `config.py`가 `supabase.co` 도메인을 감지해 자동 추가하므로, Supabase URL 끝에 직접 붙이지 않아도 됩니다.

### Supabase Fallback DB 준비

Supabase Fallback DB는 스키마가 동일해야 합니다. SCAManager 앱이 Supabase에 처음 연결될 때 마이그레이션이 자동 실행되지 않으므로, 미리 수동 마이그레이션을 실행해 두세요.

```bash
# DATABASE_URL을 Supabase URL로 임시 교체 후 마이그레이션
DATABASE_URL="postgresql://...supabase.co/postgres?sslmode=require" make migrate
```

### /health 모니터링

```bash
curl http://localhost:8000/health
# 정상: {"status":"ok","active_db":"primary"}
# 장애: {"status":"ok","active_db":"fallback"}
```

`active_db`가 `"fallback"`이면 Primary DB 장애 상태입니다. 모니터링 도구(Uptime Kuma, Prometheus 등)에서 이 필드를 감시해 경보를 설정하세요.

### 동작 방식 상세

| 상황 | 동작 |
|------|------|
| `DATABASE_URL_FALLBACK` 미설정 | 단일 엔진 모드 — Failover 없음 |
| Primary 정상 | `SessionLocal()` → Primary DB 세션 반환 |
| Primary `OperationalError` | 즉시 Fallback DB로 전환 |
| Fallback 중 Primary 복구 | probe thread가 `DB_FAILOVER_PROBE_INTERVAL`초 이내 감지 후 자동 복귀 |
| Fallback도 실패 | `OperationalError` 그대로 전파 (앱 레벨에서 500 응답) |

---

## 7. 검증 체크리스트

```
□ curl https://your-domain/health
      → {"status":"ok","active_db":"primary"} 응답 확인

□ GitHub OAuth 로그인
      → https://your-domain/login → GitHub으로 로그인

□ 리포지토리 추가 + Webhook 자동 생성
      → 대시보드 → + 리포 추가 → Webhook ping 응답 확인

□ 테스트 Push → Telegram 알림 수신
      → git commit --allow-empty -m "test" && git push

□ 대시보드 분석 이력 확인
      → https://your-domain → 리포 클릭 → 점수·등급 표시
```

---

## 8. 트러블슈팅

| 증상 | 원인 | 해결 방법 |
|------|------|----------|
| `psycopg2` 빌드 실패 | `libpq-dev` 미설치 | `apt install libpq-dev python3-dev build-essential` |
| `Connection refused` | PostgreSQL 미기동 또는 `pg_hba.conf` 설정 누락 | `systemctl status postgresql` / `pg_hba.conf` 확인 |
| SSL 관련 오류 | `DB_SSLMODE` 설정 불일치 | `.env`에서 `DB_SSLMODE=disable` 설정 |
| OAuth 콜백 불일치 | GitHub OAuth App 콜백 URL이 여전히 Railway 도메인 | GitHub OAuth App 설정에서 `Authorization callback URL` 변경 |
| 마이그레이션 타임아웃 | DB 연결 실패 (30초 제한) | `DATABASE_URL` 및 PostgreSQL 접근 권한 확인 (`src/main.py` lifespan) |
| `SESSION_SECRET` 경고 | `.env`에서 세션 시크릿 미설정 또는 기본값 사용 | `python -c "import secrets; print(secrets.token_hex(32))"` 로 새 값 생성 |
| Webhook ping 실패 | nginx `X-Forwarded-Proto` 미설정 → HTTP URL 등록 | nginx 설정에 `proxy_set_header X-Forwarded-Proto $scheme` 추가 + `APP_BASE_URL` 확인 |
| `DB_FORCE_IPV4=true` 오류 | Railway 전용 옵션이 온프레미스에서 DNS hang 유발 | `.env`에서 `DB_FORCE_IPV4=false` 로 변경 |
| `active_db: "fallback"` 지속 | Primary DB 연결 복구 안 됨 | `DATABASE_URL` 연결 확인 (포트 방화벽·PostgreSQL 기동 상태) |
| Supabase Fallback 연결 실패 | SSL 설정 불일치 | `DATABASE_URL_FALLBACK`에 `?sslmode=require` 포함 확인 |
