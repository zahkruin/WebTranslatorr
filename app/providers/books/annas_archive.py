import re
from typing import Dict, Any, List
from bs4 import BeautifulSoup

from app.providers.base import BaseProvider
from config import settings


class AnnasArchiveProvider(BaseProvider):
    def __init__(self, http_client, domain_resolver=None):
        domain = settings.ANNASARCHIVE_DOMAIN
        if domain_resolver:
            active_domain = domain_resolver.get_current("annasarchive")
            if active_domain:
                domain = active_domain
                
        super().__init__(
            provider_id="annasarchive",
            display_name="Anna's Archive",
            base_url=domain,
            http_client=http_client,
            categories=[7000, 7020, 8000, 8010]
        )

    async def search(self, query: str, category: int = None, limit: int = 100, **kwargs) -> List[Dict[str, Any]]:
        combined_query = self._combine_query(query, kwargs.get('author'), kwargs.get('title'))
        query_to_use = self.normalize_query(combined_query)
        self.logger.info(f"Buscando en Anna's Archive: '{query_to_use}'")
        if not query_to_use:
            return []
            
        results = []
        
        # Optimize search for epub and spanish to reduce noise
        search_url = f"{self.base_url}/search?q={query_to_use}&lang=es&ext=epub"
        
        try:
            # Anna's Archive bloquea casi todo, use_scraper es obligatorio
            resp = await self.http_client.get(search_url, use_scraper=True)
            soup = BeautifulSoup(resp.text, 'lxml')
            
            seen_urls = set()
            
            # Annas Archive usa a[href*="/md5/"] para los links de los libros
            for a in soup.select('a[href*="/md5/"]'):
                href = a.get('href')
                
                # El titulo suele estar en un div interno
                title_div = a.find('h3') or a.select_one('div.text-xl, div.font-bold')
                if not title_div:
                    continue
                    
                title = title_div.get_text(strip=True)
                
                if not href or href in seen_urls:
                    continue
                    
                seen_urls.add(href)
                
                # md5 as internal ID
                internal_id = href.split('/md5/')[-1]

                item = {
                    "id": internal_id,
                    "title": title,
                    "guid": f"{self.base_url}{href}",
                    "size": 1000000, # Podriamos parsearlo pero requiere extraccion fina
                    "link": f"{settings.HOST}:{settings.PORT}/api/download?provider={self.provider_id}&id={internal_id}&fmt=epub",
                    "description": f"Libro: {title}",
                    "pubDate": "Wed, 01 Jan 2020 00:00:00 +0000",
                    "categories": [7020]
                }
                
                results.append(item)
                
                if len(results) >= limit:
                    break

        except Exception as e:
            self.logger.error(f"Error parseando Anna's Archive: {e}")
            
        return results

    async def get_download_url(self, internal_id: str, **kwargs) -> str | None:
        """
        Anna's Archive ofrece múltiples mirrors.
        Preferimos "Slow Partner Server" porque no suelen requerir login, aunque tarden.
        """
        detail_url = f"{self.base_url}/md5/{internal_id}"
        
        try:
            resp = await self.http_client.get(detail_url, use_scraper=True)
            soup = BeautifulSoup(resp.text, 'lxml')
            
            # Buscar enlaces de descarga
            for a in soup.select('a.js-download-link'):
                text = a.get_text(strip=True).lower()
                href = a.get('href', '')
                
                # Generalmente los links empiezan por /download/o enlace externo
                if 'slow partner server' in text or 'slow' in text or 'libgen' in text:
                    # found download link!
                    if href.startswith('/'):
                        return f"{self.base_url}{href}"
                    return href
            
            # Fallback if specific classes are missing
            for a in soup.find_all('a', href=True):
                if '/download/' in a['href'] or 'libgen.li' in a['href']:
                    href = a['href']
                    if href.startswith('/'):
                        return f"{self.base_url}{href}"
                    return href

            self.logger.warning(f"No se encontró enlace de descarga para {internal_id}")
        except Exception as e:
            self.logger.error(f"Error obteniendo download url de {internal_id}: {e}")
            
        return None
