"""
Provider para divxtotal.wtf - Torrent tracker de películas y series.

DivxTotal es un tracker de torrents con dominio extremadamente inestable
(18+ dominios históricos). Estructura:

- Búsqueda: GET /buscar/{query}/page/{n}
- Resultados: Tarjetas con imagen, título, tipo (película/serie), badges
- Detalle: /pelicula/{id}/{slug} o /serie/{id}/{slug}
- Descarga: Magnet links y archivos .torrent en página de detalle

Patrón similar a MejorTorrentProvider: búsqueda → enriquecimiento por detalle → magnet/torrent.
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


logger = logging.getLogger("provider.divxtotal")


class DivxtotalProvider(BaseProvider):
    """
    Provider para DivxTotal - películas y series en español vía torrent.
    """

    _MAX_PAGES = 2  # Limit pagination to avoid saturating
    _RESULTS_PER_PAGE = 10

    # Quality mapping to Newznab categories
    QUALITY_MAP = {
        "HD": 2040,
        "1080p": 2040,
        "720p": 2030,
        "4K": 2045,
        "DVDRip": 2030,
        "BRRip": 2040,
        "BluRay": 2040,
        "HDTV": 5030,
        "WEB-DL": 2080,
        "WEBRip": 2080,
        "HDRip": 2080,
    }

    def __init__(self, http_client: HttpClient, domain_resolver=None):
        domain = settings.DIVXTOTAL_DOMAIN
        if domain_resolver:
            active_domain = domain_resolver.get_current("divxtotal")
            if active_domain:
                domain = active_domain

        super().__init__(
            provider_id="divxtotal",
            display_name="DivxTotal",
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
        self.logger.info(f"Buscando en DivxTotal: '{query_to_use}'")
        if not query_to_use:
            return []

        encoded_query = quote_plus(query_to_use)
        all_results = []

        # Search multiple pages
        for page in range(1, self._MAX_PAGES + 1):
            search_url = f"{self.base_url}/buscar/{encoded_query}/page/{page}"

            try:
                resp = await self.http_client.get(search_url, use_scraper=True)
                if resp.status_code != 200:
                    break

                page_results = self._parse_results(resp.text)
                if not page_results:
                    break

                all_results.extend(page_results)

                if len(page_results) < self._RESULTS_PER_PAGE:
                    break  # No more pages

            except Exception as e:
                self.logger.error(f"Error en búsqueda página {page}: {e}")
                break

        # Enrich results with detail pages (semaphore=3 for concurrency control)
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

        # Filter by season/episode if specified
        if season is not None:
            enriched = [r for r in enriched if r.season == season or r.season is None]
        if episode is not None:
            enriched = [r for r in enriched if r.episode == episode or r.episode is None]

        # Apply offset
        if offset:
            enriched = enriched[offset:]

        return enriched

    def _parse_results(self, html: str) -> list[SearchResult]:
        """Parse search results page."""
        soup = BeautifulSoup(html, 'lxml')
        results = []
        seen_links = set()

        # DivxTotal card-based layout
        selectors = [
            'a[href*="/pelicula/"]',
            'a[href*="/serie/"]',
            'article a[href]',
            'div.card a[href]',
            'h2 a[href]', 'h3 a[href]',
        ]

        for selector in selectors:
            for link in soup.select(selector):
                href = link.get('href', '')
                title_text = link.get_text(strip=True)

                if not href or not title_text or len(title_text) < 3:
                    continue
                if href in seen_links:
                    continue
                seen_links.add(href)

                # Determine content type
                if '/pelicula/' in href:
                    content_type = 'movie'
                    match = re.search(r'/pelicula/(\d+)/?', href)
                elif '/serie/' in href:
                    content_type = 'tv'
                    match = re.search(r'/serie/(\d+)/?', href)
                else:
                    continue

                if not match:
                    continue

                item_id = match.group(1)

                # Try to extract quality from title or badges
                quality = self._extract_quality(title_text, link)

                # Map to categories
                cat = [2000, 2040] if content_type == 'movie' else [5000, 5040]
                sub_cat = self.QUALITY_MAP.get(quality)
                if sub_cat:
                    cat = [cat[0], sub_cat]

                # Normalize link
                if href.startswith('/'):
                    link_full = f"{self.base_url}{href}"
                elif not href.startswith('http'):
                    link_full = f"{self.base_url}/{href}"
                else:
                    link_full = href

                result = SearchResult(
                    title=title_text,
                    guid=f"divxtotal-{item_id}",
                    link=link_full,
                    download_url="",  # Will be filled by detail page
                    size_bytes=0,
                    pub_date=datetime.now(),
                    categories=cat,
                    seeders=50,  # Placeholder, updated by detail page
                    peers=50,
                    extra_attrs={"quality": quality, "content_type": content_type},
                )
                results.append(result)

        return results

    async def _fetch_detail_page(self, result: SearchResult) -> list[SearchResult]:
        """Visit detail page to extract magnet/torrent links and metadata."""
        response = await self.http_client.get(result.link, use_scraper=True)
        soup = BeautifulSoup(response.text, 'lxml')

        # Extract description
        desc_text = ""
        desc_elem = soup.select_one('[class*="sinopsis"], [class*="description"], [class*="descripcion"]')
        if desc_elem:
            desc_text = desc_elem.get_text(strip=True)[:500]
        elif result.extra_attrs.get('content_type') == 'movie':
            # Try to find description near the title
            for p in soup.select('p'):
                text = p.get_text(strip=True)
                if len(text) > 50:
                    desc_text = text[:500]
                    break

        # Extract year
        year = ""
        year_elem = soup.select_one('[class*="year"], [class*="año"], [class*="ano"], time')
        if year_elem:
            year_text = year_elem.get_text(strip=True)
            year_match = re.search(r'(19|20)\d{2}', year_text)
            if year_match:
                year = year_match.group(0)

        # Extract quality
        quality_elem = soup.select_one('[class*="quality"], [class*="calidad"], [class*="resolucion"]')
        quality = result.extra_attrs.get('quality', '')
        if quality_elem and not quality:
            quality = quality_elem.get_text(strip=True)

        # Extract size
        size_bytes = 0
        size_elem = soup.select_one('[class*="size"], [class*="tamaño"], [class*="tamano"]')
        if size_elem:
            size_text = size_elem.get_text(strip=True)
            size_bytes = self._parse_size(size_text)

        # Extract seeds/peers
        seeders = 50
        peers = 50
        seeds_elem = soup.select_one('[class*="seed"], [class*="semillas"]')
        peers_elem = soup.select_one('[class*="peer"], [class*="clientes"]')
        if seeds_elem:
            seeds_text = seeds_elem.get_text(strip=True)
            seeds_match = re.search(r'(\d+)', seeds_text)
            if seeds_match:
                seeders = int(seeds_match.group(1))
        if peers_elem:
            peers_text = peers_elem.get_text(strip=True)
            peers_match = re.search(r'(\d+)', peers_text)
            if peers_match:
                peers = int(peers_match.group(1))

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

        # Extract info_hash from magnet
        info_hash = None
        if magnet_uri:
            hash_match = re.search(r'btih:([a-fA-F0-9]{40})', magnet_uri)
            if hash_match:
                info_hash = hash_match.group(1).upper()

        # Extract IMDb ID if available
        imdb_id = None
        for a in soup.find_all('a', href=True):
            href = a['href']
            imdb_match = re.search(r'(tt\d{7,8})', href)
            if imdb_match:
                imdb_id = imdb_match.group(1)
                break

        # Build description
        description_parts = []
        if quality:
            description_parts.append(f"Calidad: {quality}")
        if year:
            description_parts.append(f"Año: {year}")
        if desc_text:
            description_parts.append(desc_text)
        result.description = " | ".join(description_parts) if description_parts else result.title

        # Update result with detail metadata
        result.magnet_uri = magnet_uri
        result.info_hash = info_hash
        result.size_bytes = size_bytes or 1000000000
        result.seeders = seeders
        result.peers = peers
        if imdb_id:
            result.imdb_id = imdb_id

        # Set download_url: prefer magnet, fall back to torrent
        if magnet_uri:
            result.download_url = magnet_uri
        elif torrent_url:
            result.download_url = torrent_url
        else:
            # Use detail page URL as fallback
            result.download_url = result.link

        # Update categories based on quality
        if quality:
            sub_cat = self.QUALITY_MAP.get(quality)
            if sub_cat:
                parent = 2000 if result.extra_attrs.get('content_type') == 'movie' else 5000
                result.categories = [parent, sub_cat]

        # Check if series: try to extract season/episode
        content_type = result.extra_attrs.get('content_type', '')
        if content_type == 'tv':
            season_num, episode_num = self._extract_season_episode(soup, result.title)
            result.season = season_num
            result.episode = episode_num

        return [result]

    @staticmethod
    def _extract_quality(title: str, link) -> str:
        """Extract quality from title text or badges."""
        # Check title for quality indicators
        quality_patterns = [
            '4K', '2160p', '1080p', '720p', '480p',
            'DVDRip', 'BRRip', 'BluRay', 'HDRip',
            'HDTV', 'WEB-DL', 'WEBRip', 'MicroHD',
            'HD', 'SD',
        ]
        for q in quality_patterns:
            if q.lower() in title.lower():
                return q

        # Check parent for badges
        parent = link.parent
        if parent:
            badge = parent.select_one('[class*="quality"], [class*="badge"], [class*="calidad"], [class*="tag"]')
            if badge:
                badge_text = badge.get_text(strip=True)
                for q in quality_patterns:
                    if q.lower() in badge_text.lower():
                        return q

        return "HD"

    @staticmethod
    def _extract_season_episode(soup: BeautifulSoup, title: str) -> tuple[int, int]:
        """Extract season and episode from detail page or title."""
        # Check detail page elements
        season_elem = soup.select_one('[class*="season"], [class*="temporada"]')
        episode_elem = soup.select_one('[class*="episode"], [class*="capitulo"], [class*="episodio"]')

        season_num = 1
        episode_num = 1

        if season_elem:
            s_match = re.search(r'(\d+)', season_elem.get_text(strip=True))
            if s_match:
                season_num = int(s_match.group(1))
        if episode_elem:
            e_match = re.search(r'(\d+)', episode_elem.get_text(strip=True))
            if e_match:
                episode_num = int(e_match.group(1))

        # Try title patterns
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

        return season_num, episode_num

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

    async def get_download_url(self, internal_id: str) -> str:
        """
        The download_url is set during search enrichment.
        internal_id is the URL to the detail page or the magnet/torrent link.
        """
        return internal_id
