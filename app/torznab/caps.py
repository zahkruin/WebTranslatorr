"""Genera el XML de capabilities (/api?t=caps)."""

from xml.etree.ElementTree import Element, SubElement, tostring

from config import settings


class CapsGenerator:

    @staticmethod
    def generate(
        providers: list,
        server_title: str | None = None,
        server_url: str | None = None,
    ) -> str:
        """
        Agrega las capabilities de todos los providers activos
        en un solo XML de caps.

        Cuando se llama desde /api/{provider_id} (single-provider),
        `server_title` recibe el `display_name` del provider y
        `server_url` apunta a `/api/{provider_id}` para que Readarr
        muestre cada indexer con su nombre real y URL correcta.
        """
        # Determinar capacidades agregadas
        supports_book = any(p.supports_book_search for p in providers)
        supports_tv = any(p.supports_tv_search for p in providers)
        supports_movie = any(p.supports_movie_search for p in providers)

        # Recopilar todas las categorías soportadas
        all_categories = set()
        for p in providers:
            all_categories.update(p.supported_categories)

        # Construir XML
        caps = Element("caps")

        # Server info — use configured external URL so *Arr apps can reach us
        external_url = settings.EXTERNAL_URL.rstrip("/") + "/"

        title = server_title or "WebTranslatorr"
        url = server_url or external_url

        SubElement(caps, "server", attrib={
            "version": "1.0",
            "title": title,
            "strapline": "Universal Torznab Proxy",
            "url": url,
        })

        # Limits
        SubElement(caps, "limits", attrib={
            "max": "100",
            "default": "50",
        })

        # Searching capabilities
        searching = SubElement(caps, "searching")

        # Derive supported params from provider capabilities (not hardcoded)
        book_params = set()
        movie_params = set()
        tv_params = set()
        for p in providers:
            book_params.update(p.supported_search_params)
            movie_params.update(p.supported_search_params)
            tv_params.update(p.supported_search_params)

        # Always include "q" for search (all providers support it)
        # Add author and title if any book provider declares them
        book_params.add("q")

        SubElement(searching, "search", attrib={
            "available": "yes",
            "supportedParams": "q",
        })
        SubElement(searching, "book-search", attrib={
            "available": "yes" if supports_book else "no",
            "supportedParams": ",".join(sorted(book_params)),
        })
        SubElement(searching, "tv-search", attrib={
            "available": "yes" if supports_tv else "no",
            "supportedParams": "q,season,ep,tvdbid",
        })
        SubElement(searching, "movie-search", attrib={
            "available": "yes" if supports_movie else "no",
            "supportedParams": "q,imdbid",
        })

        # Categories
        categories = SubElement(caps, "categories")

        # Book categories
        if any(c in all_categories for c in [7000, 7020, 8000, 8010]):
            cat = SubElement(categories, "category", attrib={
                "id": "7000",
                "name": "Books",
            })
            SubElement(cat, "subcat", attrib={"id": "7020", "name": "Ebook"})

        if any(c in all_categories for c in [8000, 8010]):
            cat = SubElement(categories, "category", attrib={
                "id": "8000",
                "name": "Books (alt)",
            })
            SubElement(cat, "subcat", attrib={"id": "8010", "name": "Ebook"})

        # Movie categories
        if any(c in all_categories for c in [2000, 2030, 2040, 2045]):
            cat = SubElement(categories, "category", attrib={
                "id": "2000",
                "name": "Movies",
            })
            if 2030 in all_categories:
                SubElement(cat, "subcat", attrib={"id": "2030", "name": "SD"})
            if 2040 in all_categories:
                SubElement(cat, "subcat", attrib={"id": "2040", "name": "HD"})
            if 2045 in all_categories:
                SubElement(cat, "subcat", attrib={"id": "2045", "name": "UHD"})

        # TV categories
        if any(c in all_categories for c in [5000, 5030, 5040, 5045]):
            cat = SubElement(categories, "category", attrib={
                "id": "5000",
                "name": "TV",
            })
            if 5030 in all_categories:
                SubElement(cat, "subcat", attrib={"id": "5030", "name": "SD"})
            if 5040 in all_categories:
                SubElement(cat, "subcat", attrib={"id": "5040", "name": "HD"})
            if 5045 in all_categories:
                SubElement(cat, "subcat", attrib={"id": "5045", "name": "UHD"})

        # Custom extension: supported languages for translation lookups
        from app.core.languages import SUPPORTED_LANGUAGES
        _langs_elem = SubElement(caps, "languages", attrib={
            "default": settings.DEFAULT_SEARCH_LANGUAGE,
        })
        for code, lang in sorted(SUPPORTED_LANGUAGES.items()):
            SubElement(_langs_elem, "language", attrib={
                "code": code,
                "name": lang.display_name,
            })

        return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(caps, encoding="unicode")
