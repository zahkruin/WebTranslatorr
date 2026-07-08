"""
Torrent Blackhole watcher — monitors a directory for .torrent files and
downloads the actual content via the webseed URL embedded in each torrent.

Runs as an asyncio background task inside the server process.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger("blackhole.watcher")

POLL_INTERVAL = 5  # seconds


async def _download_file(provider_id: str, internal_id: str, fmt: str, output_path: str) -> bool:
    """Download the actual file and save it with the correct extension."""
    try:
        # Lazy imports to avoid circular deps at module level
        from app.providers.registry import get_registry
        from app.scraping.http_client import HttpClient

        registry = get_registry()
        prov = registry.get(provider_id)

        internal_id_actual = internal_id if provider_id != "ebookelo" else f"{internal_id}/{fmt}"
        ddl_url = await prov.get_download_url(internal_id_actual, fmt=fmt)
        if not ddl_url:
            logger.warning("No download URL for %s/%s", provider_id, internal_id)
            return False

        http_client = HttpClient(timeout=120, max_retries=2)
        file_bytes = await http_client.download_file(
            ddl_url,
            use_scraper=getattr(prov, 'is_zipped', False) or provider_id == "annasarchive",
        )
        await http_client.close()

        if getattr(prov, 'is_zipped', False):
            from app.utils.zip_extractor import ZipExtractor
            extracted = ZipExtractor.extract_epub_from_memory(file_bytes)
            if extracted:
                file_bytes = extracted
                fmt = "epub"

        ext = fmt if fmt in ("epub", "mobi", "pdf") else "epub"
        final_path = f"{output_path}.{ext}"

        with open(final_path, "wb") as f:
            f.write(file_bytes)

        logger.info("Downloaded %d bytes → %s", len(file_bytes), final_path)
        return True
    except Exception as e:
        logger.error("Download failed for %s/%s: %s", provider_id, internal_id, e)
        return False


def _parse_webseed(url: str) -> tuple[str, str, str] | None:
    """Extract (provider, id, fmt) from a webseed URL like
    /api/download-content?provider=X&id=Y&fmt=Z"""
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        provider = qs.get("provider", [None])[0]
        internal_id = qs.get("id", [None])[0]
        fmt = qs.get("fmt", ["epub"])[0]
        if provider and internal_id:
            return provider, internal_id, fmt
    except Exception:
        pass
    return None


async def _watch_loop(watch_dir: str, output_dir: str) -> None:
    """Main watch loop — polls for .torrent files and processes them."""
    watch_path = Path(watch_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info("Blackhole watcher started: %s → %s", watch_dir, output_dir)

    seen: set[str] = set()

    while True:
        try:
            for f in sorted(watch_path.glob("*.torrent")):
                fname = str(f)
                if fname in seen:
                    continue
                seen.add(fname)

                # Wait a moment for the file to be fully written by Readarr
                await asyncio.sleep(1)
                if f.stat().st_size == 0:
                    seen.discard(fname)
                    continue

                # Parse torrent to extract webseed URL
                try:
                    from bencode import bdecode
                    with open(fname, "rb") as fh:
                        torrent = bdecode(fh.read())
                except Exception:
                    logger.warning("Failed to parse torrent: %s", fname)
                    os.remove(fname)
                    continue

                webseed = None
                url_list = torrent.get("url-list")
                if isinstance(url_list, list) and url_list:
                    ws = url_list[0]
                    webseed = ws if isinstance(ws, str) else ws.decode("utf-8", errors="replace")
                if not webseed:
                    hs = torrent.get("httpseeds")
                    if hs:
                        webseed = hs if isinstance(hs, str) else hs.decode("utf-8", errors="replace")

                if not webseed:
                    logger.warning("No webseed in torrent: %s", fname)
                    os.remove(fname)
                    continue

                parsed = _parse_webseed(webseed)
                if not parsed:
                    logger.warning("Bad webseed URL in torrent: %s → %s", fname, webseed)
                    os.remove(fname)
                    continue

                provider_id, internal_id, fmt = parsed
                out_base = os.path.join(str(output_path), Path(fname).stem)
                success = await _download_file(provider_id, internal_id, fmt, out_base)

                if success:
                    os.remove(fname)
                    logger.info("Processed: %s", fname)
                else:
                    logger.warning("Download failed, keeping: %s", fname)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Watch loop error: %s", e)

        await asyncio.sleep(POLL_INTERVAL)

    logger.info("Blackhole watcher stopped")


def start_blackhole_watcher() -> asyncio.Task | None:
    """Start the blackhole watcher as a background task. Returns the task or None."""
    from config import settings
    watch_dir = (settings.BLACKHOLE_DIR or "").strip()
    if not watch_dir:
        return None

    output_dir = (settings.BLACKHOLE_OUTPUT_DIR or "").strip() or watch_dir

    logger.info("Starting blackhole watcher (watch=%s, output=%s)", watch_dir, output_dir)
    return asyncio.create_task(_watch_loop(watch_dir, output_dir))
