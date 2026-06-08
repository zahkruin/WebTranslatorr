"""
Tests for HTML parsing helper functions.
"""

from app.scraping.parser import parse_html, extract_text, extract_href, safe_int


def test_parse_html():
    """parse_html should return a BeautifulSoup object."""
    soup = parse_html("<html><body><p>hello</p></body></html>")
    assert soup is not None
    assert soup.find("p").text == "hello"


def test_extract_text_with_element():
    """extract_text should return the stripped text of an element."""
    soup = parse_html("<a>click me</a>")
    assert extract_text(soup.find("a")) == "click me"


def test_extract_text_with_none():
    """extract_text should return the default when element is None."""
    assert extract_text(None, "fallback") == "fallback"
    assert extract_text(None) == ""


def test_extract_href_with_element():
    """extract_href should return the href attribute."""
    soup = parse_html('<a href="https://example.com">link</a>')
    assert extract_href(soup.find("a")) == "https://example.com"


def test_extract_href_with_none():
    """extract_href should return the default when element is None."""
    assert extract_href(None, "default") == "default"


def test_safe_int_valid():
    """safe_int should parse a valid integer string."""
    assert safe_int("42") == 42


def test_safe_int_invalid():
    """safe_int should return default for an invalid string."""
    assert safe_int("abc") == 0


def test_safe_int_none():
    """safe_int should return default for None."""
    assert safe_int(None) == 0
