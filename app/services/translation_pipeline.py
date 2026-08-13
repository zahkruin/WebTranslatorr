"""
Translation pipeline for literary titles (English → Spanish).

Orchestrates a 4-phase cascade with silent fallback:
  1. Local SQLite cache
  2. Wikidata SPARQL lookup (free, no rate limits)
  3. Google Books API
  4. TitleCleaner post-processing

All external calls are async, exceptions are logged but never propagated.
"""

import asyncio
import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import aiosqlite
import httpx

from config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Phase output dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TranslationResult:
    """Immutable result of a translation pipeline lookup.

    Attributes:
        title_es: Translated title in the target language.
        source: Origin of the translation ("cache", "wikidata", "google_books").
        confidence: Confidence score (1.0 = cache, 0.95 = wikidata, 0.70 = google_books).
        target_lang: ISO 639-1 code of the target language (default "es").
    """
    title_es: str
    source: str
    confidence: float
    target_lang: str = "es"


# ---------------------------------------------------------------------------
# Phase 1 — Local SQLite cache
# ---------------------------------------------------------------------------

class TranslationCache:
    """Persistent English→Spanish translation cache backed by SQLite.

    Avoids redundant external API calls for titles that have already
    been resolved.  Uses WAL journal mode for concurrent read/write
    and an ``asyncio.Lock`` to serialise writes.

    Can be used as an async context manager (``async with``).
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        """Initialise the cache layer (does NOT open the database yet).

        Args:
            db_path: Path to the SQLite database file.  Defaults to
                     ``settings.TRANSLATION_CACHE_PATH`` or
                     ``data/translation_cache.db``.
        """
        raw = db_path or settings.TRANSLATION_CACHE_PATH or ""
        self._db_path = Path(raw) if raw else Path("data/translation_cache.db")
        self._conn: Optional[aiosqlite.Connection] = None
        self._write_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalise a string for deterministic hashing.

        Lowercases, strips punctuation, collapses whitespace,
        deduplicates words and sorts them alphabetically so
        that ``Warbreaker Brandon Sanderson`` and
        ``Brandon Sanderson Warbreaker`` produce the same key.

        Args:
            text: Raw input string (may be *None* or empty).

        Returns:
            Normalised string or ``""`` when input is empty.
        """
        if not text:
            return ""
        text = text.lower()
        text = re.sub(r"[^\w\s]", "", text)
        words = text.split()
        deduped: list[str] = []
        seen: set[str] = set()
        for w in words:
            if w not in seen:
                seen.add(w)
                deduped.append(w)
        return " ".join(sorted(deduped)).strip()

    @classmethod
    def _compute_hash(cls, title_en: str, author: Optional[str], target_lang: str = "es") -> str:
        """Produce a deterministic SHA-256 hash for a title+author+language tuple.

        Args:
            title_en: English title.
            author: Author name (optional).
            target_lang: ISO 639-1 target language code.

        Returns:
            Hex-encoded SHA-256 digest.
        """
        normalized = cls._normalize(title_en) + "|" + cls._normalize(author or "") + "|" + target_lang
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Open the database, enable WAL, and create the schema.

        Safe to call multiple times — subsequent calls are no-ops.
        """
        if self._conn is not None:
            return
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(str(self._db_path))
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._create_schema()
        logger.debug("TranslationCache connected to %s", self._db_path)

    async def _create_schema(self) -> None:
        """Create the ``translation_cache`` table and index if missing.

        The schema is evolved in-place: if the ``target_lang`` column
        is absent it will be added automatically.
        """
        assert self._conn is not None
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS translation_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title_en_hash TEXT NOT NULL,
                title_en TEXT NOT NULL,
                author TEXT,
                title_es TEXT NOT NULL,
                source TEXT NOT NULL,
                confidence REAL NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                hit_count INTEGER NOT NULL DEFAULT 0,
                last_hit_at TEXT,
                target_lang TEXT NOT NULL DEFAULT 'es'
            )
            """
        )
        # Migration: add target_lang column if missing (for existing databases)
        try:
            await self._conn.execute(
                "ALTER TABLE translation_cache ADD COLUMN target_lang TEXT NOT NULL DEFAULT 'es'"
            )
        except Exception:
            # Column already exists — ignore
            pass
        await self._conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_translation_cache_hash "
            "ON translation_cache(title_en_hash)"
        )
        await self._conn.commit()

    async def close(self) -> None:
        """Close the database connection gracefully."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            logger.debug("TranslationCache connection closed")

    async def __aenter__(self) -> "TranslationCache":
        await self.connect()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def get(
        self, title_en: str, author: Optional[str] = None, target_lang: str = "es"
    ) -> Optional[TranslationResult]:
        """Look up a cached translation.

        Args:
            title_en: English title.
            author: Author name (optional).
            target_lang: ISO 639-1 target language code.

        Returns:
            Cached ``TranslationResult`` or ``None`` on miss.
        """
        if self._conn is None:
            await self.connect()
        assert self._conn is not None
        async with self._write_lock:
            h = self._compute_hash(title_en, author, target_lang)
            cursor = await self._conn.execute(
                "SELECT title_es, source, confidence, target_lang FROM translation_cache "
                "WHERE title_en_hash = ?",
                (h,),
            )
            row = await cursor.fetchone()
            await cursor.close()
            if row is None:
                return None
            await self._conn.execute(
                "UPDATE translation_cache "
                "SET hit_count = hit_count + 1, last_hit_at = datetime('now') "
                "WHERE title_en_hash = ?",
                (h,),
            )
            await self._conn.commit()
            return TranslationResult(
                title_es=row[0],
                source=row[1],
                confidence=row[2],
                target_lang=row[3] if len(row) > 3 else "es",
            )

    async def set(
        self,
        title_en: str,
        author: Optional[str],
        title_es: str,
        source: str,
        confidence: float,
        target_lang: str = "es",
    ) -> None:
        """Store a translation in the cache (upsert).

        Args:
            title_en: English title.
            author: Author name (optional).
            title_es: Translated title.
            source: Origin of the translation.
            confidence: Confidence score.
            target_lang: ISO 639-1 target language code.
        """
        if self._conn is None:
            await self.connect()
        assert self._conn is not None
        h = self._compute_hash(title_en, author, target_lang)
        async with self._write_lock:
            await self._conn.execute(
                "INSERT OR REPLACE INTO translation_cache "
                "(title_en_hash, title_en, author, title_es, source, confidence, target_lang) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (h, title_en, author or None, title_es, source, confidence, target_lang),
            )
            await self._conn.commit()

    async def invalidate_one(
        self, title_en: str, author: Optional[str] = None, target_lang: str = "es"
    ) -> bool:
        """Remove a single cache entry.

        Args:
            title_en: English title.
            author: Author name (optional).
            target_lang: ISO 639-1 target language code.

        Returns:
            ``True`` if an entry was deleted, ``False`` otherwise.
        """
        if self._conn is None:
            await self.connect()
        assert self._conn is not None
        h = self._compute_hash(title_en, author, target_lang)
        cursor = await self._conn.execute(
            "DELETE FROM translation_cache WHERE title_en_hash = ?", (h,)
        )
        deleted = cursor.rowcount > 0
        await cursor.close()
        await self._conn.commit()
        return deleted

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    async def stats(self) -> dict[str, int]:
        """Return aggregate cache statistics.

        Returns:
            Dictionary with keys ``entries`` and ``total_hits``.
        """
        if self._conn is None:
            await self.connect()
        assert self._conn is not None
        cursor = await self._conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(hit_count), 0) FROM translation_cache"
        )
        row = await cursor.fetchone()
        await cursor.close()
        return {"entries": row[0] if row else 0, "total_hits": row[1] if row else 0}


# ---------------------------------------------------------------------------
# Phase 2 — Wikidata SPARQL lookup
# ---------------------------------------------------------------------------

class WikidataClient:
    """Look up Spanish book titles via Wikidata SPARQL queries.

    Free service with no API key or rate limit.  Falls back silently
    on any error.
    """

    SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
    ENTITY_DATA_URL = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
    USER_AGENT = (
        "WebTranslatorr/1.0 (translation pipeline; "
        "https://github.com/user/WebTranslatorr)"
    )

    def __init__(
        self,
        client: httpx.AsyncClient,
        timeout: Optional[int] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        """Initialise the Wikidata client.

        Args:
            client: Shared ``httpx.AsyncClient``.
            timeout: Request timeout in seconds (defaults to
                     ``settings.TRANSLATION_PIPELINE_TIMEOUT``).
            enabled: Whether Wikidata lookups are enabled (defaults to
                     ``settings.TRANSLATION_PIPELINE_WIKIDATA_ENABLED``).
        """
        self._client = client
        self._timeout = timeout or settings.TRANSLATION_PIPELINE_TIMEOUT
        self._enabled = (
            enabled
            if enabled is not None
            else settings.TRANSLATION_PIPELINE_WIKIDATA_ENABLED
        )
        self._logger = logging.getLogger(f"{__name__}.wikidata")

    # ------------------------------------------------------------------
    # SPARQL helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _escape_sparql(value: str) -> str:
        """Escape special characters for safe SPARQL string injection."""
        return (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_translated_title(
        self, title_en: str, author: Optional[str] = None, target_lang: str = "es"
    ) -> Optional[str]:
        """Resolve a translated title via Wikidata.

        Args:
            title_en: English title (source language).
            author: Author name (optional).
            target_lang: ISO 639-1 / Wikidata language tag for the target
                         language (e.g. ``"es"``, ``"fr"``, ``"de"``).

        Returns:
            Translated title string, or ``None`` if not found / errored.
        """
        if not self._enabled:
            return None

        result = await self._run_sparql_query(title_en, author, target_lang)
        if result is None and author and title_en.lower().endswith(author.lower()):
            stripped_title = title_en[: -len(author)].strip()
            if stripped_title:
                self._logger.debug(
                    "Wikidata retry with stripped title: '%s'", stripped_title
                )
                result = await self._run_sparql_query(stripped_title, author, target_lang)
        return result

    async def get_spanish_title(
        self, title_en: str, author: Optional[str] = None
    ) -> Optional[str]:
        """Resolve a Spanish title via Wikidata (backwards-compatible wrapper).

        Delegates to :meth:`get_translated_title` with ``target_lang="es"``.
        """
        return await self.get_translated_title(title_en, author, target_lang="es")

    async def _run_sparql_query(
        self, title_en: str, author: Optional[str] = None, target_lang: str = "es"
    ) -> Optional[str]:
        escaped_title = self._escape_sparql(title_en)
        author_clause = ""
        if author:
            escaped_author = self._escape_sparql(author)
            author_clause = (
                f"?item wdt:P50 ?author_entity. "
                f'?author_entity rdfs:label "{escaped_author}"@en.'
            )

        query = (
            "SELECT ?item ?label_target WHERE {"
            f"  ?item rdfs:label \"{escaped_title}\"@en."
            f"  {author_clause}"
            "  ?item rdfs:label ?label_target."
            f'  FILTER(LANG(?label_target) = "{target_lang}")'
            "} LIMIT 3"
        )

        try:
            sparql_resp = await self._client.post(
                self.SPARQL_ENDPOINT,
                data={"format": "json", "query": query},
                headers={
                    "User-Agent": self.USER_AGENT,
                    "Accept": "application/json",
                },
                timeout=self._timeout,
            )
            sparql_resp.raise_for_status()
            data = sparql_resp.json()

            bindings = data.get("results", {}).get("bindings", [])
            if not bindings:
                return None

            item_url = bindings[0].get("item", {}).get("value", "")
            qid = item_url.rsplit("/", 1)[-1] if item_url else None
            if not qid:
                return None

            entity_resp = await self._client.get(
                self.ENTITY_DATA_URL.format(qid=qid),
                headers={"User-Agent": self.USER_AGENT},
                timeout=self._timeout,
            )
            entity_resp.raise_for_status()
            entity_data = entity_resp.json()

            label_target = (
                entity_data.get("entities", {})
                .get(qid, {})
                .get("labels", {})
                .get(target_lang, {})
                .get("value")
            )
            return label_target

        except (
            httpx.HTTPError,
            KeyError,
            IndexError,
            json.JSONDecodeError,
        ) as exc:
            self._logger.warning(
                "Wikidata lookup failed for '%s': %s", title_en, exc
            )
            return None


# ---------------------------------------------------------------------------
# Phase 3 — Google Books API
# ---------------------------------------------------------------------------

class GoogleBooksClient:
    """Look up Spanish book titles via the Google Books API.

    Requires a valid API key.  Respects rate-limit (429) and access-denied
    (403) responses gracefully.
    """

    BASE_URL = "https://www.googleapis.com/books/v1/volumes"

    def __init__(
        self,
        client: httpx.AsyncClient,
        api_key: Optional[str] = None,
        timeout: Optional[int] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        """Initialise the Google Books client.

        Args:
            client: Shared ``httpx.AsyncClient``.
            api_key: Google Books API key (defaults to
                     ``settings.GOOGLE_BOOKS_API_KEY``).
            timeout: Request timeout in seconds (defaults to
                     ``settings.TRANSLATION_PIPELINE_TIMEOUT``).
            enabled: Whether Google Books lookups are enabled (defaults to
                     ``settings.TRANSLATION_PIPELINE_GOOGLE_BOOKS_ENABLED``).
        """
        self._client = client
        self._api_key = api_key or settings.GOOGLE_BOOKS_API_KEY or None
        if not self._api_key:
            self._api_key = None
        self._timeout = timeout or settings.TRANSLATION_PIPELINE_TIMEOUT
        self._enabled = (
            enabled
            if enabled is not None
            else settings.TRANSLATION_PIPELINE_GOOGLE_BOOKS_ENABLED
        )
        self._logger = logging.getLogger(f"{__name__}.googlebooks")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_translated_title(
        self, title_en: str, author: Optional[str] = None, target_lang: str = "es"
    ) -> Optional[str]:
        """Resolve a translated title via Google Books.

        Multi-phase lookup, parametrised by target language:

        1. Search without langRestrict to find the book's
           canonical volume.
        2. Look up author's works in the target language and match by
           published date proximity.
        3. Fallback: search by author alone with langRestrict and
           pick the first target-language result.
        4. Unrestricted fallback: author search without langRestrict,
           return first title that differs from the English input.

        Args:
            title_en: English title.
            author: Author name (optional).
            target_lang: ISO 639-1 / Google Books language code for
                         ``langRestrict`` and ``volumeInfo.language``
                         (e.g. ``"es"``, ``"fr"``, ``"de"``).

        Returns:
            Translated title string, or ``None`` if not found / errored.
        """
        if not self._enabled or not self._api_key:
            return None

        q = f'intitle:"{title_en}"'
        if author:
            q += f'+inauthor:"{author}"'

        base_params = {
            "maxResults": 3,
            "printType": "books",
            "key": self._api_key,
        }

        try:
            # ---- Phase 1: find the book in any language ---------------
            resp = await self._client.get(
                self.BASE_URL,
                params={**base_params, "q": q},
                timeout=self._timeout,
            )

            if resp.status_code in (429, 403):
                self._logger.warning(
                    "Google Books access denied (%s)", resp.status_code
                )
                return None
            resp.raise_for_status()

            data = resp.json()
            items = data.get("items", [])
            if not items:
                return None

            canonical_volume = items[0]
            canonical_vi = canonical_volume.get("volumeInfo", {})
            canonical_date = canonical_vi.get("publishedDate", "")

            # ---- Phase 2: author search in target language, match by date --
            if author:
                author_es_q = f'inauthor:"{author}"'
                es_resp = await self._client.get(
                    self.BASE_URL,
                    params={
                        **base_params,
                        "q": author_es_q,
                        "langRestrict": target_lang,
                        "maxResults": 20,
                    },
                    timeout=self._timeout,
                )

                if es_resp.status_code not in (429, 403):
                    es_resp.raise_for_status()
                    es_data = es_resp.json()
                    es_items = es_data.get("items", [])

                    for item in es_items:
                        vi = item.get("volumeInfo", {})
                        if vi.get("language") != target_lang:
                            continue
                        es_date = vi.get("publishedDate", "")
                        if es_date and canonical_date:
                            es_year = es_date[:4]
                            en_year = canonical_date[:4]
                            if es_year == en_year:
                                es_title = self._get_best_title(vi)
                                if es_title and es_title != title_en:
                                    self._logger.debug(
                                        "Google Books date-matched: '%s' -> '%s'",
                                        title_en, es_title,
                                    )
                                    return es_title

            # ---- Phase 3: fallback – first target-language result by author -
            if author:
                author_es_q_fb = f'inauthor:"{author}"'
                es_resp_fb = await self._client.get(
                    self.BASE_URL,
                    params={
                        **base_params,
                        "q": author_es_q_fb,
                        "langRestrict": target_lang,
                        "maxResults": 20,
                    },
                    timeout=self._timeout,
                )

                if es_resp_fb.status_code not in (429, 403):
                    es_resp_fb.raise_for_status()
                    es_data_fb = es_resp_fb.json()

                    for item in es_data_fb.get("items", []):
                        vi = item.get("volumeInfo", {})
                        if vi.get("language") != target_lang:
                            continue
                        es_title = self._get_best_title(vi)
                        if es_title and es_title.lower() != title_en.lower():
                            self._logger.debug(
                                "Google Books fallback: '%s' -> '%s'",
                                title_en, es_title,
                            )
                            return es_title

            # ---- Phase 4: unrestricted fallback ---------------------------
            if author:
                author_any_q = f'inauthor:"{author}"'
                any_resp = await self._client.get(
                    self.BASE_URL,
                    params={
                        **base_params,
                        "q": author_any_q,
                        "maxResults": 20,
                    },
                    timeout=self._timeout,
                )

                if any_resp.status_code not in (429, 403):
                    any_resp.raise_for_status()
                    any_data = any_resp.json()

                    for item in any_data.get("items", []):
                        vi = item.get("volumeInfo", {})
                        any_title = self._get_best_title(vi)
                        if any_title and any_title.lower() != title_en.lower():
                            self._logger.debug(
                                "Google Books unrestricted fallback: '%s' -> '%s'",
                                title_en, any_title,
                            )
                            return any_title

            return None

        except httpx.HTTPError as exc:
            self._logger.warning(
                "Google Books lookup failed for '%s': %s", title_en, exc
            )
            return None

    async def get_spanish_title(
        self, title_en: str, author: Optional[str] = None
    ) -> Optional[str]:
        """Resolve a Spanish title via Google Books (backwards-compatible wrapper).

        Delegates to :meth:`get_translated_title` with ``target_lang="es"``.
        """
        return await self.get_translated_title(title_en, author, target_lang="es")

    @staticmethod
    def _get_best_title(volume_info: dict) -> Optional[str]:
        """Return the best display title from a volumeInfo dict."""
        title = volume_info.get("title")
        subtitle = volume_info.get("subtitle")
        if title and subtitle:
            return f"{title}: {subtitle}"
        return title


# ---------------------------------------------------------------------------
# Phase 4 — Title cleaner (post-processing)
# ---------------------------------------------------------------------------

class TitleCleaner:
    """Strip editorial metadata from Google Books titles.

    Applies a fixed sequence of regex patterns, each guarded by a
    revert-on-empty rule (except the final whitespace collapse).
    """

    # Regex patterns applied in order.  Each tuple is (pattern, replacement).
    _PATTERNS: list[tuple[str, str]] = [
        (r'\s*\[Edición\s+de\s+bolsillo\]', ""),
        (r'\s*\[Kindle\s+Edition\]', ""),
        (r'\s*\(Spanish\s+Edition\)', ""),
        (r'\s*\(Edición\s+en\s+español\)', ""),
        (r'\s*:\s*A\s+Novel\s*$', ""),
        (r'\s*-\s*Vol\.\s*\d+.*$', ""),
        (r'\s*\(Volume\s*\d+.*?\)', ""),
        (r'\s*\(Book\s*\d+.*?\)', ""),
        (r'\s*\(\d{4}\)', ""),
        (r'\s*\[.*?\]', ""),
        (r'\s+', " "),  # Collapse multiple spaces (no revert guard needed)
    ]

    @classmethod
    def clean(cls, raw_title: str) -> str:
        """Clean editorial metadata from a raw title string.

        Args:
            raw_title: Raw title as returned by an external API.

        Returns:
            Cleaned title string.
        """
        result = raw_title
        for i, (pattern, replacement) in enumerate(cls._PATTERNS):
            candidate = re.sub(pattern, replacement, result)
            # Guard: revert if the pattern emptied the title (skip for
            # the whitespace-collapse pattern, which is always last).
            if i < len(cls._PATTERNS) - 1 and not candidate.strip():
                continue
            result = candidate
        return result.strip()


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------

class TranslationPipeline:
    """Orchestrate the 4-phase translation cascade.

    Usage as async context manager::

        async with TranslationPipeline() as pipeline:
            result = await pipeline.translate("The Name of the Wind", "Patrick Rothfuss")

    Phases are tried in order; the first success short-circuits the rest.
    """

    def __init__(self) -> None:
        """Initialise the pipeline (does NOT open connections yet)."""
        self._http_client: Optional[httpx.AsyncClient] = None
        self._cache: Optional[TranslationCache] = None
        self._wikidata: Optional[WikidataClient] = None
        self._google_books: Optional[GoogleBooksClient] = None
        self._cleaner = TitleCleaner()
        self._logger = logging.getLogger(f"{__name__}.pipeline")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "TranslationPipeline":
        self._http_client = httpx.AsyncClient()
        self._cache = TranslationCache()
        await self._cache.connect()

        if settings.TRANSLATION_PIPELINE_WIKIDATA_ENABLED:
            self._wikidata = WikidataClient(
                self._http_client,
                timeout=settings.TRANSLATION_PIPELINE_TIMEOUT,
                enabled=True,
            )

        if settings.TRANSLATION_PIPELINE_GOOGLE_BOOKS_ENABLED:
            self._google_books = GoogleBooksClient(
                self._http_client,
                api_key=settings.GOOGLE_BOOKS_API_KEY,
                timeout=settings.TRANSLATION_PIPELINE_TIMEOUT,
                enabled=True,
            )

        return self

    async def __aexit__(self, *args: object) -> None:
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None
        if self._cache is not None:
            await self._cache.close()
            self._cache = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def _title_variants(title: str) -> list[str]:
        """Generate search variants for a book title.

        Returns the original title, with/without leading "The".
        For combined "Author ... Title" queries from Readarr t=search,
        strips one trailing word at a time (up to half the input length)
        so that the pure title remains.
        """
        variants = [title]
        lower = title.lower().strip()
        if lower.startswith("the "):
            variants.append(title[4:].strip())
        else:
            variants.append("The " + title.strip())
        words = lower.split()
        total = len(words)
        max_strips = max(1, total // 2)
        for strip_count in range(1, max_strips + 1):
            if total - strip_count < 2:
                break
            head = " ".join(words[: total - strip_count]).strip()
            if head and head not in ("the", "a", "an"):
                origin = title[: len(head)]
                variants.append(origin.strip())
                if lower.startswith("the "):
                    without_the = origin[4:].strip()
                    if without_the:
                        variants.append(without_the)
        seen = set()
        unique = []
        for v in variants:
            key = v.lower().strip()
            if key and key not in seen:
                seen.add(key)
                unique.append(v)
        return unique

    async def translate(
        self,
        title_en: str,
        author: Optional[str] = None,
        target_lang: "SearchLanguage | str | None" = None,
    ) -> Optional[TranslationResult]:
        """Translate an English book title to the target language.

        Cascades through cache → Wikidata → Google Books with silent
        fallback.  All title variants are tried against each phase
        before falling through to the next one.

        Args:
            title_en: English title (required, non-empty).
            author: Author name (optional, improves accuracy).
            target_lang: Target ``SearchLanguage`` instance, ISO 639-1
                         code string, or ``None`` (defaults to ``"es"``).

        Returns:
            ``TranslationResult`` or ``None`` if all phases fail.
        """
        if not title_en or not title_en.strip():
            return None

        from app.core.languages import SearchLanguage as SL, resolve_language

        if target_lang is None:
            lang = resolve_language("es")
        elif isinstance(target_lang, str):
            lang = resolve_language(target_lang)
        else:
            lang = target_lang

        lang_code = lang.wikidata_code  # ISO 639-1, same for both backends

        variants = self._title_variants(title_en)

        # ---- Phase 1: Local cache (all variants) ----------------------
        if self._cache is not None:
            for variant in variants:
                try:
                    result = await self._cache.get(variant, author, target_lang=lang_code)
                    if result is not None:
                        self._logger.debug(
                            "Cache hit for '%s' by %s (lang=%s)",
                            variant, author, lang_code,
                        )
                        return result
                except Exception as exc:
                    self._logger.warning("Cache lookup error: %s", exc)

        # ---- Phase 2: Wikidata (all variants before falling back) -----
        if self._wikidata is not None:
            for variant in variants:
                try:
                    title_translated = await self._wikidata.get_translated_title(
                        variant, author, target_lang=lang_code
                    )
                    if title_translated is not None and title_translated.strip():
                        if self._cache is not None:
                            await self._cache.set(
                                variant, author, title_translated, "wikidata", 0.95,
                                target_lang=lang_code,
                            )
                        return TranslationResult(
                            title_es=title_translated,
                            source="wikidata",
                            confidence=0.95,
                            target_lang=lang_code,
                        )
                except Exception as exc:
                    self._logger.warning("Wikidata phase error: %s", exc)

        # ---- Phase 3: Google Books (all variants) ---------------------
        if self._google_books is not None:
            for variant in variants:
                try:
                    title_translated = await self._google_books.get_translated_title(
                        variant, author, target_lang=lang_code
                    )
                    if title_translated is not None and title_translated.strip():
                        cleaned = self._cleaner.clean(title_translated)
                        if cleaned:
                            if self._cache is not None:
                                await self._cache.set(
                                    variant,
                                    author,
                                    cleaned,
                                    "google_books",
                                    0.70,
                                    target_lang=lang_code,
                                )
                            return TranslationResult(
                                title_es=cleaned,
                                source="google_books",
                                confidence=0.70,
                                target_lang=lang_code,
                            )
                except Exception as exc:
                    self._logger.warning("Google Books phase error: %s", exc)

        # ---- Fallback ------------------------------------------------
        return None

    async def get_stats(self) -> dict[str, int]:
        """Return pipeline-level cache statistics.

        Returns:
            Dictionary with keys ``entries`` and ``total_hits``.
        """
        if self._cache is not None:
            return await self._cache.stats()
        return {"entries": 0, "total_hits": 0}

    async def invalidate(
        self, title_en: str, author: Optional[str] = None, target_lang: str = "es"
    ) -> bool:
        """Invalidate a single cache entry.

        Args:
            title_en: English title.
            author: Author name (optional).
            target_lang: ISO 639-1 target language code.

        Returns:
            ``True`` if an entry was deleted.
        """
        if self._cache is not None:
            return await self._cache.invalidate_one(title_en, author, target_lang)
        return False


# ---------------------------------------------------------------------------
# Module-level singleton (lazy-loaded, used by the search endpoint)
# ---------------------------------------------------------------------------

_translation_pipeline: Optional[TranslationPipeline] = None
_pipeline_lock = asyncio.Lock()


async def get_translation_pipeline() -> Optional[TranslationPipeline]:
    """Return a shared TranslationPipeline instance (lazy-loaded singleton).

    The pipeline is only created when
    ``settings.TRANSLATION_PIPELINE_SEARCH_ENABLED`` is True and
    connects once — subsequent calls return the same instance.

    Returns:
        Configured ``TranslationPipeline`` or ``None`` if disabled.
    """
    global _translation_pipeline

    if not settings.TRANSLATION_PIPELINE_SEARCH_ENABLED:
        return None

    if _translation_pipeline is not None:
        return _translation_pipeline

    async with _pipeline_lock:
        # Double-check after acquiring the lock
        if _translation_pipeline is not None:
            return _translation_pipeline

        pipeline = TranslationPipeline()
        await pipeline.__aenter__()
        _translation_pipeline = pipeline
        logger.info("TranslationPipeline singleton initialised")
        return _translation_pipeline


async def shutdown_translation_pipeline() -> None:
    """Gracefully shut down the shared TranslationPipeline singleton."""
    global _translation_pipeline
    if _translation_pipeline is not None:
        await _translation_pipeline.__aexit__(None, None, None)
        _translation_pipeline = None
        logger.info("TranslationPipeline singleton shut down")
