"""
Provider para MejorTorrent (mejortorrent.eu).

Estructura:
- Búsqueda: GET /busqueda?q={query}
- Resultados: enlaces <a> con href a /pelicula/{id}/{slug} o /serie/{id}/{id}/{slug}
- Detalle película: Muestra género, año, formato, y enlace directo a .torrent
- Detalle serie: Muestra formato, nº episodios, un .torrent POR episodio
- Los .torrent son archivos reales, NO magnet links
"""

import re
from typing import Optional
from urllib.parse import quote_plus
from datetime import datetime

from bs4 import BeautifulSoup

from app.providers.base import BaseProvider
from app.core.models import SearchResult, ProviderCapabilities
from app.core.categories import CategoryMapper
from app.scraping.http_client import HttpClient
from config import settings


class MejorTorrentProvider(BaseProvider):
    """
    Provider para MejorTorrent - películas y series en español.
    """

    provider_id = "mejortorrent"
    display_name = "MejorTorrent"

    # Mapeo de calidades del sitio → categorías Newznab
    QUALITY_MAP = {
        "DVDRip": 2030,
        "BluRay-1080p": 2040,
        "MicroHD-1080p": 2040,
        "4K": 2045,
        "HDTV": 5030,
        "HDTV-720p": 5040,
        "HDTV-1080p": 5040,
        "SAT-Rip": 5030,
        "WEB-DL": 2080,
        "WEBRip": 2080,
    }

    def __init__(self, http_client: HttpClient, domain_resolver=None):
        base_url = settings.MEJORTORRENT_DOMAIN
        if domain_resolver:
            active_domain = domain_resolver.get_current("mejortorrent")
            if active_domain:
                base_url = active_domain
                
        super().__init__(
            http_client=http_client,
            provider_id="mejortorrent",
            display_name="MejorTorrent",
            base_url=base_url
        )

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id=self.provider_id,
            display_name=self.display_name,
            supported_categories=[
                2000, 2030, 2040, 2045,
                5000, 5030, 5040, 5045,
            ],
            supported_search_params=["q", "season", "ep", "imdbid"],
            supports_tv_search=True,
            supports_movie_search=True,
        )

    async def search(
        self,
        query: str,
        categories: list[int],
        *,
        offset: int = 0,
        limit: int = 50,
        imdb_id: Optional[str] = None,
        tvdb_id: Optional[int] = None,
        season: Optional[int] = None,
        episode: Optional[int] = None,
        author: Optional[str] = None,
        title: Optional[str] = None,
    ) -> list[SearchResult]:

        # Si Radarr envía imdbid → resolver a título español via TMDB
        if imdb_id and not query:
            query = await self._resolve_imdb_to_spanish_title(imdb_id)

        if not query:
            return []

        # Buscar en MejorTorrent
        search_url = self._build_search_url(query)

        try:
            response = await self.http_client.get(search_url)
            results = self._parse_search_results(response.text)
        except Exception as e:
            self.logger.error(f"Error en búsqueda: {e}")
            return []

        # Enriquecer: visitar cada página de detalle
        enriched = []
        for result in results[:limit]:
            try:
                detail = await self._fetch_detail_page(result)
                enriched.extend(detail)
            except Exception as e:
                self.logger.warning(f"Error en detalle {result.guid}: {e}")
                enriched.append(result)

        # Filtrar por temporada/episodio si se especificó
        if season is not None:
            enriched = [r for r in enriched if r.season == season or r.season is None]
        if episode is not None:
            enriched = [r for r in enriched if r.episode == episode or r.episode is None]

        # Aplicar offset
        if offset:
            enriched = enriched[offset:]

        return enriched

    def _build_search_url(self, query: str, page: int = 1) -> str:
        q = quote_plus(query)
        if page > 1:
            return f"{self.base_url}/busqueda/page/{page}?q={q}"
        return f"{self.base_url}/busqueda?q={q}"

    def _parse_results(self, html: str) -> list[SearchResult]:
        """
        Parsea la página de búsqueda.
        """
        soup = BeautifulSoup(html, "lxml")
        results = []
        seen_ids = set()

        for link in soup.select('a[href*="/pelicula/"], a[href*="/serie/"], a[href*="/documental/"]'):
            href = link.get("href", "")
            full_text = link.get_text(strip=True)
            if not full_text:
                continue

            # Determinar tipo de contenido por URL
            if "/pelicula/" in href:
                content_type = "movie"
                match = re.search(r'/pelicula/(\d+)/', href)
            elif "/serie/" in href:
                content_type = "tv"
                match = re.search(r'/serie/(\d+)/', href)
            elif "/documental/" in href:
                content_type = "tv"
                match = re.search(r'/documental/(\d+)/', href)
            else:
                continue

            if not match:
                continue

            item_id = match.group(1)
            if item_id in seen_ids:
                continue
            seen_ids.add(item_id)

            # Extraer calidad del texto "Título (Calidad)"
            quality_match = re.search(r'\(([^)]+)\)\s*$', full_text)
            quality = quality_match.group(1) if quality_match else "DVDRip"

            categories = self._quality_to_categories(quality, content_type)

            result = SearchResult(
                title=full_text,
                guid=f"mejortorrent-{item_id}",
                link=f"{self.base_url}{href}" if href.startswith('/') else href,
                download_url="",
                size_bytes=0,
                pub_date=datetime.now(),
                categories=categories,
                seeders=50,
                peers=50,
                extra_attrs={"quality": quality},
            )
            results.append(result)

        return results

    async def _fetch_detail_page(self, result: SearchResult) -> list[SearchResult]:
        """
        Visita la página de detalle para extraer URL del .torrent.
        """
        response = await self.http_client.get(result.link)
        soup = BeautifulSoup(response.text, "lxml")

        # Extraer descripción
        desc_text = ""
        desc_el = soup.find(string=re.compile(r'Descripción', re.I))
        if desc_el and desc_el.parent:
            desc_text = desc_el.parent.get_text(strip=True)
            desc_text = re.sub(r'Descripción\s*:?\s*', '', desc_text, flags=re.I)

        # Extraer año
        year = ""
        year_link = soup.select_one('a[href*="/year/"]')
        if year_link:
            year = year_link.get_text(strip=True)

        # Extraer género
        genre_links = soup.select('a[href*="/genre/"]')
        genres = [g.get_text(strip=True) for g in genre_links]

        # Extraer enlaces a .torrent
        torrent_links = soup.select('a[href$=".torrent"]')

        if not torrent_links:
            result.description = desc_text
            return [result]

        is_series = "/serie/" in result.link or "/documental/" in result.link

        if is_series:
            # Series: un resultado por episodio
            episode_results = []
            for i, tlink in enumerate(torrent_links, 1):
                torrent_url = tlink.get("href", "")
                if torrent_url.startswith('/'):
                    torrent_url = f"{self.base_url}{torrent_url}"

                # Extraer temporada y episodio del nombre del torrent
                season_num, episode_num = self._extract_season_episode(torrent_url, i)

                ep_result = SearchResult(
                    title=f"{result.title} - E{episode_num:02d}",
                    guid=f"{result.guid}-e{episode_num:02d}",
                    link=result.link,
                    download_url=torrent_url,
                    size_bytes=0,
                    pub_date=result.pub_date,
                    categories=result.categories,
                    description=f"{', '.join(genres)} | {year} | {desc_text}",
                    seeders=50,
                    peers=50,
                    season=season_num,
                    episode=episode_num,
                )
                episode_results.append(ep_result)
            return episode_results
        else:
            # Película: un solo resultado
            torrent_url = torrent_links[0].get("href", "")
            if torrent_url.startswith('/'):
                torrent_url = f"{self.base_url}{torrent_url}"

            # Extraer IMDb si está disponible
            imdb_id = self._extract_imdb_id(soup)
            if imdb_id:
                result.imdb_id = imdb_id

            result.download_url = torrent_url
            result.description = f"{', '.join(genres)} | {year} | {desc_text}"
            return [result]

    def _extract_season_episode(self, torrent_name: str, fallback_ep: int) -> tuple[int, int]:
        """Extrae temporada y episodio del nombre del torrent."""
        patterns = [
            r'(\d+)x(\d+)',
            r'Temporada\s*(\d+).*?(\d+)',
            r'Capitulo\s*(\d+)',
            r'Episodio\s*(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, torrent_name, re.I)
            if match:
                groups = match.groups()
                if len(groups) == 2:
                    return int(groups[0]), int(groups[1])
                elif len(groups) == 1:
                    return 1, int(groups[0])

        return 1, fallback_ep

    def _extract_imdb_id(self, soup: BeautifulSoup) -> Optional[str]:
        """Intenta extraer el IMDb ID de la página."""
        # Buscar en enlaces o texto
        for link in soup.select('a[href*="imdb.com"]'):
            href = link.get("href", "")
            match = re.search(r'tt\d+', href)
            if match:
                return match.group(0)
        return None

    def _quality_to_categories(self, quality: str, content_type: str) -> list[int]:
        """Mapea calidad del sitio a categorías Newznab."""
        parent = 2000 if content_type == "movie" else 5000
        sub = self.QUALITY_MAP.get(quality, 2030 if content_type == "movie" else 5030)
        return [parent, sub]

    async def _resolve_imdb_to_spanish_title(self, imdb_id: str) -> str:
        """
        Usa TMDB API para resolver IMDb ID → título en español.
        """
        if not settings.TMDB_API_KEY:
            return imdb_id

        try:
            tmdb_url = f"https://api.themoviedb.org/3/find/{imdb_id}"
            params = {
                "external_source": "imdb_id",
                "language": "es-ES",
                "api_key": settings.TMDB_API_KEY,
            }
            resp = await self.http_client.get(tmdb_url, params=params)
            data = resp.json()

            if data.get("movie_results"):
                return data["movie_results"][0].get("title", "")
            elif data.get("tv_results"):
                return data["tv_results"][0].get("name", "")
        except Exception as e:
            self.logger.warning(f"TMDB lookup failed for {imdb_id}: {e}")

        return imdb_id

    async def get_download_url(self, internal_id: str) -> str:
        """El download_url ya es la URL directa al .torrent."""
        return internal_id
