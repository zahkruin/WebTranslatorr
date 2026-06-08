"""
Tests for Library Genesis provider (libgen.py).

Covers: search (table parsing, MD5 extraction, size parsing),
get_download_url (multi-strategy), _parse_size, edge cases.
"""
import pytest
from unittest.mock import AsyncMock
from datetime import datetime

from app.providers.books.libgen import LibgenProvider
from app.core.models import SearchResult
from app.scraping.http_client import ScraperResponse

# ── HTML Fixtures ─────────────────────────────────────────────────────

SEARCH_HTML = """<html><body>
<table class="c">
<tr><th>ID</th><th>Authors</th><th>Title</th><th>Edition</th><th>Year</th><th>Pages</th><th>Size</th><th>Ext</th><th>Mirror</th><th>Edit</th></tr>
<tr>
<td>1</td>
<td>Cervantes, Miguel de</td>
<td><a href="book/index.php?md5=a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4">Don Quijote de la Mancha</a></td>
<td>1st</td><td>1605</td><td>500</td><td>2.5 MB</td><td>epub</td><td></td><td></td>
</tr>
<tr>
<td>2</td>
<td>Tolkien, J.R.R.</td>
<td><a href="book/index.php?md5=b2c3d4e5f6a7b2c3d4e5f6a7b2c3d4e5">El Señor de los Anillos</a></td>
<td>2nd</td><td>1954</td><td>1200</td><td>5.1 MB</td><td>pdf</td><td></td><td></td>
</tr>
</table>
</body></html>"""

SEARCH_HTML_EMPTY = """<html><body><p>No results found</p></body></html>"""

SEARCH_HTML_NO_TABLE = """<html><body><p>Some other page</p></body></html>"""

SEARCH_HTML_SHORT_ROW = """<html><body>
<table class="c">
<tr><th>ID</th></tr>
<tr><td>1</td><td>Author</td></tr>
</table>
</body></html>"""

SEARCH_HTML_NO_MD5 = """<html><body>
<table class="c">
<tr><th>ID</th><th>Authors</th><th>Title</th><th>Ed</th><th>Year</th><th>Pages</th><th>Size</th><th>Ext</th><th>M</th><th>E</th></tr>
<tr>
<td>1</td><td>Author Name</td><td>No Link Title</td><td>1</td><td>2020</td><td>100</td><td>1 MB</td><td>epub</td><td></td><td></td>
</tr>
</table>
</body></html>"""

DETAIL_HTML_LIBGEN = """<html><body>
<a href="/main/a1/a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4">Download</a>
<a href="https://libgen.ee/get.php?md5=a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4">Libgen Download</a>
</body></html>"""

DETAIL_HTML_MIRROR = """<html><body>
<a href="/download/mirror123">epub Download</a>
</body></html>"""

DETAIL_HTML_CLOUDFLARE = """<html><body>
<a href="https://cloudflare-ipfs.com/ipfs/hash123">IPFS Download</a>
</body></html>"""

DETAIL_HTML_NO_LINKS = """<html><body><p>No download links available</p></body></html>"""

# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.get = AsyncMock()
    return client

@pytest.fixture
def provider(mock_client):
    return LibgenProvider(http_client=mock_client)

# ── search() Tests ────────────────────────────────────────────────────

class TestLibgenSearch:

    @pytest.mark.asyncio
    async def test_search_returns_results(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML, b"", {}, "https://libgen.ee/search.php"
        )
        results = await provider.search("quijote", categories=[7020])
        assert len(results) == 2
        assert all(isinstance(r, SearchResult) for r in results)
        assert results[0].title == "Don Quijote de la Mancha - Cervantes, Miguel de"
        assert results[0].guid.startswith("libgen-")
        assert results[0].author == "Cervantes, Miguel de"
        assert "1605" in results[0].description
        assert results[0].extra_attrs["format"] == "epub"
        assert results[0].extra_attrs["year"] == "1605"

    @pytest.mark.asyncio
    async def test_search_parses_size_mb(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML, b"", {}, "https://libgen.ee/search.php"
        )
        results = await provider.search("quijote", categories=[7020])
        # 2.5 MB = 2621440 bytes
        assert results[0].size_bytes == int(2.5 * 1024 * 1024)

    @pytest.mark.asyncio
    async def test_search_returns_pdf_format(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML, b"", {}, "https://libgen.ee/search.php"
        )
        results = await provider.search("tolkien", categories=[7020])
        assert results[1].extra_attrs["format"] == "pdf"

    @pytest.mark.asyncio
    async def test_search_empty_query(self, provider):
        results = await provider.search("", categories=[7020])
        assert results == []

    @pytest.mark.asyncio
    async def test_search_http_error(self, provider, mock_client):
        mock_client.get.side_effect = Exception("Connection refused")
        results = await provider.search("quijote", categories=[7020])
        assert results == []

    @pytest.mark.asyncio
    async def test_search_no_table_found(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML_NO_TABLE, b"", {}, "url"
        )
        results = await provider.search("quijote", categories=[7020])
        assert results == []

    @pytest.mark.asyncio
    async def test_search_short_rows_skipped(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML_SHORT_ROW, b"", {}, "url"
        )
        results = await provider.search("quijote", categories=[7020])
        assert results == []

    @pytest.mark.asyncio
    async def test_search_no_md5_skipped(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML_NO_MD5, b"", {}, "url"
        )
        results = await provider.search("quijote", categories=[7020])
        assert results == []

    @pytest.mark.asyncio
    async def test_search_applies_limit(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML, b"", {}, "url"
        )
        results = await provider.search("quijote", categories=[7020], limit=1)
        assert len(results) <= 1

    @pytest.mark.asyncio
    async def test_search_applies_offset(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML, b"", {}, "url"
        )
        results = await provider.search("quijote", categories=[7020], offset=1)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_combines_author_and_title(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML, b"", {}, "url"
        )
        results = await provider.search(
            "libro", categories=[7020], author="Cervantes", title="Quijote"
        )
        assert isinstance(results, list)

# ── get_download_url() Tests ──────────────────────────────────────────

class TestLibgenDownload:

    @pytest.mark.asyncio
    async def test_download_libgen_link(self, provider, mock_client):
        """Libgen direct download link with 'libgen' and 'get' in href."""
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML_LIBGEN, b"", {}, "https://libgen.ee"
        )
        url = await provider.get_download_url(
            "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
        )
        assert url is not None
        assert "libgen.ee" in url

    @pytest.mark.asyncio
    async def test_download_mirror_link(self, provider, mock_client):
        """Mirror download link with 'epub' text."""
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML_MIRROR, b"", {}, "https://libgen.ee"
        )
        url = await provider.get_download_url(
            "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4", fmt="epub"
        )
        assert url is not None
        assert "libgen.ee/download" in url

    @pytest.mark.asyncio
    async def test_download_cloudflare_link(self, provider, mock_client):
        """Cloudflare/IPFS download link."""
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML_CLOUDFLARE, b"", {}, "https://libgen.ee"
        )
        url = await provider.get_download_url(
            "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
        )
        assert url is not None

    @pytest.mark.asyncio
    async def test_download_fallback_direct_url(self, provider, mock_client):
        """Fallback: construct direct URL when no download links found."""
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML_NO_LINKS, b"", {}, "https://libgen.ee"
        )
        md5 = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
        url = await provider.get_download_url(md5)
        assert url is not None
        assert "/main/a1/" in url
        assert md5 in url

    @pytest.mark.asyncio
    async def test_download_http_error(self, provider, mock_client):
        mock_client.get.side_effect = Exception("Timeout")
        url = await provider.get_download_url("abc123")
        assert url is None

# ── _parse_size() Tests ───────────────────────────────────────────────

class TestLibgenParseSize:

    def test_parse_size_kb(self):
        result = LibgenProvider._parse_size("500 KB")
        assert result == 500 * 1024

    def test_parse_size_mb(self):
        result = LibgenProvider._parse_size("3.5 MB")
        assert result == int(3.5 * 1024 * 1024)

    def test_parse_size_gb(self):
        result = LibgenProvider._parse_size("2 GB")
        assert result == 2 * 1024 * 1024 * 1024

    def test_parse_size_plain_number(self):
        result = LibgenProvider._parse_size("1500000")
        assert result == 1500000

    def test_parse_size_empty(self):
        result = LibgenProvider._parse_size("")
        assert result == 1000000

    def test_parse_size_invalid(self):
        result = LibgenProvider._parse_size("abc")
        assert result == 1000000

    def test_parse_size_none_text_still_returns_default(self):
        result = LibgenProvider._parse_size(None)
        assert result == 1000000

# ── Capabilities Test ─────────────────────────────────────────────────

def test_get_capabilities(provider):
    caps = provider.get_capabilities()
    assert caps.provider_id == "libgen"
    assert caps.supports_book_search is True
    assert caps.supports_movie_search is False
    assert 7020 in caps.supported_categories
