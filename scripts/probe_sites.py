#!/usr/bin/env python3
"""
Batch site validation script for WebTranslatorr.

Probes book/mixed sites from site-catalog.csv to assess connectivity,
detect Cloudflare/JS protections, login requirements, and classify
implementation complexity. Updates the CSV with findings.

Usage:
    python scripts/probe_sites.py --dry-run
    python scripts/probe_sites.py --limit 5
    python scripts/probe_sites.py --start-from SITE-0610 --limit 10
    python scripts/probe_sites.py --force  # reprobe already-classified sites
"""

import asyncio
import argparse
import csv
import logging
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on sys.path so `app` imports work when run standalone
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import httpx
from app.scraping.http_client import HttpClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CSV_COLUMNS = [
    "id", "name", "url", "language", "content_type", "formats",
    "search_method", "search_url_template", "pagination",
    "has_cloudflare", "requires_js", "requires_login", "has_captcha",
    "download_direct", "complexity", "score", "estimated_volume",
    "update_frequency", "notes", "discovery_source", "last_verified",
]

UPDATABLE_FIELDS = [
    "has_cloudflare", "requires_js", "requires_login", "has_captcha",
    "download_direct", "complexity", "notes",
]

TARGET_CONTENT_TYPES = {"books", "mixed"}

DEFAULT_CSV_PATH = str(_PROJECT_ROOT / ".kilo" / "plans" / "site-catalog.csv")

LOG_DIR = _PROJECT_ROOT / "scripts"

# Cloudflare detection signatures in headers
CF_HEADER_KEYS = {"cf-ray", "cf-cache-status", "cf-chl-bypass", "cf-chl-out"}
CF_SERVER_VALUE = "cloudflare"

# Cloudflare detection signatures in HTML body
CF_HTML_SIGNATURES = [
    "/cdn-cgi/", "jschl-answer", "cf_chl_opt", "cf-chl-bypass",
    "challenge-platform", "just a moment", "checking your browser",
    "cf-browser-verify", "cf_clearance",
]

# HTTP status codes that strongly suggest Cloudflare or WAF
BLOCKED_STATUS_CODES = {403, 406, 503}

# Minimum meaningful text content length (chars after stripping HTML tags)
MIN_TEXT_CONTENT_LENGTH = 100

# Threshold for "medium" complexity (more than this = probably parseable)
MEDIUM_TEXT_THRESHOLD = 500

# Default probe timeout per site
DEFAULT_TIMEOUT = 15

# Default delay between sites (seconds)
DEFAULT_DELAY = 2.0

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging() -> logging.Logger:
    """Configure file + console logging with timestamp-based filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"probe_results_{timestamp}.log"

    logger = logging.getLogger("probe_sites")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    # File handler (detailed)
    fh = logging.FileHandler(str(log_path), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S"
    ))
    logger.addHandler(fh)

    # Console handler (info and above)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(levelname)-8s | %(message)s"))
    logger.addHandler(ch)

    logger.info("Log file: %s", log_path)
    return logger


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def _strip_html(text: str) -> str:
    """Remove HTML tags and return plain text."""
    return re.sub(r"<[^>]+>", "", text).strip()


def _detect_cloudflare_headers(headers: dict) -> bool:
    """Check HTTP headers for Cloudflare signatures."""
    for key, value in headers.items():
        key_lower = key.lower()
        val_lower = str(value).lower()
        if key_lower in CF_HEADER_KEYS:
            return True
        if key_lower == "server" and CF_SERVER_VALUE in val_lower:
            return True
    return False


def _detect_cloudflare_html(html: str) -> bool:
    """Check HTML body for Cloudflare challenge signatures."""
    html_lower = html.lower()
    return any(sig.lower() in html_lower for sig in CF_HTML_SIGNATURES)


def _detect_js_required(html: str) -> bool:
    """Check if the site requires JavaScript to render content."""
    html_lower = html.lower()
    text = _strip_html(html)

    # Empty or skeleton page
    if len(text) < MIN_TEXT_CONTENT_LENGTH:
        return True

    # Explicit noscript warning
    if "<noscript>" in html_lower:
        noscript_content = re.search(r"<noscript[^>]*>(.*?)</noscript>", html_lower, re.DOTALL)
        if noscript_content:
            noscript_text = noscript_content.group(1).strip()
            # Only flag if noscript says JS is needed (not just a benign message)
            js_keywords = ["javascript", "enable", "required", "please", "browser", "support"]
            if any(kw in noscript_text for kw in js_keywords):
                return True

    # Meta refresh to a challenge page
    if re.search(r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+url=', html_lower):
        return True

    return False


def _detect_login_required(html: str, final_url: str) -> bool:
    """Check if the site redirects to login or has a login form."""
    html_lower = html.lower()
    html_prefix = html_lower[:800]  # Only check beginning of page

    # Redirect to login page
    if "/login" in final_url.lower() or "/signin" in final_url.lower():
        return True

    # Login form indicators in the first part of the page
    login_form_indicators = [
        'name="password"',
        'type="password"',
        'id="login"',
        'class="login',
        'action="/login',
        'action="/signin',
        '"wp-login.php"',
    ]
    for indicator in login_form_indicators:
        if indicator in html_prefix:
            return True

    return False


def _classify_complexity(
    status: int,
    text_content: str,
    has_cf: bool,
    requires_js: bool,
    has_html: bool,
) -> tuple:
    """
    Classify the site's implementation complexity.

    Returns (complexity: str, notes: str).
    """
    if has_cf or requires_js:
        return "high", ""

    if status == 200 and len(text_content) >= MIN_TEXT_CONTENT_LENGTH:
        if len(text_content) >= MEDIUM_TEXT_THRESHOLD:
            return "low", ""
        else:
            return "medium", "Page has content but is relatively sparse"

    if status in BLOCKED_STATUS_CODES:
        return "blocked", f"HTTP {status} - access blocked by WAF or Cloudflare"

    if status == 200 and not has_html:
        return "TBD", "Returned 200 but no parseable HTML body"

    if status == 0:
        return "TBD", "DOWN: no response received"

    return "TBD", f"needs manual review (status={status})"


# ---------------------------------------------------------------------------
# Core probing logic
# ---------------------------------------------------------------------------

async def probe_site(
    client: HttpClient,
    row: dict,
    logger: logging.Logger,
) -> dict:
    """
    Probe a single site and return updated row dictionary.

    Protocol:
    1. HTTP HEAD to check connectivity and headers
    2. HTTP GET (use_scraper=False) to analyze body content
    3. If blocked, retry with use_scraper=True
    4. Try a test search if search_url_template is defined
    5. Update row fields with findings
    """
    results = {k: row.get(k, "") for k in CSV_COLUMNS}
    url = (row.get("url") or "").strip()

    if not url:
        results["notes"] = "SKIP: no URL"
        return results

    site_id = results.get("id", "UNKNOWN")
    logger.info("Probing %s (%s)", site_id, url)

    # Seed with "no" defaults for technical fields (overwritten on detection)
    for field in ("has_cloudflare", "requires_js", "requires_login", "has_captcha"):
        if not results.get(field, "").strip():
            results[field] = "no"

    headers: dict = {}
    body_html: str = ""
    final_url: str = url
    status: int = 0
    timed_out: bool = False

    # ── Phase 1: HEAD request ──────────────────────────────────────────
    try:
        head_resp = await client.head(url, timeout=DEFAULT_TIMEOUT, follow_redirects=True)
        headers = head_resp.headers
        final_url = head_resp.url
        status = head_resp.status_code
        logger.debug("  HEAD → %s %s (final: %s)", status, url, final_url)
    except Exception as exc:
        logger.debug("  HEAD failed: %s", exc)

    # ── Phase 2: GET request (clean, no cloudscraper) ──────────────────
    try:
        resp = await client.get(url, use_scraper=False, follow_redirects=True)
        body_html = resp.text if hasattr(resp, "text") else ""
        headers = resp.headers  # Prefer GET headers (more complete)
        final_url = resp.url
        status = resp.status_code
        logger.debug("  GET  → %s (%d chars HTML)", status, len(body_html))
    except httpx.HTTPStatusError as exc:
        # Non-2xx response — still extract headers and body for analysis
        status = exc.response.status_code
        headers = dict(exc.response.headers)
        body_html = exc.response.text if hasattr(exc.response, "text") else ""
        final_url = str(exc.response.url) if hasattr(exc.response, "url") else url
        logger.debug("  GET  → %s (HTTPStatusError)", status)
    except Exception as exc:
        error_str = str(exc)
        if "timeout" in error_str.lower():
            timed_out = True
            logger.debug("  GET timeout: %s", exc)
        else:
            logger.debug("  GET error: %s", exc)

    # ── Phase 3: Detect Cloudflare via headers ─────────────────────────
    cf_headers = _detect_cloudflare_headers(headers)
    if cf_headers:
        results["has_cloudflare"] = "yes"
        logger.debug("  Cloudflare detected via headers")

    # ── Phase 4: Detect features from HTML body ────────────────────────
    text_content = _strip_html(body_html)
    cf_html = _detect_cloudflare_html(body_html)
    js_required = _detect_js_required(body_html)
    login_required = _detect_login_required(body_html, final_url)

    if cf_html:
        results["has_cloudflare"] = "yes"
        logger.debug("  Cloudflare detected via HTML")

    if js_required:
        results["requires_js"] = "yes"
        logger.debug("  JavaScript required (skeleton page or noscript challenge)")

    if login_required:
        results["requires_login"] = "yes"
        logger.debug("  Login required detected")

    # If blocked by HTTP status without Cloudflare header, try cloudscraper
    if status in BLOCKED_STATUS_CODES and not cf_headers and not cf_html:
        logger.debug("  Blocked (%s), retrying with cloudscraper...", status)
        try:
            scraper_resp = await client.get(
                url, use_scraper=True, follow_redirects=True
            )
            scraper_html = scraper_resp.text if hasattr(scraper_resp, "text") else ""
            scraper_text = _strip_html(scraper_html)
            logger.debug("  cloudscraper → %s (%d chars)", scraper_resp.status_code, len(scraper_html))

            if scraper_resp.status_code == 200 and len(scraper_text) >= MIN_TEXT_CONTENT_LENGTH:
                results["has_cloudflare"] = "yes"
                status = 200
                body_html = scraper_html
                text_content = scraper_text
                logger.debug("  Cloudflare bypassed via cloudscraper")
            else:
                results["has_cloudflare"] = "yes"
        except Exception as exc:
            results["has_cloudflare"] = "yes"
            logger.debug("  cloudscraper also failed: %s", exc)

    # ── Phase 5: Attempt test search ───────────────────────────────────
    search_template = (row.get("search_url_template") or "").strip()
    if search_template and status == 200:
        search_url = search_template.replace("{query}", "test")
        try:
            search_resp = await client.get(
                search_url, use_scraper=False, follow_redirects=True
            )
            search_text = _strip_html(search_resp.text if hasattr(search_resp, "text") else "")
            logger.debug("  Search test → %s (%d chars)", search_resp.status_code, len(search_text))
        except httpx.HTTPStatusError:
            logger.debug("  Search test → blocked (HTTPStatusError)")
        except Exception as exc:
            logger.debug("  Search test → failed: %s", exc)

    # ── Phase 6: Classify complexity ───────────────────────────────────
    has_cf = results.get("has_cloudflare", "no") == "yes"
    requires_js = results.get("requires_js", "no") == "yes"
    has_html = len(body_html.strip()) > 0

    complexity, auto_notes = _classify_complexity(
        status, text_content, has_cf, requires_js, has_html
    )
    results["complexity"] = complexity

    if auto_notes and not results.get("notes", "").strip():
        results["notes"] = auto_notes

    if timed_out and not results.get("notes", "").strip():
        results["notes"] = "DOWN: connection timeout"

    # Update last_verified timestamp
    results["last_verified"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Log summary line
    cf_tag = "CF" if results.get("has_cloudflare") == "yes" else "OK"
    js_tag = "JS" if results.get("requires_js") == "yes" else "--"
    login_tag = "LOGIN" if results.get("requires_login") == "yes" else "--"
    logger.info(
        "  → %-8s | cf=%-3s js=%-4s login=%-5s | complexity=%-7s | %s",
        site_id, cf_tag, js_tag, login_tag, complexity,
        results.get("notes", "") or "no issues",
    )

    return results


# ---------------------------------------------------------------------------
# CSV I/O
# ---------------------------------------------------------------------------

def read_csv(path: str) -> list[dict]:
    """Read CSV and return list of row dicts with original fieldnames."""
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return rows


def write_csv(path: str, rows: list[dict], fieldnames: list[str]) -> None:
    """Write rows to CSV preserving column order."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def backup_csv(path: str) -> str:
    """Create a timestamped backup of the CSV file. Returns backup path."""
    bak_path = path + ".bak"
    shutil.copy2(path, bak_path)
    return bak_path


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def filter_rows(
    rows: list[dict],
    *,
    force: bool = False,
    start_from: str | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    Filter rows to probe and return (to_probe, rest).

    Selection criteria:
    - content_type in {"books", "mixed"}
    - score >= 3.0
    - complexity is TBD or empty, OR technical fields are empty, OR --force
    - If --start-from, skip rows before that ID
    """
    to_probe: list[dict] = []
    rest: list[dict] = []
    started = start_from is None

    for row in rows:
        ct = (row.get("content_type") or "").strip().lower()
        score_str = (row.get("score") or "0").strip()
        complexity = (row.get("complexity") or "").strip()

        try:
            score = float(score_str)
        except (ValueError, TypeError):
            score = 0.0

        # Skip non-book/mixed types
        if ct not in TARGET_CONTENT_TYPES:
            rest.append(row)
            continue

        if score < 3.0:
            rest.append(row)
            continue

        # Check if the site needs probing
        needs_probe = False

        if not complexity or complexity.upper() == "TBD":
            needs_probe = True
        else:
            # Check for empty technical fields
            for field in ("has_cloudflare", "requires_js", "requires_login"):
                if not row.get(field, "").strip():
                    needs_probe = True
                    break

        if force:
            needs_probe = True

        site_id = row.get("id", "").strip()
        if start_from and not started:
            if site_id == start_from:
                started = True
            if not started:
                rest.append(row)
                continue

        if needs_probe:
            to_probe.append(row)
        else:
            rest.append(row)

    return to_probe, rest


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main_async(args: argparse.Namespace) -> None:
    logger = setup_logging()

    csv_path = args.csv_path
    if not os.path.exists(csv_path):
        logger.error("CSV not found: %s", csv_path)
        sys.exit(1)

    # ── Read and filter CSV ────────────────────────────────────────────
    logger.info("Reading CSV: %s", csv_path)
    all_rows = read_csv(csv_path)
    logger.info("Total rows in CSV: %d", len(all_rows))

    to_probe, rest = filter_rows(
        all_rows,
        force=args.force,
        start_from=args.start_from,
    )
    logger.info(
        "Sites to probe: %d (skipped: %d, force=%s, start_from=%s)",
        len(to_probe), len(rest), args.force, args.start_from or "beginning",
    )

    if args.limit is not None and args.limit > 0:
        to_probe = to_probe[:args.limit]
        logger.info("Limited to %d sites", len(to_probe))

    if not to_probe:
        logger.info("No sites to probe. Exiting.")
        return

    # ── Dry-run mode ───────────────────────────────────────────────────
    if args.dry_run:
        logger.info("DRY RUN — would probe %d sites:", len(to_probe))
        for row in to_probe:
            site_id = row.get("id", "?")
            name = row.get("name", "?")
            url = row.get("url", "?")
            complexity = row.get("complexity", "TBD")
            score = row.get("score", "?")
            logger.info("  %-10s | %-30s | %-6s | cpx=%-8s | %s", site_id, name[:30], score, complexity, url)
        return

    # ── Probe loop ─────────────────────────────────────────────────────
    logger.info(
        "Creating HttpClient (timeout=%ds, max_retries=2, delay=%.1fs)",
        DEFAULT_TIMEOUT, args.delay,
    )
    client = HttpClient(timeout=DEFAULT_TIMEOUT, max_retries=2)

    updated_rows: list[dict] = []
    stats = {
        "probed": 0,
        "ok": 0,
        "down": 0,
        "cloudflare": 0,
        "js_required": 0,
        "login_required": 0,
        "low": 0,
        "medium": 0,
        "high": 0,
        "blocked": 0,
        "tbd": 0,
    }

    try:
        for i, row in enumerate(to_probe):
            if i > 0:
                await asyncio.sleep(args.delay)

            updated = await probe_site(client, row, logger)
            updated_rows.append(updated)

            # Update stats
            stats["probed"] += 1
            notes_val = (updated.get("notes") or "").lower()
            if "down" in notes_val:
                stats["down"] += 1
            elif updated.get("complexity", "") == "blocked":
                stats["blocked"] += 1
            else:
                stats["ok"] += 1

            if updated.get("has_cloudflare") == "yes":
                stats["cloudflare"] += 1
            if updated.get("requires_js") == "yes":
                stats["js_required"] += 1
            if updated.get("requires_login") == "yes":
                stats["login_required"] += 1

            cpx = updated.get("complexity", "tbd")
            if cpx in stats:
                stats[cpx] += 1
    finally:
        await client.close()

    # ── Merge updated rows back into full dataset ──────────────────────
    # Build lookup by id for the probed rows
    probed_by_id = {r["id"]: r for r in updated_rows}

    merged_rows: list[dict] = []
    for row in all_rows:
        rid = row.get("id", "")
        if rid in probed_by_id:
            merged_rows.append(probed_by_id[rid])
        else:
            merged_rows.append(row)

    # ── Backup and write CSV ───────────────────────────────────────────
    bak_path = backup_csv(csv_path)
    logger.info("Backup created: %s", bak_path)
    write_csv(csv_path, merged_rows, fieldnames=CSV_COLUMNS)
    logger.info("CSV updated: %s (%d rows)", csv_path, len(merged_rows))

    # ── Summary ────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print(" PROBE SUMMARY")
    print("=" * 60)
    print(f"  Sites probed:      {stats['probed']:>5d}")
    print(f"  Sites OK:          {stats['ok']:>5d}")
    print(f"  Sites DOWN:        {stats['down']:>5d}")
    print(f"  With Cloudflare:   {stats['cloudflare']:>5d}")
    print(f"  Requires JS:       {stats['js_required']:>5d}")
    print(f"  Requires login:    {stats['login_required']:>5d}")
    print("-" * 60)
    print("  Complexity breakdown:")
    print(f"    low:             {stats['low']:>5d}")
    print(f"    medium:          {stats['medium']:>5d}")
    print(f"    high:            {stats['high']:>5d}")
    print(f"    blocked:         {stats['blocked']:>5d}")
    print(f"    TBD:             {stats['tbd']:>5d}")
    print("=" * 60)
    print(f"  Log: {LOG_DIR / sorted(os.listdir(LOG_DIR))[-1] if os.listdir(LOG_DIR) else 'N/A'}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch site validation for WebTranslatorr. "
                    "Probes book/mixed sites to detect Cloudflare, JS requirements, "
                    "login gates, and classify implementation complexity.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/probe_sites.py --dry-run
  python scripts/probe_sites.py --limit 5
  python scripts/probe_sites.py --start-from SITE-0610 --limit 10
  python scripts/probe_sites.py --force --limit 3
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without modifying the CSV",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most N sites",
    )
    parser.add_argument(
        "--start-from",
        type=str,
        default=None,
        help="Start probing from this site ID (e.g. SITE-0610)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"Seconds delay between sites (default: {DEFAULT_DELAY})",
    )
    parser.add_argument(
        "--csv-path",
        type=str,
        default=DEFAULT_CSV_PATH,
        help=f"Path to site-catalog.csv (default: {DEFAULT_CSV_PATH})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprobe sites even if complexity is already assigned",
    )

    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
