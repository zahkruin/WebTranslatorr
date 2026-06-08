"""
Tests for WordPress REST API client (wp_api_client.py).

Covers: search (JSON parsing, post→SearchResult mapping, pagination),
get_download_url (content link extraction, Yoast parsing),
_parse_title_author (all separators), get_capabilities_search.
"""
import json
import pytest
from unittest.mock import AsyncMock

from app.scraping.wp_api_client import WordPressApiClient
from app.core.models import SearchResult
from app.scraping.http_client import ScraperResponse

# ── Test Data ─────────────────────────────────────────────────────────

WP_POST = {
    "id": 21172,
    "date": "2026-04-19T08:42:37",
    "date_gmt": "2026-04-19T08:42:37",
    "slug": "el-capitan-alatriste-perez-reverte",
    "link": "https://epubflix1.com/el-capitan-alatriste/",
    "title": {"rendered": "El capitán Alatriste | Arturo Pérez-Reverte"},
    "content": {"rendered": "<p>Libro de aventuras en el Siglo de Oro.</p>"},
    "excerpt": {"rendered": "<p>Aventuras del capitán Alatriste en el Madrid del XVII</p>"},
    "type": "post",
    "categories": [4],
    "tags": [12],
    "yoast_head_json": {
        "og_title": "El capitán Alatriste",
        "og_description": "Las aventuras del capitán Alatriste",
        "og_image": [{"url": "https://epubflix1.com/cover.jpg"}],
    },
    "_embedded": {
        "wp:term": [[
            {"id": 4, "name": "Novela histórica", "slug": "novela-historica"},
            {"id": 7, "name": "Aventuras", "slug": "aventuras"},
            {"id": 99, "name": "Uncategorized", "slug": "uncategorized"},
        ]]
    }
}

WP_POST_MINIMAL = {
    "id": 1,
    "title": {"rendered": "Minimal Book"},
    "link": "/minimal-book/",
    "type": "post",
}

WP_POST_EN_DASH = {
    "id": 2,
    "title": {"rendered": "Book Title – Author Name"},
    "link": "https://site.com/book/",
    "type": "post",
}

WP_POST_EM_DASH = {
    "id": 3,
    "title": {"rendered": "Book Title — Author Name"},
    "link": "https://site.com/book2/",
    "type": "post",
}

WP_POST_HYPHEN = {
    "id": 4,
    "title": {"rendered": "Book Title - Author Name"},
    "link": "https://site.com/book3/",
    "type": "post",
}

WP_POST_NO_AUTHOR = {
    "id": 5,
    "title": {"rendered": "Just a Book Title"},
    "link": "https://site.com/book4/",
    "type": "post",
}

WP_POST_WITH_ISBN = {
    "id": 6,
    "date": "2026-01-15T10:00:00",
    "slug": "test-book",
    "link": "https://site.com/test-book/",
    "title": {"rendered": "Test Book | Author"},
    "content": {"rendered": "<p>Content</p>"},
    "excerpt": {"rendered": "<p>Test excerpt</p>"},
    "type": "post",
    "yoast_head_json": {
        "og_description": "Test description",
        "schema": {
            "@graph": [
                {"@type": "WebSite", "name": "Site"},
                {"@type": "Book", "isbn": "978-3-16-148410-0"},
            ]
        }
    },
    "_embedded": {"wp:term": [[
        {"id": 8, "name": "Sin categoría", "slug": "sin-categoria"},
        {"id": 9, "name": "Historia", "slug": "historia"},
    ]]}
}

# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def mock_http():
    client = AsyncMock()
    client.get = AsyncMock()
    return client

@pytest.fixture
def wp_client(mock_http):
    return WordPressApiClient(
        http_client=mock_http,
        base_url="https://epubflix1.com",
        provider_id="test-wp",
    )

# ── search() Tests ────────────────────────────────────────────────────

class TestWpApiSearch:

    @pytest.mark.asyncio
    async def test_search_returns_results(self, wp_client, mock_http):
        mock_http.get.return_value = ScraperResponse(
            200, json.dumps([WP_POST]), b"", {}, "url"
        )
        results = await wp_client.search("quijote", limit=10)
        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].title == "El capitán Alatriste"
        assert results[0].author == "Arturo Pérez-Reverte"

    @pytest.mark.asyncio
    async def test_search_parses_excerpt_as_description(self, wp_client, mock_http):
        mock_http.get.return_value = ScraperResponse(
            200, json.dumps([WP_POST]), b"", {}, "url"
        )
        results = await wp_client.search("quijote")
        assert "Aventuras del capitán Alatriste" in results[0].description

    @pytest.mark.asyncio
    async def test_search_extracts_cover_url(self, wp_client, mock_http):
        mock_http.get.return_value = ScraperResponse(
            200, json.dumps([WP_POST]), b"", {}, "url"
        )
        results = await wp_client.search("quijote")
        assert results[0].extra_attrs["cover_url"] == "https://epubflix1.com/cover.jpg"

    @pytest.mark.asyncio
    async def test_search_extracts_genres(self, wp_client, mock_http):
        mock_http.get.return_value = ScraperResponse(
            200, json.dumps([WP_POST]), b"", {}, "url"
        )
        results = await wp_client.search("quijote")
        assert "Novela histórica" in results[0].extra_attrs["genre"]

    @pytest.mark.asyncio
    async def test_search_empty_query(self, wp_client):
        results = await wp_client.search("")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_api_error(self, wp_client, mock_http):
        mock_http.get.side_effect = Exception("API error")
        results = await wp_client.search("quijote")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_handles_non_list_response(self, wp_client, mock_http):
        """API returns a dict instead of a list."""
        mock_http.get.return_value = ScraperResponse(
            200, json.dumps({"error": "not found"}), b"", {}, "url"
        )
        results = await wp_client.search("quijote")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_extracts_isbn(self, wp_client, mock_http):
        mock_http.get.return_value = ScraperResponse(
            200, json.dumps([WP_POST_WITH_ISBN]), b"", {}, "url"
        )
        results = await wp_client.search("test")
        assert results[0].extra_attrs.get("isbn") == "978-3-16-148410-0"

    @pytest.mark.asyncio
    async def test_search_minimal_post(self, wp_client, mock_http):
        """Post with minimal fields."""
        mock_http.get.return_value = ScraperResponse(
            200, json.dumps([WP_POST_MINIMAL]), b"", {}, "url"
        )
        results = await wp_client.search("minimal")
        assert len(results) == 1
        assert results[0].title == "Minimal Book"
        assert results[0].guid == "test-wp-1"

# ── get_download_url() Tests ──────────────────────────────────────────

class TestWpApiDownload:

    @pytest.mark.asyncio
    async def test_get_download_url_yoast_fallback(self, wp_client, mock_http):
        """When content has no download links, fallback to Yoast og_url."""
        mock_http.get.return_value = ScraperResponse(
            200, json.dumps({**WP_POST, "yoast_head_json": {"og_url": "https://site.com/dl"}}),
            b"", {}, "url"
        )
        url = await wp_client.get_download_url(21172)
        assert url == "https://site.com/dl"

    @pytest.mark.asyncio
    async def test_get_download_url_no_links(self, wp_client, mock_http):
        mock_http.get.return_value = ScraperResponse(
            200, json.dumps(WP_POST_MINIMAL), b"", {}, "url"
        )
        url = await wp_client.get_download_url(1)
        assert url is None

    @pytest.mark.asyncio
    async def test_get_download_url_api_error(self, wp_client, mock_http):
        mock_http.get.side_effect = Exception("Error")
        url = await wp_client.get_download_url(1)
        assert url is None

# ── _parse_title_author() Tests ──────────────────────────────────────

class TestParseTitleAuthor:

    def test_pipe_separator(self):
        t, a = WordPressApiClient._parse_title_author("Book Title | Author Name")
        assert t == "Book Title"
        assert a == "Author Name"

    def test_emdash_separator(self):
        t, a = WordPressApiClient._parse_title_author("Book Title — Author Name")
        assert t == "Book Title"
        assert a == "Author Name"

    def test_endash_separator(self):
        t, a = WordPressApiClient._parse_title_author("Book Title – Author Name")
        assert t == "Book Title"
        assert a == "Author Name"

    def test_hyphen_separator(self):
        t, a = WordPressApiClient._parse_title_author("Book Title - Author Name")
        assert t == "Book Title"
        assert a == "Author Name"

    def test_no_separator(self):
        t, a = WordPressApiClient._parse_title_author("Just a Book")
        assert t == "Just a Book"
        assert a is None

    def test_empty_string(self):
        t, a = WordPressApiClient._parse_title_author("")
        assert t == ""

    def test_multiple_pipes(self):
        """Only the last pipe separates author."""
        t, a = WordPressApiClient._parse_title_author(
            "Series Name | Book Title | Author"
        )
        assert t == "Series Name | Book Title"
        assert a == "Author"

# ── Capabilities Test ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_capabilities_search(wp_client, mock_http):
    mock_http.get.return_value = ScraperResponse(
        200, json.dumps([WP_POST]), b"", {}, "url"
    )
    result = await wp_client.get_capabilities_search()
    assert result is True

@pytest.mark.asyncio
async def test_get_capabilities_search_empty(wp_client, mock_http):
    mock_http.get.return_value = ScraperResponse(
        200, "[]", b"", {}, "url"
    )
    result = await wp_client.get_capabilities_search()
    assert result is False
