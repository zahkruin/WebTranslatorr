"""
Generador de archivos .torrent on-the-fly para book providers.

Readarr espera archivos .torrent válidos de indexers Torznab.
Los book providers devuelven descargas directas (EPUB/PDF/MOBI),
así que creamos un torrent metadata-only con un web seed que
apunta a la descarga real para que Readarr no falle al intentar
parsear el archivo como torrent.
"""
import hashlib
import time
from io import BytesIO

from bencode import bdecode, bencode


TORRENT_PIECE_LENGTH = 262144  # 256 KiB


def generate_torrent(
    file_name: str,
    file_data: bytes,
    announce_url: str = "",
    comment: str = "WebTranslatorr proxy torrent",
    created_by: str = "WebTranslatorr",
    web_seed_url: str | None = None,
) -> tuple[bytes, str, str]:
    pieces = []
    for i in range(0, len(file_data), TORRENT_PIECE_LENGTH):
        chunk = file_data[i:i + TORRENT_PIECE_LENGTH]
        pieces.append(hashlib.sha1(chunk).digest())

    info = {
        b"name": file_name.encode("utf-8"),
        b"piece length": TORRENT_PIECE_LENGTH,
        b"pieces": b"".join(pieces),
        b"length": len(file_data),
    }

    info_bencoded = bencode(info)
    info_hash = hashlib.sha1(info_bencoded).digest()

    torrent = {
        b"info": info,
        b"comment": comment.encode("utf-8"),
        b"created by": created_by.encode("utf-8"),
        b"creation date": int(time.time()),
        # Dummy announce — qBittorrent needs at least one tracker to
        # start the torrent even when downloading purely via webseed.
        b"announce": announce_url.encode("utf-8") if announce_url else b"",
    }

    if web_seed_url:
        # BEP 19: url-list as a list.  Some libtorrent versions also
        # support a single string as a fallback.
        url_bytes = web_seed_url.encode("utf-8")
        torrent[b"url-list"] = [url_bytes]
        torrent[b"httpseeds"] = url_bytes  # BEP 17: single-string fallback

    torrent_bytes = bencode(torrent)
    info_hash_hex = info_hash.hex()
    magnet_uri = (
        f"magnet:?xt=urn:btih:{info_hash_hex}"
        f"&dn={file_name}"
    )
    if announce_url:
        magnet_uri += f"&tr={announce_url}"

    return torrent_bytes, info_hash_hex, magnet_uri


def parse_info_hash(torrent_bytes: bytes) -> str:
    """Extrae el info_hash hex de un archivo .torrent."""
    torrent = bdecode(torrent_bytes)
    info = torrent["info"]
    info_bencoded = bencode(info)
    return hashlib.sha1(info_bencoded).hexdigest()
