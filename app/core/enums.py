"""
Enums for content types and search types.
"""

from enum import Enum


class ContentType(Enum):
    BOOK = "book"
    MOVIE = "movie"
    TV = "tv"


class SearchType(Enum):
    GENERIC = "search"
    TV = "tvsearch"
    MOVIE = "movie"
    BOOK = "book"
