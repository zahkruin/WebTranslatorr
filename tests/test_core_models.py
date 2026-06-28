"""
Tests for core data models, enums, and exceptions.

Covers: SearchResult defaults, ProviderCapabilities,
ContentType, SearchType, exception hierarchy.
"""
import pytest
from datetime import datetime

from app.core.models import SearchResult, ProviderCapabilities
from app.core.enums import ContentType, SearchType
from app.core.exceptions import (
    WebTranslatorrError, ProviderNotFoundError, ProviderError,
    ScrapingError, DownloadError, ValidationError,
)


# ── SearchResult Tests ────────────────────────────────────────────────

class TestSearchResult:

    def test_default_values(self):
        result = SearchResult(
            title="Test", guid="test-1",
            link="https://example.com", download_url="https://example.com/dl"
        )
        assert result.title == "Test"
        assert result.size_bytes == 0
        assert isinstance(result.pub_date, datetime)
        assert result.categories == [7000, 7020, 8000, 8010]
        assert result.description == ""
        assert result.author is None
        assert result.imdb_id is None
        assert result.seeders is None
        assert result.extra_attrs == {}

    def test_full_book_result(self):
        result = SearchResult(
            title="El Quijote", guid="ebookelo-1828",
            link="https://ebookelo.com/ebook/1828/quijote",
            download_url="http://localhost:9811/api/download?provider=ebookelo&id=1828&fmt=epub",
            size_bytes=2500000, categories=[7000, 7020, 8000, 8010],
            description="Obra maestra", author="Miguel de Cervantes",
            seeders=100, peers=100,
            extra_attrs={"format": "epub", "genre": "Novela", "language": "es"},
        )
        assert result.title == "El Quijote"
        assert result.author == "Miguel de Cervantes"
        assert result.extra_attrs["format"] == "epub"
        assert 7000 in result.categories

    def test_video_result(self):
        result = SearchResult(
            title="Inception", guid="mejortorrent-30403",
            link="https://mejortorrent.eu/pelicula/30403/inception",
            download_url="https://mejortorrent.eu/torrents/peliculas/inception.torrent",
            size_bytes=0, categories=[2000, 2040],
            imdb_id="tt1375666", seeders=50, peers=50,
            info_hash="abc123", magnet_uri="magnet:?xt=urn:btih:abc123",
        )
        assert result.imdb_id == "tt1375666"
        assert result.info_hash == "abc123"
        assert result.magnet_uri is not None

    def test_tv_result(self):
        result = SearchResult(
            title="Breaking Bad - E01", guid="mejortorrent-123-e01",
            link="https://mejortorrent.eu/serie/123/breaking-bad",
            download_url="https://mejortorrent.eu/torrents/series/bb-s01e01.torrent",
            categories=[5000, 5040], season=1, episode=1,
        )
        assert result.season == 1
        assert result.episode == 1


# ── ProviderCapabilities Tests ────────────────────────────────────────

class TestProviderCapabilities:

    def test_book_provider_caps(self):
        caps = ProviderCapabilities(
            provider_id="ebookelo", display_name="Ebookelo",
            supported_categories=[7000, 7020, 8000, 8010],
            supported_search_params=["q", "author", "title"],
            supports_book_search=True,
        )
        assert caps.provider_id == "ebookelo"
        assert caps.supports_book_search is True
        assert caps.supports_movie_search is False
        assert caps.supports_tv_search is False

    def test_video_provider_caps(self):
        caps = ProviderCapabilities(
            provider_id="mejortorrent", display_name="MejorTorrent",
            supported_categories=[2000, 2030, 2040, 2045, 5000, 5030, 5040],
            supported_search_params=["q", "season", "ep", "imdbid"],
            supports_movie_search=True, supports_tv_search=True,
        )
        assert caps.supports_movie_search is True
        assert caps.supports_tv_search is True
        assert "imdbid" in caps.supported_search_params


# ── Enums Tests ───────────────────────────────────────────────────────

class TestEnums:

    def test_content_type_values(self):
        assert ContentType.BOOK.value == "book"
        assert ContentType.MOVIE.value == "movie"
        assert ContentType.TV.value == "tv"

    def test_search_type_values(self):
        assert SearchType.GENERIC.value == "search"
        assert SearchType.TV.value == "tvsearch"
        assert SearchType.MOVIE.value == "movie"
        assert SearchType.BOOK.value == "book"

    def test_search_type_from_string(self):
        assert SearchType("search") == SearchType.GENERIC
        assert SearchType("tvsearch") == SearchType.TV
        assert SearchType("movie") == SearchType.MOVIE
        assert SearchType("book") == SearchType.BOOK


# ── Exceptions Tests ──────────────────────────────────────────────────

class TestExceptions:

    def test_provider_not_found_error(self):
        err = ProviderNotFoundError("Provider 'xyz' not found")
        assert isinstance(err, WebTranslatorrError)
        assert isinstance(err, Exception)
        assert str(err) == "Provider 'xyz' not found"

    def test_provider_error(self):
        err = ProviderError("Search failed")
        assert isinstance(err, WebTranslatorrError)

    def test_scraping_error(self):
        err = ScrapingError("CSS selector not found")
        assert isinstance(err, WebTranslatorrError)

    def test_download_error(self):
        err = DownloadError("Download timeout")
        assert isinstance(err, WebTranslatorrError)

    def test_validation_error(self):
        err = ValidationError("Invalid parameter")
        assert isinstance(err, WebTranslatorrError)

    def test_exceptions_can_be_raised_and_caught(self):
        with pytest.raises(ProviderNotFoundError):
            raise ProviderNotFoundError("test")
        
        with pytest.raises(WebTranslatorrError):
            raise ScrapingError("test")
