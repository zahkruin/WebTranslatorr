"""
Search language definitions for translation pipeline and *Arr integration.

Each language maps an ISO 639-1 code to the display name and the
Wikidata / Google Books language identifiers used during lookups.

Usage::

    from app.core.languages import SEARCH_LANGUAGES, SearchLanguage, resolve_language

    lang = resolve_language("fr")  # returns SearchLanguage.FRENCH
    print(lang.display_name)       # "Français"
    print(lang.wikidata_code)      # "fr"
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SearchLanguage:
    """A target language for book-title translation lookups.

    Attributes:
        code: ISO 639-1 two-letter code (e.g. ``"es"``).
        display_name: Human-readable language name.
        wikidata_code: Language tag used in Wikidata SPARQL queries
                       (same as ``code`` for most languages).
        google_books_code: Language code accepted by the Google Books
                           ``langRestrict`` parameter.
    """

    code: str
    display_name: str
    wikidata_code: str
    google_books_code: str


# -- Supported languages ---------------------------------------------------

class _Languages:
    SPANISH = SearchLanguage("es", "Español", "es", "es")
    ENGLISH = SearchLanguage("en", "English", "en", "en")
    FRENCH = SearchLanguage("fr", "Français", "fr", "fr")
    GERMAN = SearchLanguage("de", "Deutsch", "de", "de")
    ITALIAN = SearchLanguage("it", "Italiano", "it", "it")
    PORTUGUESE = SearchLanguage("pt", "Português", "pt", "pt")


SearchLanguage = _Languages  # type: ignore[misc,assignment]

SUPPORTED_LANGUAGES: dict[str, SearchLanguage] = {
    lang.code: lang
    for lang in (
        _Languages.SPANISH,
        _Languages.ENGLISH,
        _Languages.FRENCH,
        _Languages.GERMAN,
        _Languages.ITALIAN,
        _Languages.PORTUGUESE,
    )
}

DEFAULT_SEARCH_LANGUAGE = _Languages.SPANISH


def resolve_language(code: Optional[str]) -> SearchLanguage:
    """Resolve a language code string to a ``SearchLanguage`` instance.

    Args:
        code: ISO 639-1 two-letter code, or ``None`` / empty string.

    Returns:
        Matching ``SearchLanguage``, falling back to
        ``DEFAULT_SEARCH_LANGUAGE`` (Spanish) when *code* is
        ``None``, empty, or not recognised.
    """
    if not code:
        return DEFAULT_SEARCH_LANGUAGE
    code = code.strip().lower()
    if code in SUPPORTED_LANGUAGES:
        return SUPPORTED_LANGUAGES[code]
    return DEFAULT_SEARCH_LANGUAGE
