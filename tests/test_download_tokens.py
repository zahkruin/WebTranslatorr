"""
Tests for download token signing and verification.
"""

import time
from unittest.mock import patch

import pytest

from app.services.download_tokens import (
    build_download_content_url,
    build_download_url,
    sign_download,
    verify_download,
)


class TestDownloadTokens:
    def test_sign_and_verify_valid_token(self):
        with patch("app.services.download_tokens.settings") as mock_settings:
            mock_settings.API_KEY = "secret-key"
            mock_settings.DOWNLOAD_TOKEN_TTL = 3600
            token = sign_download("epublibre", "123", "epub")
            assert verify_download(token, "epublibre", "123", "epub")

    def test_verify_rejects_wrong_provider(self):
        with patch("app.services.download_tokens.settings") as mock_settings:
            mock_settings.API_KEY = "secret-key"
            mock_settings.DOWNLOAD_TOKEN_TTL = 3600
            token = sign_download("epublibre", "123", "epub")
            assert not verify_download(token, "lectulandia", "123", "epub")

    def test_verify_rejects_expired_token(self):
        with patch("app.services.download_tokens.settings") as mock_settings:
            mock_settings.API_KEY = "secret-key"
            token = sign_download("epublibre", "123", "epub", ttl_seconds=-10)
            assert not verify_download(token, "epublibre", "123", "epub")

    def test_build_download_url_includes_apikey(self):
        with patch("app.services.download_tokens.settings") as mock_settings:
            mock_settings.EXTERNAL_URL = "http://localhost:9811"
            mock_settings.API_KEY = "testkey"
            url = build_download_url("epublibre", "42", "epub")
            assert "apikey=testkey" in url
            assert "provider=epublibre" in url

    def test_build_download_content_url_includes_token(self):
        with patch("app.services.download_tokens.settings") as mock_settings:
            mock_settings.EXTERNAL_URL = "http://localhost:9811"
            mock_settings.API_KEY = "testkey"
            mock_settings.DOWNLOAD_TOKEN_TTL = 3600
            url = build_download_content_url("epublibre", "42", "epub")
            assert "token=" in url
            assert "provider=epublibre" in url
