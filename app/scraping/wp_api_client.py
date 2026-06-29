"""
WordPress REST API client for querying book sites that expose their API.

Usage:
    client = WordPressApiClient(http_client, "https://epubflix1.com")
    results = await client.search("quijote", limit=20)
    download_url = await client.get_download_url(post_id)
"""

import re
import json
import logging
from typing import Optional
from datetime import datetime
from urllib.parse import quote_plus

from app.core.models import SearchResult
from app.scraping.http_client import HttpClient
from config import settings

logger = logging.getLogger("wp_api")


class WordPressApiClient:
    """
    Client for WordPress REST API v2 endpoints.
    Handles search via /wp/v2/posts and maps responses to SearchResult.
    """

    def __init__(
        self,
        http_client: HttpClient,
        base_url: str,
        provider_id: str,
        requires_scraper: bool = False,
        per_page: int = 20,
    ):
        self._http = http_client
        self._base_url = base_url.rstrip("/")
        self._provider_id = provider_id
        self._requires_scraper = requires_scraper
        self._per_page = per_page

    # ── public API ──────────────────────────────────────────────

    async def search(
        self,
        query: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SearchResult]:
        """
        Search books via WordPress REST API.

        Args:
            query: Search term.
            limit: Max results to return.
            offset: Pagination offset.

        Returns:
            List of SearchResult objects.
        """
        if not query:
            return []

        # Determine which page(s) to fetch
        page = (offset // self._per_page) + 1 if offset else 1
        per_page = min(limit, self._per_page)

        api_url = (
            f"{self._base_url}/wp-json/wp/v2/posts"
            f"?search={quote_plus(query)}"
            f"&per_page={per_page}"
            f"&page={page}"
            f"&_embed"  # include featured media, author, terms
        )

        logger.debug(f"[{self._provider_id}] API request: {api_url}")

        try:
            resp = await self._http.get(api_url, use_scraper=self._requires_scraper)
            raw = json.loads(resp.text) if isinstance(resp.text, str) else []
            # API may return a list of posts, or a dict on error
            posts = raw if isinstance(raw, list) else []
        except Exception as e:
            logger.error(f"[{self._provider_id}] API search failed: {e}")
            return []

        results = []
        for post in posts:
            try:
                result = self._post_to_search_result(post)
                if result:
                    results.append(result)
            except Exception as e:
                logger.warning(f"[{self._provider_id}] Failed to map post {post.get('id')}: {e}")

        # Apply client-side offset if pagination not handled by API
        if offset and page == 1:
            results = results[offset % self._per_page:]

        return results[:limit]

    async def get_download_url(self, post_id: int) -> Optional[str]:
        """
        Fetch a single post/page to extract download URL from content.

        Args:
            post_id: WordPress post ID.

        Returns:
            Download URL or None if not found.
        """
        api_url = f"{self._base_url}/wp-json/wp/v2/posts/{post_id}?_embed"
        logger.debug(f"[{self._provider_id}] Fetching post detail: {api_url}")

        try:
            resp = await self._http.get(api_url, use_scraper=self._requires_scraper)
            post = json.loads(resp.text) if isinstance(resp.text, str) else {}
        except Exception as e:
            logger.error(f"[{self._provider_id}] API post detail failed: {e}")
            return None

        # Try to find download links in content
        content = post.get("content", {}).get("rendered", "")
        if content:
            # Look for common download link patterns in HTML content
            patterns = [
                r'href=["\']([^"\']*\.(?:epub|mobi|pdf|azw3|fb2))["\']',
                r'href=["\']([^"\']*(?:download|descargar)[^"\']*)["\']',
                r'href=["\']([^"\']*(?:mega\.nz|mediafire|drive\.google)[^"\']*)["\']',
            ]
            for pattern in patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    url = match.group(1)
                    if url.startswith("/"):
                        return f"{self._base_url}{url}"
                    return url

        # Try yoast_head_json for og:url or schema
        yoast = post.get("yoast_head_json", {})
        if yoast:
            og_url = yoast.get("og_url", "")
            if og_url:
                return og_url

        return None

    async def get_capabilities_search(self, query: str = "libro") -> bool:
        """Quick check: does the API return results for a test query?"""
        results = await self.search(query, limit=1)
        return len(results) > 0

    async def list_recent(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SearchResult]:
        """
        List most recent posts via WordPress REST API (no search query).

        Used for RSS/browse mode when *Arr apps sync without a search term.
        Drops the `search=` parameter so the API returns newest posts first.
        """
        page = (offset // self._per_page) + 1 if offset else 1
        per_page = min(limit, self._per_page)

        api_url = (
            f"{self._base_url}/wp-json/wp/v2/posts"
            f"?per_page={per_page}"
            f"&page={page}"
            f"&_embed"
        )

        logger.debug(f"[{self._provider_id}] Recent posts: {api_url}")

        try:
            resp = await self._http.get(api_url, use_scraper=self._requires_scraper)
            raw = json.loads(resp.text) if isinstance(resp.text, str) else []
            posts = raw if isinstance(raw, list) else []
        except Exception as e:
            logger.error(f"[{self._provider_id}] API recent posts failed: {e}")
            return []

        results = []
        for post in posts:
            try:
                result = self._post_to_search_result(post)
                if result:
                    results.append(result)
            except Exception as e:
                logger.warning(f"[{self._provider_id}] Failed to map post {post.get('id')}: {e}")

        if offset and page == 1:
            results = results[offset % self._per_page:]

        return results[:limit]

    # ── private helpers ─────────────────────────────────────────

    def _post_to_search_result(self, post: dict) -> Optional[SearchResult]:
        """
        Map a WordPress REST API post object to SearchResult.

        WordPress post structure:
        {
            "id": 123,
            "date": "2026-04-19T08:42:37",
            "slug": "book-title-author-name",
            "link": "https://site.com/book-title/",
            "title": {"rendered": "Book Title | Author Name"},
            "excerpt": {"rendered": "<p>Description...</p>"},
            "content": {"rendered": "<p>Full content with download links</p>"},
            "categories": [4, 7],
            "tags": [12, 15],
            "yoast_head_json": {"og_title": "...", "og_description": "..."},
            "_embedded": {
                "author": [{"name": "..."}],
                "wp:featuredmedia": [{"source_url": "https://..."}],
                "wp:term": [[{"id": 4, "name": "Genre", "slug": "genre"}]]
            }
        }
        """
        post_id = post.get("id")
        if not post_id:
            return None

        # Title: parse "Title | Author" pattern
        title_raw = post.get("title", {}).get("rendered", "")
        title, author = self._parse_title_author(title_raw)

        if not title:
            return None

        # GUID
        guid = f"{self._provider_id}-{post_id}"

        # Link
        link = post.get("link", "")
        if link.startswith("/"):
            link = f"{self._base_url}{link}"

        # Download URL: proxy endpoint
        download_url = (
            f"{settings.EXTERNAL_URL}/api/download"
            f"?provider={self._provider_id}"
            f"&id={post_id}"
            f"&fmt=epub"
        )

        # Date
        pub_date = datetime.now()
        date_str = post.get("date", "")
        if date_str:
            try:
                from datetime import timezone
                pub_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        # Description: prefer excerpt, fallback to yoast
        description = ""
        excerpt = post.get("excerpt", {}).get("rendered", "")
        if excerpt:
            # Strip HTML tags
            description = re.sub(r"<[^>]+>", "", excerpt).strip()
        if not description:
            yoast = post.get("yoast_head_json", {})
            description = yoast.get("og_description", "") or yoast.get("description", "")
        if not description:
            description = f"Libro: {title}"

        # Estimate size from content length (rough)
        content_text = post.get("content", {}).get("rendered", "")
        size_bytes = max(len(content_text.encode("utf-8")) * 2, 500000)

        result = SearchResult(
            title=title,
            guid=guid,
            link=link,
            download_url=download_url,
            size_bytes=size_bytes,
            pub_date=pub_date,
            categories=[7000, 7020, 8000, 8010],
            description=description,
            author=author,
        )

        # Extra attrs from Yoast
        yoast = post.get("yoast_head_json", {})
        if yoast:
            if yoast.get("og_image"):
                result.extra_attrs["cover_url"] = yoast["og_image"][0]["url"] if isinstance(yoast["og_image"], list) else str(yoast["og_image"])
            schema = yoast.get("schema", {})
            if isinstance(schema, dict):
                graph = schema.get("@graph", [])
                for item in graph:
                    if item.get("@type") == "Book":
                        result.extra_attrs["isbn"] = item.get("isbn", "") or ""
                        break

        # Categories from embedded terms
        embedded = post.get("_embedded", {})
        wp_terms = embedded.get("wp:term", [])
        genres = []
        for term_group in wp_terms:
            for term in term_group:
                name = term.get("name", "")
                if name and name.lower() not in ("uncategorized", "sin categoría"):
                    genres.append(name)
        if genres:
            result.extra_attrs["genre"] = ", ".join(genres)

        return result

    @staticmethod
    def _parse_title_author(title_raw: str) -> tuple[str, Optional[str]]:
        """
        Parse "Book Title | Author Name" or "Book Title — Author Name" format.

        Returns (title, author).
        """
        title_raw = title_raw.strip()

        # Try " | " separator
        if " | " in title_raw:
            parts = title_raw.rsplit(" | ", 1)
            return parts[0].strip(), parts[1].strip() if len(parts) > 1 else None

        # Try " — " (em-dash) separator
        if " — " in title_raw:
            parts = title_raw.rsplit(" — ", 1)
            return parts[0].strip(), parts[1].strip() if len(parts) > 1 else None

        # Try " – " (en-dash) separator
        if " – " in title_raw:
            parts = title_raw.rsplit(" – ", 1)
            return parts[0].strip(), parts[1].strip() if len(parts) > 1 else None

        # Try " - " separator at the end (author typically comes last)
        if " - " in title_raw:
            parts = title_raw.rsplit(" - ", 1)
            # Heuristic: if last part looks like an author name (contains uppercase letters after first)
            potential_author = parts[1].strip()
            if potential_author and potential_author[0].isupper():
                return parts[0].strip(), potential_author

        return title_raw, None
