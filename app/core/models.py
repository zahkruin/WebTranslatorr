"""
Data models for search results and provider capabilities.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class SearchResult:
    """Resultado genérico de búsqueda, agnóstico al provider."""
    title: str
    guid: str
    link: str
    download_url: str
    size_bytes: int = 0
    pub_date: datetime = field(default_factory=datetime.now)
    categories: list[int] = field(default_factory=lambda: [8010])
    description: str = ""

    # Campos opcionales según tipo de contenido
    author: Optional[str] = None
    imdb_id: Optional[str] = None
    tvdb_id: Optional[int] = None
    season: Optional[int] = None
    episode: Optional[int] = None

    # Campos Torznab
    seeders: Optional[int] = None
    peers: Optional[int] = None
    info_hash: Optional[str] = None
    magnet_uri: Optional[str] = None

    # Metadatos extra (flexibles)
    extra_attrs: dict[str, str] = field(default_factory=dict)


@dataclass
class ProviderCapabilities:
    """Capacidades que cada provider declara."""
    provider_id: str
    display_name: str
    supported_categories: list[int]
    supported_search_params: list[str]
    supports_book_search: bool = False
    supports_tv_search: bool = False
    supports_movie_search: bool = False
