# Phase 1 Findings: WordPress REST API Investigation

**Date**: 2026-06-08
**Status**: Complete

## Executive Summary

Probed WordPress REST API on all 8 WordPress-based book sites integrated in WebTranslatorr.
**4 out of 8 sites have their REST API enabled** and return structured JSON data.
**2 of those 4** (Epubflix1, LectuEpubLibre5) return actual book data when queried.
The other 2 (EpubLibre, Lectulandia) have the API enabled but return empty posts — they likely use custom post types.

## Detailed Results

| Site | Domain | `/wp-json/` | `/wp/v2/posts?search=quijote` | Auth | Notable |
|------|--------|:-----------:|:------------------------------:|:----:|---------|
| **Ebookelo** | ww2.ebookelo.com | 404 | — | — | API disabled |
| **EpubLibre** | epublibre.bid | Yes | Empty `[]` | None advertised | Elementor + Wordfence. CPT likely. |
| **Lectulandia** | ww3.lectulandia.co | Yes | Empty `[]` | Application Passwords | Yoast + Ninja Forms. CPT likely. |
| **Espaebook** | espaebook.cc | Transport error | — | — | Site down/blocked |
| **HolaEbook** | holaebook.com | Redirect | Redirect | — | Redirects to different URL |
| **Epubflix1** | epubflix1.com | **Yes** | **Returns book data** | Application Passwords | `wp/v2/posts` works. Title format: "Book \| Author" |
| **LectuEpubLibre5** | lectuepublibre5.com | **Yes** | **Returns book data** | Application Passwords + 2FA | Same format as Epubflix1 |
| **MundoEpubLibre1** | mundoepublibre1.com | Transport error | — | — | Site down/blocked |

## Data Structure (Epubflix1 & LectuEpubLibre5)

WordPress REST API `/wp/v2/posts` returns standard post objects:

```json
{
  "id": 21172,
  "date": "2026-04-19T08:42:37",
  "slug": "book-title-series-author",
  "link": "https://site.com/book-title/",
  "title": {"rendered": "Book Title | Author Name"},
  "content": {"rendered": "<p>HTML content with download links</p>"},
  "excerpt": {"rendered": "<p>Short description</p>"},
  "type": "post",
  "categories": [4, 7],
  "tags": [12, 15],
  "yoast_head_json": {
    "og_title": "Book Title",
    "og_description": "...",
    "og_image": [{"url": "https://..."}],
    "schema": {"@graph": [...]}
  }
}
```

Key fields for SearchResult mapping:
- `id` → `guid` (as `{provider_id}-{post_id}`)
- `title.rendered` → `title` (parsed as "Book Title | Author Name")
- `link` → `link` (full URL to detail page)
- `excerpt.rendered` → `description`
- `date` → `pub_date`
- `yoast_head_json.schema` → may contain ISBN in Book schema
- `yoast_head_json.og_image` → `extra_attrs["cover_url"]`
- Categories/tags → `extra_attrs["genre"]`

Author is embedded in title using ` | ` separator — no separate author field.

## Actions Taken

### Code Changes
1. **Created `app/scraping/wp_api_client.py`** — WordPress REST API client that queries `/wp/v2/posts`, maps responses to `SearchResult`, and handles pagination.

2. **Updated `app/providers/books/epubflix1.py`** — Hybrid approach:
   - Try WordPress REST API first (fast, structured)
   - Fall back to HTML scraping if API returns no results
   - `get_download_url()` still uses scraping (API content doesn't reliably expose download URLs)

3. **Updated `app/providers/books/lectuepublibre5.py`** — Same hybrid approach as Epubflix1.

4. **Updated `app/providers/books/lectulandia.py`** — Hardened linkCode extraction:
   - Added 7 alternative regex patterns for JS variable extraction
   - Added validation (alphanumeric, 6-32 chars)
   - Added fallback: if `download.php` not found, search for direct download links on detail page

5. **Updated `app/providers/books/ebookelo.py`** — Optimized enrichment:
   - Capped enrichment to MAX_ENRICH=25 results
   - Parallelized enrichment with Semaphore(3) for concurrency control
   - Added `language` field to enriched metadata

### Sites Still Needing Attention (Phase 2)
- **Ebookelo** — ad-gate verification pending (profitablecpmgate.com)
- **Espaebook** — site unreachable, needs retry
- **MundoEpubLibre1** — site unreachable, needs retry
- **HolaEbook** — redirect behavior needs investigation
- **B00k.Bond** — CMS identification pending, transport error

### Providers Not Yet Updated (Phase 3-4)
- **EpubLibre** — API enabled but posts empty (custom post type?). Scraping still primary.
- **Lectulandia** — API enabled but posts empty. Scraping still primary (linkCode hardened).
- **MundoEpubLibre1** — Code almost identical to LectuEpubLibre5. Unification opportunity.

## Next Steps

1. **Phase 2**: Audit HTML structure for sites without working API (Ebookelo, Espaebook, MundoEpubLibre1)
2. **Phase 3**: B00k.Bond CMS identification, HolaEbook redirect investigation
3. **Phase 4**: Unify LectuEpubLibre5 + MundoEpubLibre1 code, implement health checks
