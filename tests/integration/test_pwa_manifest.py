"""PWA manifest + icon serving 회귀 가드 (Cycle 81 PR-A — 영역 🅑 모바일 진입).

5+1 cross-verify (관점 🅑) PR-A 의무:
- manifest.json 200 응답 + JSON valid
- icon-192.svg + icon-512.svg 200 응답 + SVG valid
- base.html PWA 헤더 (manifest link + theme-color + apple-touch-icon)
- start_url + scope + display 정합성
"""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from src.main import app


def test_manifest_serves_200():
    """GET /static/manifest.json — 200 응답."""
    with TestClient(app) as c:
        response = c.get("/static/manifest.json")
        assert response.status_code == 200


def test_manifest_is_valid_json():
    """manifest.json = valid JSON 구조 + 필수 필드 모두 존재."""
    with TestClient(app) as c:
        response = c.get("/static/manifest.json")
        data = json.loads(response.text)
        # PWA install criteria — 필수 필드
        assert "name" in data
        assert "short_name" in data
        assert "start_url" in data
        assert "display" in data
        assert "icons" in data
        # SCAManager 정합
        assert data["name"].startswith("SCAManager")
        assert data["start_url"] == "/"
        assert data["display"] == "standalone"
        assert data["scope"] == "/"


def test_manifest_includes_192_and_512_icons():
    """manifest.icons = 192 + 512 (PWA install 의무 사이즈)."""
    with TestClient(app) as c:
        data = json.loads(c.get("/static/manifest.json").text)
        sizes = {icon["sizes"] for icon in data["icons"]}
        assert "192x192" in sizes
        assert "512x512" in sizes


def test_manifest_icons_have_maskable_purpose():
    """icons.purpose = "any maskable" (PWA maskable 호환)."""
    with TestClient(app) as c:
        data = json.loads(c.get("/static/manifest.json").text)
        for icon in data["icons"]:
            assert "maskable" in icon.get("purpose", ""), \
                f"icon {icon['src']} maskable 부재"


def test_icon_192_svg_serves_200():
    """GET /static/icons/icon-192.svg — 200 응답 + SVG content."""
    with TestClient(app) as c:
        response = c.get("/static/icons/icon-192.svg")
        assert response.status_code == 200
        assert "<svg" in response.text
        assert "viewBox" in response.text


def test_icon_512_svg_serves_200():
    """GET /static/icons/icon-512.svg — 200 응답 + SVG content."""
    with TestClient(app) as c:
        response = c.get("/static/icons/icon-512.svg")
        assert response.status_code == 200
        assert "<svg" in response.text
        assert "viewBox" in response.text


def test_base_html_includes_manifest_link():
    """base.html (overview 페이지 응답) = manifest link + theme-color + apple-touch-icon 헤더 포함."""
    with TestClient(app) as c:
        response = c.get("/")
        # 비로그인 시 /login redirect — login 페이지도 base.html 상속 = PWA 헤더 동일
        # Follow redirects to ensure base.html headers present
        if response.status_code == 302:
            response = c.get(response.headers["location"])
        assert response.status_code == 200
        # PWA 핵심 헤더 3종
        assert '<link rel="manifest" href="/static/manifest.json">' in response.text
        assert 'theme-color' in response.text
        assert '/static/icons/icon-192.svg' in response.text
