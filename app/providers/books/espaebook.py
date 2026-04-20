import re
from typing import Dict, Any, List
from bs4 import BeautifulSoup

from app.providers.base import BaseProvider
from config import settings


class EspaebookProvider(BaseProvider):
    def __init__(self, http_client, domain_resolver=None):
        domain = settings.ESPAEBOOK_DOMAIN
        if domain_resolver:
            active_domain = domain_resolver.get_current("espaebook")
            if active_domain:
                domain = active_domain
                
        super().__init__(
            provider_id="espaebook",
            display_name="Espaebook",
            base_url=domain,
            http_client=http_client,
            categories=[7000, 7020, 8000, 8010]
        )

    async def search(self, query: str, category: int = None, limit: int = 100, **kwargs) -> List[Dict[str, Any]]:
        combined_query = self._combine_query(query, kwargs.get('author'), kwargs.get('title'))
        query_to_use = self.normalize_query(combined_query)
        self.logger.info(f"Buscando en Espaebook: '{query_to_use}'")
        if not query_to_use:
            return []
            
        results = []
        
        # Búsqueda GET as in most wp sites
        search_url = f"{self.base_url}/?s={query_to_use}"
        
        try:
            resp = await self.http_client.get(search_url, use_scraper=True)
            soup = BeautifulSoup(resp.text, 'lxml')
            
            seen_urls = set()
            
            # Similar to epublibre, look for /book/ or /libro/
            for a in soup.select('a[href*="/libro/"], a[href*="/book/"], h2.entry-title a'):
                href = a.get('href')
                title = a.get_text(strip=True)
                
                if not href or not title or href in seen_urls:
                    continue
                    
                seen_urls.add(href)
                
                # Extraer un slug válido
                match = re.search(r'/(?:libro|book)/([^/]+)/?', href)
                internal_id = match.group(1) if match else None
                
                if not internal_id:
                    # Alternativa: coger lo ultimo de la url
                    internal_id = [x for x in href.split('/') if x][-1]

                item = {
                    "id": internal_id,
                    "title": title,
                    "guid": href if href.startswith('http') else f"{self.base_url}{href}",
                    "size": 1000000,
                    "link": f"{settings.HOST}:{settings.PORT}/api/download?provider={self.provider_id}&id={internal_id}&fmt=epub",
                    "description": f"Libro: {title}",
                    "pubDate": "Wed, 01 Jan 2020 00:00:00 +0000",
                    "categories": [7020]
                }
                
                results.append(item)
                
                if len(results) >= limit:
                    break

        except Exception as e:
            self.logger.error(f"Error parseando Espaebook: {e}")
            
        return results

    async def get_download_url(self, internal_id: str, **kwargs) -> str | None:
        """
        Espaebook tiene una web para descargar que requiere otro click, igual que Epublibre.
        """
        detail_url = f"{self.base_url}/libro/{internal_id}/" # o book
        
        try:
            resp = await self.http_client.get(detail_url, use_scraper=True)
            
            if resp.status_code == 404:
                # Try fallback
                detail_url = f"{self.base_url}/book/{internal_id}/"
                resp = await self.http_client.get(detail_url, use_scraper=True)
                
            soup = BeautifulSoup(resp.text, 'lxml')
            
            for a in soup.find_all('a', href=True):
                text = a.get_text(strip=True).upper()
                # Botones típicos: "DESCARGAR EPUB"
                if 'EPUB' in text or 'DESCARGAR' in text:
                    # Ignorar enlaces a generos o al mismo book
                    if '/genre/' not in a['href'] and '/autor/' not in a['href'] and '/book/' not in a['href']:
                        # Devuelve el link
                        return a['href']
            
            self.logger.warning(f"No se encontró enlace de descarga para {internal_id}")
        except Exception as e:
            self.logger.error(f"Error obteniendo download url de {internal_id}: {e}")
            
        return None
