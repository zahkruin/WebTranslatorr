"""
Provider para elitetorrent.com - Torrent tracker de películas y series HD.

EliteTorrent es un tracker con más de 10 años de trayectoria.
Estructura:
- Búsqueda: GET /?s={query}
- Resultados: Sistema de páginas con paginacion class
- Detalle: Página individual con metadatos completos
- Descarga: Magnet link o archivo .torrent en página de detalle
- Filtros: por año de estreno, calidad, idioma

Patrón similar a MejorTorrentProvider.
"""

import re
import logging
from typing import Optional
from datetime import datetime
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from app.providers.base import BaseProvider
from app.core.models import SearchResult, ProviderCapabilities
from app.scraping.http_client import HttpClient
from config import settings


logger = logging.getLogger("provider.elitetorrent")


class EliteTorrentProvider(BaseProvider):
    """
    Provider para EliteTorrent - películas y series en HD vía torrent.
    """

    _MAX_PAGES = 2

    # Quality mapping to Newznab categories
    QUALITY_MAP = {
        "4K": 2045,
        "2160p": 2045,
        "MicroHD": 2040,
        "1080p": 2040,
        "720p": 2030,
        "BRRip": 2040,
        "BluRay": 2040,
        "HDRip": 2080,
        "HDTV": 5030,
        "WEB-DL": 2080,
        "WEBRip": 2080,
    }

    def __init__(self, http_client: HttpClient, domain_resolver=None):
        domain = settings.ELITETORRENT_DOMAIN
        if domain_resolver:
            active_domain = domain_resolver.get_current("elitetorrent")
            if active_domain:
                domain = active_domain

        super().__init__(
            provider_id="elitetorrent",
            display_name="EliteTorrent",
            base_url=domain,
            http_client=http_client,
            categories=[2000, 2030, 2040, 2045, 5000, 5030, 5040]
        )

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id=self.provider_id,
            display_name=self.display_name,
            supported_categories=[
                2000, 2030, 2040, 2045,
                5000, 5030, 5040, 5045,
            ],
            supported_search_params=["q", "imdb_id", "tvdb_id", "season", "episode"],
            supports_movie_search=True,
            supports_tv_search=True,
            supports_book_search=False,
        )

    async def search(
        self,
        query: str,
        categories: list[int] = None,
        *,
        offset: int = 0,
        limit: int = 50,
        imdb_id: Optional[str] = None,
        tvdb_id: Optional[int] = None,
        season: Optional[int] = None,
        episode: Optional[int] = None,
        author: Optional[str] = None,
        title: Optional[str] = None,
        **kwargs
    ) -> list[SearchResult]:
        if not query:
            return []

        query_to_use = self.normalize_query(query)
        self.logger.info(f"Buscando en EliteTorrent: '{query_to_use}'")
        if not query_to_use:
            return []

        encoded_query = quote_plus(query_to_use)
        all_results = []

        # Search multiple pages
        for page in range(1, self._MAX_PAGES + 1):
            if page == 1:
                search_url = f"{self.base_url}/?s={encoded_query}"
            else:
                search_url = f"{self.base_url}/page/{page}/?s={encoded_query}"

            try:
                resp = await self.http_client.get(search_url, use_scraper=True)
                if resp.status_code != 200:
                    break

                page_results = self._parse_results(resp.text)
                if not page_results:
                    break

                all_results.extend(page_results)

                # Check if there are more pages
                soup = BeautifulSoup(resp.text, 'lxml')
                pagination = soup.select_one('.paginacion, .pagination, [class*="pagina"]')
                if not pagination:
                    break
                # Check if current page is the last one
                current = pagination.select_one('.current, .active, [class*="current"], [class*="active"]')
                if current and str(page) == current.get_text(strip=True):
                    next_exists = False
                    for a in pagination.find_all('a'):
                        if a.get_text(strip=True).isdigit() and int(a.get_text(strip=True)) > page:
                            next_exists = True
                            break
                    if not next_exists:
                        break

            except Exception as e:
                self.logger.error(f"Error en búsqueda página {page}: {e}")
                break

        # Enrich results with detail pages
        import asyncio
        semaphore = asyncio.Semaphore(3)
        enriched = []

        async def enrich_one(result):
            async with semaphore:
                try:
                    detail_results = await self._fetch_detail_page(result)
                    return detail_results
                except Exception as e:
                    self.logger.warning(f"Error en detalle {result.guid}: {e}")
                    return [result]

        if all_results:
            tasks = [enrich_one(r) for r in all_results[:limit]]
            detail_lists = await asyncio.gather(*tasks)
            for detail_list in detail_lists:
                enriched.extend(detail_list)

        # Filter by season/episode
        if season is not None:
            enriched = [r for r in enriched if r.season == season or r.season is None]
        if episode is not None:
            enriched = [r for r in enriched if r.episode == episode or r.episode is None]

        if offset:
            enriched = enriched[offset:]

        return enriched

    def _parse_results(self, html: str) -> list[SearchResult]:
        """Parse search results page."""
        soup = BeautifulSoup(html, 'lxml')
        results = []
        seen_links = set()

        # EliteTorrent card/item layout
        selectors = [
            'a[href*="/peliculas/"]',
            'a[href*="/series/"]',
            'a[href*="/pelicula/"]',
            'a[href*="/serie/"]',
            'article a[href]',
            'div.item a[href]',
            'h2 a[href]', 'h3 a[href]',
            '.entry-title a[href]',
        ]

        for selector in selectors:
            for link in soup.select(selector):
                href = link.get('href', '')
                title_text = link.get('title') or link.get_text(strip=True)

                if not href or not title_text or len(title_text) < 3:
                    continue
                if href in seen_links:
                    continue
                seen_links.add(href)

                # Skip non-content links
                if any(skip in href.lower() for skip in [
                    '/category/', '/tag/', '/page/', '/author/',
                    '/genero/', '/genre/', '/year/', '/calidad/',
                    'wp-content', 'wp-admin', 'wp-login',
                    'facebook', 'twitter', 'instagram',
                    'javascript:', '#',
                    '/search/', '/buscar/',
                ]):
                    continue
                if title_text.lower() in (
                    'inicio', 'home', 'películas', 'peliculas',
                    'series', 'contacto', 'buscar',
                ):
                    continue

                # Determine content type
                if '/peliculas/' in href or '/pelicula/' in href:
                    content_type = 'movie'
                elif '/series/' in href or '/serie/' in href:
                    content_type = 'tv'
                else:
                    # Infer from title keywords
                    if any(kw in title_text.lower() for kw in (
                        'temporada', 'serie', 'capitulo', 'capítulo', 'episodio'
                    )):
                        content_type = 'tv'
                    else:
                        content_type = 'movie'

                # Extract internal ID
                internal_id = self._extract_internal_id(href, title_text)

                # Normalize link
                if href.startswith('/'):
                    link_full = f"{self.base_url}{href}"
                elif not href.startswith('http'):
                    link_full = f"{self.base_url}/{href}"
                else:
                    link_full = href

                # Try to extract quality
                quality = self._extract_quality(title_text, link)

                cat = [2000, 2040] if content_type == 'movie' else [5000, 5040]
                sub_cat = self.QUALITY_MAP.get(quality)
                if sub_cat:
                    cat = [cat[0], sub_cat]

                result = SearchResult(
                    title=title_text,
                    guid=f"elitetorrent-{internal_id}",
                    link=link_full,
                    download_url="",  # Filled by detail page
                    size_bytes=0,
                    pub_date=datetime.now(),
                    categories=cat,
                    seeders=50,
                    peers=50,
                    extra_attrs={"quality": quality, "content_type": content_type},
                )
                results.append(result)

        return results

    async def _fetch_detail_page(self, result: SearchResult) -> list[SearchResult]:
        """Visit detail page to extract magnet/torrent and metadata."""
        response = await self.http_client.get(result.link, use_scraper=True)
        soup = BeautifulSoup(response.text, 'lxml')

        # Extract description
        desc_text = ""
        desc_elem = soup.select_one('[class*="sinopsis"], [class*="description"], [class*="descripcion"], .entry-content')
        if desc_elem:
            desc_text = desc_elem.get_text(strip=True)[:500]

        # Extract year
        year = ""
        year_elem = soup.select_one('[class*="year"], [class*="año"], [class*="ano"]')
        if year_elem:
            year_text = year_elem.get_text(strip=True)
            year_match = re.search(r'(19|20)\d{2}', year_text)
            if year_match:
                year = year_match.group(0)

        # Extract quality
        quality_elem = soup.select_one('[class*="quality"], [class*="calidad"], [class*="resolucion"]')
        quality = result.extra_attrs.get('quality', '')
        if quality_elem:
            q_text = quality_elem.get_text(strip=True)
            for q in self.QUALITY_MAP:
                if q.lower() in q_text.lower():
                    quality = q
                    break

        # Extract size
        size_bytes = 0
        size_elem = soup.select_one('[class*="size"], [class*="tamaño"], [class*="tamano"]')
        if size_elem:
            size_text = size_elem.get_text(strip=True)
            size_bytes = self._parse_size(size_text)

        # Extract language
        language = ""
        lang_elem = soup.select_one('[class*="idioma"], [class*="language"], [class*="lang"]')
        if lang_elem:
            language = lang_elem.get_text(strip=True)

        # Extract seeds/peers
        seeders = 50
        peers = 50
        for elem in soup.select('[class*="seed"], [class*="semillas"], span, div'):
            text = elem.get_text(strip=True)
            if 'seed' in text.lower() or 'semilla' in text.lower():
                s_match = re.search(r'(\d+)', text)
                if s_match:
                    seeders = int(s_match.group(1))
            if 'peer' in text.lower() or 'cliente' in text.lower():
                p_match = re.search(r'(\d+)', text)
                if p_match:
                    peers = int(p_match.group(1))

        # Extract magnet link
        magnet_uri = None
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.startswith('magnet:'):
                magnet_uri = href
                break

        # Extract .torrent link
        torrent_url = None
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.endswith('.torrent') or 'torrent' in href.lower():
                torrent_url = href
                if torrent_url.startswith('/'):
                    torrent_url = f"{self.base_url}{torrent_url}"
                elif not torrent_url.startswith('http'):
                    torrent_url = f"{self.base_url}/{torrent_url}"
                break

        # Extract info_hash
        info_hash = None
        if magnet_uri:
            hash_match = re.search(r'btih:([a-fA-F0-9]{40})', magnet_uri)
            if hash_match:
                info_hash = hash_match.group(1).upper()

        # Extract IMDb
        imdb_id = None
        for a in soup.find_all('a', href=True):
            imdb_match = re.search(r'(tt\d{7,8})', a['href'])
            if imdb_match:
                imdb_id = imdb_match.group(1)
                break

        # Build description
        description_parts = []
        if quality:
            description_parts.append(f"Calidad: {quality}")
        if language:
            description_parts.append(f"Idioma: {language}")
        if year:
            description_parts.append(f"Año: {year}")
        if desc_text:
            description_parts.append(desc_text)
        result.description = " | ".join(description_parts) if description_parts else result.title

        # Update result
        result.magnet_uri = magnet_uri
        result.info_hash = info_hash
        result.size_bytes = size_bytes or 800000000
        result.seeders = seeders
        result.peers = peers
        if imdb_id:
            result.imdb_id = imdb_id

        if magnet_uri:
            result.download_url = magnet_uri
        elif torrent_url:
            result.download_url = torrent_url
        else:
            result.download_url = result.link

        # Update categories based on quality
        if quality:
            sub_cat = self.QUALITY_MAP.get(quality)
            if sub_cat:
                parent = 2000 if result.extra_attrs.get('content_type') == 'movie' else 5000
                result.categories = [parent, sub_cat]

        # Season/episode for series
        if result.extra_attrs.get('content_type') == 'tv':
            season_num, episode_num = self._extract_season_episode(soup, result.title)
            result.season = season_num
            result.episode = episode_num

        return [result]

    @staticmethod
    def _extract_quality(title: str, link) -> str:
        """Extract quality from title or surrounding elements."""
        quality_patterns = [
            '4K', '2160p', '1080p', '720p', '480p',
            'MicroHD', 'BRRip', 'BluRay', 'HDRip',
            'HDTV', 'WEB-DL', 'WEBRip', 'HD',
        ]
        for q in quality_patterns:
            if q.lower() in title.lower():
                return q

        parent = link.parent
        if parent:
            for q in quality_patterns:
                badge = parent.select_one(f'[class*="{q.lower()}"], [class*="{q}"]')
                if badge:
                    return q
                img = parent.find('img', alt=re.compile(q, re.I))
                if img:
                    return q

        return "HD"

    @staticmethod
    def _extract_season_episode(soup: BeautifulSoup, title: str) -> tuple[int, int]:
        """Extract season and episode numbers."""
        patterns = [
            r'(\d+)x(\d+)',
            r'Temporada\s*(\d+).*?Cap[ií]tulo\s*(\d+)',
            r'T(\d+)\s*E(\d+)',
            r'S(\d+)E(\d+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) == 2:
                    return int(groups[0]), int(groups[1])

        return 1, 1

    @staticmethod
    def _parse_size(size_text: str) -> int:
        """Convert size text to bytes."""
        if not size_text:
            return 0
        size_text = size_text.strip().lower()
        try:
            if 'gb' in size_text:
                return int(float(size_text.replace('gb', '').replace(',', '.').strip()) * 1024 * 1024 * 1024)
            elif 'mb' in size_text:
                return int(float(size_text.replace('mb', '').replace(',', '.').strip()) * 1024 * 1024)
            elif 'kb' in size_text:
                return int(float(size_text.replace('kb', '').replace(',', '.').strip()) * 1024)
        except ValueError:
            pass
        return 0

    @staticmethod
    def _extract_internal_id(href: str, title: str) -> str:
        """Extract internal ID from URL."""
        # Try numeric ID
        num_match = re.search(r'/(\d+)/?$', href.rstrip('/'))
        if num_match:
            return num_match.group(1)

        # Try slug
        parts = [p for p in href.rstrip('/').split('/') if p]
        if parts:
            return parts[-1]

        slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
        return slug or title.replace(' ', '-').lower()

    async def get_download_url(self, internal_id: str) -> str:
        """Download URL is set during search enrichment."""
        return internal_id
