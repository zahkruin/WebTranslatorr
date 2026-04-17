import re
import math
from typing import Dict, Any, List
from bs4 import BeautifulSoup

from app.providers.base import BaseProvider
from config import settings


class EpubLibreProvider(BaseProvider):
    def __init__(self, http_client, domain_resolver=None):
        domain = settings.EPUBLIBRE_DOMAIN
        if domain_resolver:
            # We don't have epublibre auto-resolution logic yet, but we will wire it up
            active_domain = domain_resolver.get_current("epublibre")
            if active_domain:
                domain = active_domain
                
        super().__init__(
            provider_id="epublibre",
            display_name="EpubLibre",
            base_url=domain,
            http_client=http_client,
            categories=[7000, 7020, 8000, 8010]
        )

    async def search(self, query: str, category: int = None, limit: int = 100, **kwargs) -> List[Dict[str, Any]]:
        self.logger.info(f"Buscando en EpubLibre: '{query}'")
        results = []
        
        # Búsqueda inicial
        search_url = f"{self.base_url}/?s={query}"
        
        try:
            resp = await self.http_client.get(search_url, use_scraper=True)
            soup = BeautifulSoup(resp.text, 'lxml')
            
            # En EpubLibre, las cards de resultados suelen ser "div.post" o links que contienen "/book/"
            seen_urls = set()
            
            # Recolectamos los enlaces que apunten a /book/ excepto el genérico "Biblioteca"
            for a in soup.select('a[href*="/book/"]'):
                href = a.get('href')
                title = a.get_text(strip=True)
                
                if not href or not title or title.lower() == 'biblioteca' or href in seen_urls:
                    continue
                    
                seen_urls.add(href)
                
                # Vamos a coger el title que haya. A veces hay un h2 o h3 dentro.
                # Generamos un slug interno basado en la URL
                match = re.search(r'/book/([^/]+)/', href)
                internal_id = match.group(1) if match else None
                
                if not internal_id:
                    continue

                item = {
                    "id": internal_id,
                    "title": title,
                    "guid": href,
                    "size": 1000000, # 1MB dummy
                    "link": f"{settings.HOST}:{settings.PORT}/api/download?provider={self.id}&id={internal_id}&fmt=epub",
                    "description": f"Libro: {title}",
                    "pubDate": "Wed, 01 Jan 2020 00:00:00 +0000",
                    "categories": [7020]
                }
                
                results.append(item)
                
                if len(results) >= limit:
                    break

        except Exception as e:
            self.logger.error(f"Error parseando EpubLibre: {e}")
            
        return results

    async def get_download_url(self, internal_id: str, **kwargs) -> str | None:
        """
        Navega a la página del libro y extrae el enlace de descarga para 'epub'.
        """
        fmt = kwargs.get('fmt', 'epub').lower()
        detail_url = f"{self.base_url}/book/{internal_id}/"
        
        try:
            resp = await self.http_client.get(detail_url, use_scraper=True)
            soup = BeautifulSoup(resp.text, 'lxml')
            
            # Buscar el botón de bajar, p.ej: "BAJAR EN EPUB" o similar
            target_text = f"EN {fmt.upper()}"
            for a in soup.find_all('a', href=True):
                text = a.get_text(strip=True).upper()
                if target_text in text or 'DESCARGAR' in text:
                    # found download link!
                    return a['href']
            
            self.logger.warning(f"No se encontró enlace de descarga para {internal_id} en {fmt}")
        except Exception as e:
            self.logger.error(f"Error obteniendo download url de {internal_id}: {e}")
            
        return None
