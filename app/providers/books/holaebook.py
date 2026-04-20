import re
from typing import Dict, Any, List
from bs4 import BeautifulSoup

from app.providers.base import BaseProvider
from config import settings


class HolaEbookProvider(BaseProvider):
    def __init__(self, http_client, domain_resolver=None):
        domain = settings.HOLAEBOOK_DOMAIN
        if domain_resolver:
            active_domain = domain_resolver.get_current("holaebook")
            if active_domain:
                domain = active_domain
                
        super().__init__(
            provider_id="holaebook",
            display_name="HolaEbook",
            base_url=domain,
            http_client=http_client,
            categories=[7000, 7020, 8000, 8010]
        )
        self.is_zipped = True  # HolaEbook descarga ZIPs

    async def search(self, query: str, category: int = None, limit: int = 100, **kwargs) -> List[Dict[str, Any]]:
        combined_query = self._combine_query(query, kwargs.get('author'), kwargs.get('title'))
        query_to_use = self.normalize_query(combined_query)
        self.logger.info(f"Buscando en HolaEbook: '{query_to_use}'")
        if not query_to_use:
            return []
            
        results = []
        
        # HolaEbook suele usar ?s=query o similar si es WP. 
        # Si es un script custom, a veces es buscar.php?q=
        search_url = f"{self.base_url}/search?q={query_to_use}"
        
        try:
            resp = await self.http_client.get(search_url, use_scraper=True)
            if resp.status_code == 404:
                 # Fallback a standar wordpress form
                 search_url = f"{self.base_url}/?s={query_to_use}"
                 resp = await self.http_client.get(search_url, use_scraper=True)
                 
            soup = BeautifulSoup(resp.text, 'lxml')
            
            seen_urls = set()
            
            # Link a /book/, /libro/ o /descargar/
            for a in soup.select('a[href*="/libro"], a[href*="/book"]'):
                href = a.get('href')
                title = a.get_text(strip=True)
                
                if not href or not title or href in seen_urls:
                    continue
                    
                seen_urls.add(href)
                
                # Extraer un slug válido
                internal_id = [x for x in href.split('/') if x][-1].replace('.html', '')

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
            self.logger.error(f"Error parseando HolaEbook: {e}")
            
        return results

    async def get_download_url(self, internal_id: str, **kwargs) -> str | None:
        """
        HolaEbook tiene una página de descarga donde hay botones a mirrors.
        """
        # Haremos un guessed request al libro, ya que HolaEbook a veces tiene rutas directas
        # Si no lo encontramos, retornamos none
        # (Esto requeriría analizar exactamente su HTML pero con cloudscraper generalizamos)
        
        detail_url = f"{self.base_url}/libro/{internal_id}.html"
        
        try:
            resp = await self.http_client.get(detail_url, use_scraper=True)
            if resp.status_code != 200:
                detail_url = f"{self.base_url}/book/{internal_id}/"
                resp = await self.http_client.get(detail_url, use_scraper=True)
                
            soup = BeautifulSoup(resp.text, 'lxml')
            
            for a in soup.find_all('a', href=True):
                text = a.get_text(strip=True).upper()
                if 'EPUB' in text or 'DESCARGAR' in text or 'DOWNLOAD' in text:
                    # HolaEbook entrega archivos ZIP, o enlaza a Zippyshare/Mega
                    return a['href']
            
            self.logger.warning(f"No se encontró enlace de descarga para {internal_id}")
        except Exception as e:
            self.logger.error(f"Error obteniendo download url de {internal_id}: {e}")
            
        return None
