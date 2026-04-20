import re
import math
from typing import Dict, Any, List
from bs4 import BeautifulSoup

from app.providers.base import BaseProvider
from config import settings


class LectulandiaProvider(BaseProvider):
    def __init__(self, http_client, domain_resolver=None):
        domain = settings.LECTULANDIA_DOMAIN
        if domain_resolver:
            active_domain = domain_resolver.get_current("lectulandia")
            if active_domain:
                domain = active_domain
                
        super().__init__(
            provider_id="lectulandia",
            display_name="Lectulandia",
            base_url=domain,
            http_client=http_client,
            categories=[7000, 7020, 8000, 8010]
        )

    async def search(self, query: str, category: int = None, limit: int = 100, **kwargs) -> List[Dict[str, Any]]:
        combined_query = self._combine_query(query, kwargs.get('author'), kwargs.get('title'))
        query_to_use = self.normalize_query(combined_query)
        self.logger.info(f"Buscando en Lectulandia: '{query_to_use}'")
        if not query_to_use:
            return []
            
        results = []
        
        # Lectulandia usa path dinámico para la búsqueda
        search_url = f"{self.base_url}/search/{query_to_use}"
        
        try:
            resp = await self.http_client.get(search_url, use_scraper=True)
            soup = BeautifulSoup(resp.text, 'lxml')
            
            seen_urls = set()
            
            # Los resultados son cards que enlazan a /book/...
            for a in soup.select('a[href*="/book/"]'):
                href = a.get('href')
                title = a.get_text(strip=True)
                
                if not href or not title or title.lower() == 'libros' or href in seen_urls:
                    continue
                    
                seen_urls.add(href)
                
                match = re.search(r'/book/([^/]+)/', href)
                internal_id = match.group(1) if match else None
                
                if not internal_id:
                    continue

                item = {
                    "id": internal_id,
                    "title": title,
                    "guid": f"{self.base_url}{href}",
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
            self.logger.error(f"Error parseando Lectulandia: {e}")
            
        return results

    async def get_download_url(self, internal_id: str, **kwargs) -> str | None:
        """
        Lectulandia tiene un proceso de 2 pasos:
        1. Página del libro -> Tiene un enlace a /download.php?...
        2. /download.php devuelve un HTML con javascript `var linkCode = "X";`
        3. El link final es /download/{linkCode}
        """
        detail_url = f"{self.base_url}/book/{internal_id}/"
        
        try:
            resp = await self.http_client.get(detail_url, use_scraper=True)
            soup = BeautifulSoup(resp.text, 'lxml')
            
            download_php_link = None
            for a in soup.find_all('a', href=True):
                if '/download.php?' in a['href']:
                    download_php_link = a['href']
                    break
                    
            if not download_php_link:
                self.logger.warning(f"No se encontró enlace download.php en Lectulandia para {internal_id}")
                return None
                
            # Paso 2: Seguir al intermediario
            inter_url = self.base_url + download_php_link if download_php_link.startswith('/') else download_php_link
            resp_inter = await self.http_client.get(inter_url, follow_redirects=True, use_scraper=True)
            
            # Paso 3: Parsear linkCode
            m = re.search(r'var linkCode = ["\']([^"\']+)["\'];', resp_inter.text)
            if m:
                code = m.group(1)
                final_url = f"{self.base_url}/download/{code}"
                return final_url
            else:
                self.logger.warning(f"No se pudo regex linkCode en download.php de {internal_id}")
            
        except Exception as e:
            self.logger.error(f"Error obteniendo download url de {internal_id}: {e}")
            
        return None
