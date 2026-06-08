"""
Tests for ScraperResponse wrapper dataclass.
"""

import pytest
from unittest.mock import MagicMock

from app.scraping.http_client import ScraperResponse


class TestScraperResponse:
    """Tests for ScraperResponse creation and attribute access."""

    def test_create_directly(self):
        resp = ScraperResponse(
            status_code=200,
            text="<html>ok</html>",
            content=b"<html>ok</html>",
            headers={"content-type": "text/html"},
            url="https://example.com/page",
        )
        assert resp.status_code == 200
        assert resp.text == "<html>ok</html>"
        assert resp.content == b"<html>ok</html>"
        assert resp.headers == {"content-type": "text/html"}
        assert resp.url == "https://example.com/page"

    def test_from_requests_response(self):
        mock_req = MagicMock()
        mock_req.status_code = 200
        mock_req.text = "<html>ok</html>"
        mock_req.content = b"<html>ok</html>"
        mock_req.headers = {"Content-Type": "text/html"}
        mock_req.url = "https://example.com/page?q=test"

        resp = ScraperResponse.from_requests_response(mock_req)

        assert resp.status_code == 200
        assert resp.text == "<html>ok</html>"
        assert resp.content == b"<html>ok</html>"
        assert resp.headers == {"Content-Type": "text/html"}
        assert resp.url == "https://example.com/page?q=test"

    def test_default_values(self):
        resp = ScraperResponse(
            status_code=404,
            text="",
            content=b"",
            headers={},
            url="https://example.com/notfound",
        )
        assert resp.status_code == 404
        assert resp.text == ""
        assert resp.content == b""
        assert resp.headers == {}
        assert resp.url == "https://example.com/notfound"

    def test_repr(self):
        resp = ScraperResponse(
            status_code=200,
            text="content",
            content=b"content",
            headers={},
            url="https://example.com",
        )
        r = repr(resp)
        assert "ScraperResponse" in r
        assert "200" in r
        assert "example.com" in r
