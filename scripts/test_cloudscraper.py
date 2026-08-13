#!/usr/bin/env python3
"""
test_cloudscraper.py — Evalúa si cloudscraper puede romper la protección
Cloudflare de 3 sitios de manga bloqueados.

Prueba 4 intentos progresivos por dominio:
  1. HTTP simple (httpx sin cloudscraper)
  2. cloudscraper con configuración por defecto
  3. cloudscraper con headers adicionales (Referer, Origin)
  4. cloudscraper con cookies de sesión simuladas

Para cada intento, analiza el HTML para determinar si se superó el challenge
o se recibió una página de bloqueo.

Salidas:
  - Informe detallado en consola (progreso + resumen)
  - JSON con resultados completos en scripts/cloudscraper_report_{timestamp}.json

Uso:
    python scripts/test_cloudscraper.py
"""

import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# Allow importing from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.scraping.http_client import HttpClient, ScraperResponse  # noqa: E402

# ---------------------------------------------------------------------------
# Configuración de targets
# ---------------------------------------------------------------------------

TARGETS: list[dict[str, str]] = [
    {"name": "TuMangaOnline", "url": "https://visortmo.com"},
    {"name": "LectorManga", "url": "https://lectortmo.com"},
    {"name": "LeerManga", "url": "https://leermanga.net"},
]

# ---------------------------------------------------------------------------
# Firmas de detección de challenge Cloudflare
# ---------------------------------------------------------------------------

CHALLENGE_SIGNATURES: list[str] = [
    "challenge-platform",
    "cf_chl_opt",
    "cf-browser-verification",
    "checking your browser",
    "_cf_chl_",
    "jschl-answer",
    "just a moment...",
    "window._cf_chl_opt",
    "cf_captcha",
    "cf-wrapper",
    "attention required",
    "security check",
]

# ---------------------------------------------------------------------------
# Firmas de contenido real (manga)
# ---------------------------------------------------------------------------

MANGA_SIGNATURES: list[str] = [
    "manga",
    "capítulo",
    "capitulo",
    "leer",
    "lector",
    "página",
    "pagina",
    "género",
    "genero",
    "scanlation",
    "tomos",
    "biblioteca",
    "catálogo",
    "catalogo",
]


# ====================================================================
# Helpers de análisis
# ====================================================================


def detect_challenge(html: str) -> bool:
    """Detecta si el HTML contiene una página de challenge o bloqueo Cloudflare."""
    if not html:
        return True  # Empty body treated as blocked
    html_lower = html.lower()
    for sig in CHALLENGE_SIGNATURES:
        if sig in html_lower:
            return True
    return False


def has_real_content(html: str) -> bool:
    """Heurística para determinar si el HTML parece contenido real (no bloqueo)."""
    if not html:
        return False
    html_lower = html.lower()

    # Count manga-related keywords
    keyword_score = sum(1 for sig in MANGA_SIGNATURES if sig in html_lower)

    # Structural checks
    has_doctype = "doctype" in html_lower and "<html" in html_lower
    has_body = "<body" in html_lower
    has_head = "<head" in html_lower or "head>" in html_lower
    size_score = 1 if len(html) > 5000 else 0

    total = keyword_score + (1 if has_doctype else 0) + (1 if has_body and has_head else 0) + size_score
    return total >= 3


def analyze_response(
    resp: ScraperResponse | None,
    error: str | None,
    attempt_name: str,
    elapsed: float,
    snippet_len: int = 200,
) -> dict[str, Any]:
    """Analiza una respuesta HTTP y devuelve un dict estructurado con el resultado."""
    result: dict[str, Any] = {
        "attempt": attempt_name,
        "elapsed_ms": round(elapsed * 1000, 1),
    }

    if error:
        result["status"] = "ERROR"
        result["error"] = error[:200]
        result["is_challenge"] = None
        result["has_content"] = False
        result["html_length"] = 0
        return result

    if resp is None:
        result["status"] = "ERROR"
        result["error"] = "No response received"
        result["is_challenge"] = None
        result["has_content"] = False
        result["html_length"] = 0
        return result

    html = resp.text or ""
    is_challenge = detect_challenge(html)
    has_content = has_real_content(html)

    result["http_status"] = resp.status_code
    result["final_url"] = resp.url
    result["html_length"] = len(html)
    result["content_type"] = resp.headers.get("content-type", "unknown")
    result["is_challenge"] = is_challenge
    result["has_content"] = has_content

    # Status determination
    if resp.status_code >= 400:
        result["status"] = f"HTTP_{resp.status_code}" if not is_challenge else "BLOCKED"
    elif is_challenge:
        result["status"] = "BLOCKED"
    elif has_content:
        result["status"] = "SUCCESS"
    else:
        result["status"] = "UNKNOWN"

    # HTML snippet (escaped for JSON safety)
    result["html_snippet"] = html[:snippet_len]

    # Notable headers for debugging
    notable = {"cf-ray", "cf-cache-status", "server", "set-cookie", "cf-chl-bypass", "x-frame-options"}
    result["notable_headers"] = {
        k: v for k, v in resp.headers.items() if k.lower() in notable
    }

    return result


# ====================================================================
# Intentos individuales
# ====================================================================


async def attempt_http_simple(
    client: HttpClient, url: str
) -> tuple[ScraperResponse | None, str | None]:
    """Intento 1: HTTP simple sin cloudscraper."""
    try:
        resp = await client.get(url, use_scraper=False)
        return resp, None
    except Exception as exc:
        return None, str(exc)


async def attempt_cloudscraper(
    client: HttpClient, url: str
) -> tuple[ScraperResponse | None, str | None]:
    """Intento 2: cloudscraper con configuración por defecto."""
    try:
        resp = await client.get(url, use_scraper=True)
        return resp, None
    except Exception as exc:
        return None, str(exc)


async def attempt_cloudscraper_headers(
    client: HttpClient, url: str, target_name: str
) -> tuple[ScraperResponse | None, str | None]:
    """Intento 3: cloudscraper con headers adicionales (Referer, Origin)."""
    referer_map = {
        "TuMangaOnline": "https://visortmo.com/",
        "LectorManga": "https://lectortmo.com/",
        "LeerManga": "https://leermanga.net/",
    }
    referer = referer_map.get(target_name, url.rstrip("/") + "/")

    extra_headers = {
        "Referer": referer,
        "Origin": referer.rstrip("/"),
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    try:
        resp = await client.get(url, use_scraper=True, headers=extra_headers)
        return resp, None
    except Exception as exc:
        return None, str(exc)


async def attempt_cloudscraper_cookies(
    client: HttpClient, url: str
) -> tuple[ScraperResponse | None, str | None]:
    """Intento 4: cloudscraper con cookies de sesión simuladas."""
    domain = urlparse(url).netloc

    # Simulated browser cookies (GA, session, language)
    simulated_cookies = {
        "language": "es",
        "_ga": "GA1.2.123456789.1700000000",
        "_gid": "GA1.2.987654321.1700000000",
        "consent": "accepted",
    }

    try:
        for name, value in simulated_cookies.items():
            client._scraper.cookies.set(name, value, domain=domain)
        resp = await client.get(url, use_scraper=True)
        return resp, None
    except Exception as exc:
        return None, str(exc)


# ====================================================================
# Core: test de un target
# ====================================================================


async def test_target(
    client: HttpClient, target: dict[str, str]
) -> dict[str, Any]:
    """Ejecuta los 4 intentos de bypass para un dominio y devuelve resultados."""
    name: str = target["name"]
    url: str = target["url"]
    results: dict[str, Any] = {"name": name, "url": url, "attempts": []}

    _print_header(name, url)

    # --- Attempt 1: HTTP simple ---
    _print_step(1, 4, "HTTP simple (sin cloudscraper)")
    t0 = time.monotonic()
    resp, err = await attempt_http_simple(client, url)
    elapsed = time.monotonic() - t0
    entry = analyze_response(resp, err, "http_simple", elapsed)
    results["attempts"].append(entry)
    _print_attempt_result(entry, 1)
    await asyncio.sleep(0.5)

    # --- Attempt 2: cloudscraper default ---
    _print_step(2, 4, "cloudscraper (por defecto)")
    t0 = time.monotonic()
    resp, err = await attempt_cloudscraper(client, url)
    elapsed = time.monotonic() - t0
    entry = analyze_response(resp, err, "cloudscraper_default", elapsed)
    results["attempts"].append(entry)
    _print_attempt_result(entry, 2)
    await asyncio.sleep(0.5)

    # --- Attempt 3: cloudscraper + headers ---
    _print_step(3, 4, "cloudscraper + headers adicionales")
    t0 = time.monotonic()
    resp, err = await attempt_cloudscraper_headers(client, url, name)
    elapsed = time.monotonic() - t0
    entry = analyze_response(resp, err, "cloudscraper_headers", elapsed)
    results["attempts"].append(entry)
    _print_attempt_result(entry, 3)
    await asyncio.sleep(0.5)

    # --- Attempt 4: cloudscraper + cookies ---
    _print_step(4, 4, "cloudscraper + cookies simuladas")
    t0 = time.monotonic()
    resp, err = await attempt_cloudscraper_cookies(client, url)
    elapsed = time.monotonic() - t0
    entry = analyze_response(resp, err, "cloudscraper_cookies", elapsed)
    results["attempts"].append(entry)
    _print_attempt_result(entry, 4)

    # --- Veredicto ---
    verdict = _compute_verdict(results["attempts"])
    results["bypass_status"] = verdict
    _print_verdict(name, verdict)

    return results


# ====================================================================
# Veredicto y formateo de salida
# ====================================================================


def _compute_verdict(attempts: list[dict[str, Any]]) -> str:
    """Calcula el estado global de bypass (BYPASS_OK | WORKAROUND | FAILED)."""
    scraper_attempts = [a for a in attempts if a["attempt"] != "http_simple"]

    for a in scraper_attempts:
        if a.get("status") == "SUCCESS":
            return "BYPASS_OK"

    for a in scraper_attempts:
        if a.get("status") == "UNKNOWN" and not a.get("is_challenge", True):
            return "BYPASS_WORKAROUND"

    for a in scraper_attempts:
        s = a.get("status", "")
        if s == "BLOCKED" or (s.startswith("HTTP_") and s not in ("HTTP_502", "HTTP_503")):
            return "BYPASS_FAILED"

    # All errors (connection, timeout) → indeterminate, treat as failed
    return "BYPASS_FAILED"


def _print_header(name: str, url: str) -> None:
    print(f"\n{'─' * 70}")
    print(f"  🔍 {name}")
    print(f"     {url}")
    print(f"{'─' * 70}")


def _print_step(n: int, total: int, label: str) -> None:
    print(f"  [{n}/{total}] {label}...")


def _print_attempt_result(entry: dict[str, Any], num: int) -> None:
    status = entry.get("status", "?")
    icons = {"SUCCESS": "✅", "BLOCKED": "🚫", "UNKNOWN": "❓"}
    icon = icons.get(status, "❌" if "ERROR" in status or "HTTP_" in status else "❓")

    elapsed = entry.get("elapsed_ms", 0)
    html_len = entry.get("html_length", 0)
    http_status = entry.get("http_status", "N/A")
    challenge = entry.get("is_challenge", "?")
    content = entry.get("has_content", False)

    parts = [
        f"     {icon} [{num}] {entry['attempt']}:",
        f"status={status}",
        f"HTTP={http_status}",
        f"html={html_len}B",
        f"{elapsed:.0f}ms",
        f"challenge={challenge}",
        f"content={content}",
    ]

    error = entry.get("error")
    if error:
        parts.append(f"error={error[:80]}")

    print(" ".join(parts))


def _print_verdict(name: str, verdict: str) -> None:
    icons = {"BYPASS_OK": "✅", "BYPASS_WORKAROUND": "⚠️", "BYPASS_FAILED": "❌"}
    icon = icons.get(verdict, "❓")
    print(f"\n  >>> {icon} VEREDICTO [{name}]: {verdict}")


# ====================================================================
# Entry point
# ====================================================================


def _build_summary(all_results: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "bypass_ok": sum(1 for r in all_results if r["bypass_status"] == "BYPASS_OK"),
        "bypass_workaround": sum(1 for r in all_results if r["bypass_status"] == "BYPASS_WORKAROUND"),
        "bypass_failed": sum(1 for r in all_results if r["bypass_status"] == "BYPASS_FAILED"),
    }


async def main() -> None:
    """Punto de entrada principal."""
    print("=" * 70)
    print("  cloudscraper Bypass Test — Sitios de Manga")
    print(f"  Inicio: {datetime.now(timezone.utc).isoformat()}")
    print("  Versión cloudscraper: ", end="")
    try:
        import cloudscraper
        print(getattr(cloudscraper, "__version__", "desconocida"))
    except Exception:
        print("no disponible")
    print("=" * 70)

    client = HttpClient(
        rate_limit_per_second=1.0,
        max_retries=1,
        timeout=15,
    )

    all_results: list[dict[str, Any]] = []
    try:
        for target in TARGETS:
            result = await test_target(client, target)
            all_results.append(result)
    finally:
        await client.close()

    # --- Resumen final ---
    print(f"\n{'=' * 70}")
    print("  RESUMEN FINAL")
    print(f"{'=' * 70}")

    for r in all_results:
        name = r["name"]
        verdict = r["bypass_status"]
        chain = " → ".join(f"{a['attempt']}={a['status']}" for a in r["attempts"])
        icons = {"BYPASS_OK": "✅", "BYPASS_WORKAROUND": "⚠️", "BYPASS_FAILED": "❌"}
        icon = icons.get(verdict, "❓")
        print(f"  {icon} {name}: {verdict}")
        print(f"     {chain}")

    # --- Guardar informe JSON ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = Path(__file__).parent / f"cloudscraper_report_{timestamp}.json"
    summary = _build_summary(all_results)
    report = {
        "test_timestamp": datetime.now(timezone.utc).isoformat(),
        "test_targets": len(TARGETS),
        "results": all_results,
        "summary": summary,
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n  📄 Informe guardado: {report_path}")
    print(f"  OK: {summary['bypass_ok']} | "
          f"Workaround: {summary['bypass_workaround']} | "
          f"Failed: {summary['bypass_failed']}")

    # --- Recomendación ---
    print(f"\n{'=' * 70}")
    if summary["bypass_failed"] == len(TARGETS):
        print("  ⚠️  Cloudscraper no pudo romper Cloudflare en ningún sitio.")
        print("  Considerar: proxy rotatorio, login previo, o actualizar cloudscraper.")
    elif summary["bypass_ok"] > 0:
        print("  ✅ Cloudscraper funciona en al menos un sitio.")
        print("  Revisar el JSON para los parámetros exactos del intento exitoso.")
    else:
        print("  ⚠️  Resultados mixtos — revisar el informe JSON para detalles.")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    asyncio.run(main())
