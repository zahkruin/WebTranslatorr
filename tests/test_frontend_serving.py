"""
Tests for serving static frontend files (index.html, CSS, JS).
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from pathlib import Path

from fastapi.testclient import TestClient
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


# ────────────────────────────────────────────────────────────────────────
# Helper: build a minimal app that only mounts static files
# ────────────────────────────────────────────────────────────────────────


STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def _create_frontend_app():
    """Create a minimal FastAPI app serving static files like create_app() does.

    This avoids the full lifespan machinery (init_db, _init_providers, etc.)
    so we can test file serving in isolation.
    """
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="frontend")
    return app


# ────────────────────────────────────────────────────────────────────────
# Tests
# ────────────────────────────────────────────────────────────────────────


class TestFrontendServing:
    """Tests for static file serving using TestClient."""

    def test_root_serves_index_html(self):
        """GET / should return HTML (index.html)."""
        app = _create_frontend_app()
        client = TestClient(app)

        response = client.get("/")
        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        assert "text/html" in content_type
        # Should contain opening HTML tag
        content = response.text.lower()
        assert "<html" in content or "<!doctype" in content

    def test_static_css_is_served(self):
        """GET /static/css/admin.css should return CSS."""
        app = _create_frontend_app()
        client = TestClient(app)

        response = client.get("/static/css/admin.css")
        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        assert "text/css" in content_type

    def test_static_js_is_served(self):
        """GET /static/js/admin.js should return JavaScript."""
        app = _create_frontend_app()
        client = TestClient(app)

        response = client.get("/static/js/admin.js")
        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        # JavaScript files can be served as text/javascript, application/javascript, or text/plain
        assert any(
            t in content_type
            for t in ("javascript", "text/plain", "application/octet-stream")
        )

    def test_nonexistent_static_file_returns_404(self):
        """GET /static/nonexistent.txt should return 404."""
        app = _create_frontend_app()
        client = TestClient(app)

        response = client.get("/static/nonexistent.txt")
        assert response.status_code == 404
