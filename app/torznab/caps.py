"""Genera el XML de capabilities (/api?t=caps)."""

from xml.etree.ElementTree import Element, SubElement, tostring


class CapsGenerator:

    @staticmethod
    def generate(providers: list) -> str:
        """
        Agrega las capabilities de todos los providers activos
        en un solo XML de caps.
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

        # Server info
        SubElement(caps, "server", attrib={
            "version": "1.0",
            "title": "WebTranslatorr",
            "strapline": "Universal Torznab Proxy",
            "url": "http://localhost:9811/",
        })

        # Limits
        SubElement(caps, "limits", attrib={
            "max": "100",
            "default": "50",
        })

        # Searching capabilities
        searching = SubElement(caps, "searching")
        SubElement(searching, "search", attrib={
            "available": "yes",
            "supportedParams": "q",
        })
        SubElement(searching, "book-search", attrib={
            "available": "yes" if supports_book else "no",
            "supportedParams": "q,author,title",
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

        return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(caps, encoding="unicode")
