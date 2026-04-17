"""
Tests for Torznab XML mapper.
"""

import pytest
from datetime import datetime
from xml.etree.ElementTree import fromstring

from app.core.models import SearchResult
from app.torznab.mapper import TorznabMapper


def test_results_to_xml():
    results = [
        SearchResult(
            title="Test Book",
            guid="test-123",
            link="https://example.com/book/123",
            download_url="/api/download?provider=test&id=123",
            size_bytes=1024,
            pub_date=datetime(2024, 1, 15, 12, 0, 0),
            categories=[7000, 7020],
            description="A test book",
            seeders=100,
            peers=100,
            extra_attrs={"booktitle": "Test Book"},
        )
    ]

    xml = TorznabMapper.results_to_xml(results, offset=0, total=1)

    # Parse and verify XML structure
    root = fromstring(xml)
    assert root.tag == "rss"
    assert root.attrib["version"] == "2.0"

    channel = root.find("channel")
    assert channel is not None
    assert channel.find("title").text == "WebTranslatorr"

    items = channel.findall("item")
    assert len(items) == 1

    item = items[0]
    assert item.find("title").text == "Test Book"
    assert item.find("guid").text == "test-123"


def test_empty_results_to_xml():
    xml = TorznabMapper.results_to_xml([], offset=0, total=0)
    root = fromstring(xml)
    assert root.tag == "rss"

    channel = root.find("channel")
    items = channel.findall("item")
    assert len(items) == 0
