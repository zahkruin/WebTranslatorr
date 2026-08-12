"""
Tests for ZipExtractor utility.
"""

import io
import zipfile
from unittest.mock import patch

import pytest

from app.core.exceptions import ZipBombError
from app.utils.zip_extractor import ZipExtractor


class TestZipExtractor:
    """Tests for ZipExtractor.extract_epub_from_memory."""

    def test_extract_epub_found(self):
        """Should extract and return the first .epub file from a ZIP."""
        epub_content = b"EPUB content here"
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("book.epub", epub_content)
            zf.writestr("metadata.xml", "<xml>data</xml>")
        zip_bytes = zip_buffer.getvalue()

        result = ZipExtractor.extract_epub_from_memory(zip_bytes)
        assert result == epub_content

    def test_extract_epub_not_found(self):
        """Should return None when no .epub file exists in ZIP."""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("readme.txt", "hello")
        zip_bytes = zip_buffer.getvalue()

        result = ZipExtractor.extract_epub_from_memory(zip_bytes)
        assert result is None

    def test_extract_epub_case_insensitive(self):
        """Should match .epub extension case-insensitively."""
        epub_content = b"EPUB test"
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("book.EPUB", epub_content)
        zip_bytes = zip_buffer.getvalue()

        result = ZipExtractor.extract_epub_from_memory(zip_bytes)
        assert result == epub_content

    def test_extract_bad_zipfile(self):
        """Should return None when bytes are not a valid ZIP."""
        result = ZipExtractor.extract_epub_from_memory(b"not a zip file")
        assert result is None

    def test_extract_empty_bytes(self):
        """Should return None when passed empty bytes."""
        result = ZipExtractor.extract_epub_from_memory(b"")
        assert result is None

    def test_extract_generic_exception(self):
        """Should return None when a non-BadZipFile exception occurs."""
        with patch("app.utils.zip_extractor.zipfile.ZipFile") as mock_zf:
            mock_zf.side_effect = Exception("Unexpected error")
            result = ZipExtractor.extract_epub_from_memory(b"some bytes")
            assert result is None

    def test_rejects_zip_bomb_ratio(self):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("book.epub", b"x" * 1024)
        zip_bytes = zip_buffer.getvalue()

        with patch("app.utils.zip_extractor.settings") as mock_settings:
            mock_settings.ZIP_MAX_ENTRIES = 100
            mock_settings.ZIP_MAX_UNCOMPRESSED_BYTES = 524288000
            mock_settings.ZIP_MAX_RATIO = 1
            with pytest.raises(ZipBombError):
                ZipExtractor.extract_epub_from_memory(zip_bytes)
