"""
Traduce objetos SearchResult de Python a XML RSS 2.0 compatible
con Torznab/Newznab, consumible por Sonarr, Radarr y Readarr.
"""
from xml.etree.ElementTree import Element, SubElement, tostring
from datetime import datetime

TORZNAB_NS = "http://torznab.com/schemas/2015/feed"
NEWZNAB_NS = "http://www.newznab.com/DTD/2010/feeds/attributes/"


class TorznabMapper:

    @staticmethod
    def results_to_xml(
        results: list,
        offset: int = 0,
        total: int = 0,
        channel_title: str = "WebTranslatorr"
    ) -> str:
        """Genera el XML RSS completo con todos los resultados."""

        rss = Element("rss", attrib={
            "version": "2.0",
            "xmlns:torznab": TORZNAB_NS,
            "xmlns:newznab": NEWZNAB_NS,
        })

        channel = SubElement(rss, "channel")
        SubElement(channel, "title").text = channel_title
        SubElement(channel, "description").text = "Universal Torznab Proxy"
        SubElement(channel, "link").text = "http://localhost:9811"

        # Atributo de respuesta con paginación
        SubElement(channel, "newznab:response", attrib={
            "offset": str(offset),
            "total": str(total or len(results)),
        })

        for result in results:
            TorznabMapper._build_item(channel, result)

        return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(rss, encoding="unicode")

    @staticmethod
    def _build_item(channel: Element, result) -> None:
        """Construye un <item> RSS a partir de un SearchResult."""
        item = SubElement(channel, "item")

        SubElement(item, "title").text = result.title
        SubElement(item, "guid").text = result.guid
        SubElement(item, "link").text = result.link
        SubElement(item, "description").text = result.description

        # pubDate en formato RFC 822
        pub_date = result.pub_date
        if pub_date.tzinfo:
            date_str = pub_date.strftime("%a, %d %b %Y %H:%M:%S %z")
        else:
            date_str = pub_date.strftime("%a, %d %b %Y %H:%M:%S +0000")
        SubElement(item, "pubDate").text = date_str

        # <enclosure> — el *Arr descarga de aquí
        SubElement(item, "enclosure", attrib={
            "url": result.download_url,
            "length": str(result.size_bytes),
            "type": "application/x-bittorrent",
        })

        # Categorías como torznab:attr
        for cat in result.categories:
            SubElement(item, "torznab:attr", attrib={
                "name": "category", "value": str(cat)
            })

        # Atributos obligatorios
        SubElement(item, "torznab:attr", attrib={
            "name": "size", "value": str(result.size_bytes)
        })

        # Seeders/Peers
        if result.seeders is not None:
            SubElement(item, "torznab:attr", attrib={
                "name": "seeders", "value": str(result.seeders)
            })
        if result.peers is not None:
            SubElement(item, "torznab:attr", attrib={
                "name": "peers", "value": str(result.peers)
            })

        # Info hash
        if result.info_hash:
            SubElement(item, "torznab:attr", attrib={
                "name": "infohash", "value": result.info_hash
            })

        # Magnet URI
        if result.magnet_uri:
            SubElement(item, "torznab:attr", attrib={
                "name": "magneturl", "value": result.magnet_uri
            })

        # IMDb ID
        if result.imdb_id:
            SubElement(item, "torznab:attr", attrib={
                "name": "imdbid", "value": result.imdb_id
            })

        # TVDB ID
        if result.tvdb_id:
            SubElement(item, "torznab:attr", attrib={
                "name": "tvdbid", "value": str(result.tvdb_id)
            })

        # Season/Episode
        if result.season is not None:
            SubElement(item, "torznab:attr", attrib={
                "name": "season", "value": str(result.season)
            })
        if result.episode is not None:
            SubElement(item, "torznab:attr", attrib={
                "name": "episode", "value": str(result.episode)
            })

        # Atributos extra dinámicos
        for attr_name, attr_value in result.extra_attrs.items():
            SubElement(item, "torznab:attr", attrib={
                "name": attr_name, "value": attr_value
            })
