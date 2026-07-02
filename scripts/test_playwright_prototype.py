#!/usr/bin/env python3
"""
Prototipo de evaluacion Playwright para WebTranslatorr.

Evalua si Playwright puede manejar sitios SPA y anti-bot avanzado
que HTTP simple + cloudscraper no pueden manejar.

Uso:
    python scripts/test_playwright_prototype.py

Salida:
    - Resultados en stdout (JSON)
    - Archivo JSON con timestamp en scripts/

NO es codigo de produccion — es un prototipo desechable para evaluar viabilidad.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import tracemalloc
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus, urljoin

# ── Dependencia opcional: Playwright ─────────────────────────────────────────
try:
    from playwright.async_api import async_playwright  # noqa: E402
    PLAYWRIGHT_AVAILABLE = True
except ImportError:  # pragma: no cover
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None  # type: ignore[assignment]

# ── Dependencia opcional: httpx (comparacion HTTP simple) ────────────────────
try:
    import httpx  # noqa: E402
    HTTPX_AVAILABLE = True
except ImportError:  # pragma: no cover
    HTTPX_AVAILABLE = False
    httpx = None  # type: ignore[assignment]

# ── Dependencia opcional: psutil (medicion de memoria del proceso) ───────────
try:
    import psutil  # noqa: E402
    PSUTIL_AVAILABLE = True
except ImportError:  # pragma: no cover
    PSUTIL_AVAILABLE = False
    psutil = None  # type: ignore[assignment]

# ── Constantes ──────────────────────────────────────────────────────────────

TARGETS: list[dict[str, str]] = [
    {
        "name": "InManga",
        "url": "https://inmanga.com",
        "search_path": "/search?q=",
        "query": "one piece",
        "reason": "SPA pura (Angular/Vue), HTML inicial vacio",
    },
    {
        "name": "PDF Drive",
        "url": "https://www.pdfdrive.com",
        "search_path": "/search?q=",
        "query": "python programming",
        "reason": "Anti-bot avanzado, fingerprinting",
    },
    {
        "name": "SkyMangas",
        "url": "https://skymangas.com",
        "search_path": "/search?q=",
        "query": "one piece",
        "reason": "SPA con SSR parcial",
    },
]

PLAYWRIGHT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

HTTP_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

BROWSER_TIMEOUT_MS = 15_000
HTTP_TIMEOUT_SECONDS = 15.0
REPORT_DIR = os.path.dirname(os.path.abspath(__file__))


# ── Helpers ──────────────────────────────────────────────────────────────────

def _snapshot_current_memory_mb() -> float | None:
    """Obtiene el uso de memoria RAM actual del proceso en MB.

    Usa psutil (RSS en MB) si esta disponible; si no, estima via tracemalloc.
    """
    if PSUTIL_AVAILABLE and psutil is not None:
        proc = psutil.Process(os.getpid())
        return round(proc.memory_info().rss / (1024 * 1024), 2)

    # Fallback: tracemalloc (solo memoria Python, no incluye C/navegador)
    current, _peak = tracemalloc.get_traced_memory()
    return round(current / (1024 * 1024), 2)


def _build_search_url(target: dict[str, str]) -> str:
    """Construye la URL completa de busqueda para un target."""
    base = target["url"].rstrip("/")
    path = target["search_path"]
    query = quote_plus(target["query"])
    return f"{base}{path}{query}"


def _content_indicators(html: str) -> dict[str, Any]:
    """Analiza el HTML extraido y devuelve indicadores de contenido real.

    Busca senales tipicas de paginas SPA renderizadas: enlaces, imagenes,
    articulos, y contenedores comunes de resultados de busqueda.
    """
    html_lower = html.lower()
    return {
        "html_length": len(html),
        "has_links": html_lower.count('<a ') > 10,
        "has_images": html_lower.count('<img ') > 3,
        "has_articles": "article" in html_lower or "post" in html_lower,
        "has_search_results": any(
            tag in html_lower
            for tag in (
                "search-result", "search-result-item",
                "result-item", "book-item", "list-item",
                "card", "entry", "product",
            )
        ),
        "likely_spa_empty": len(html) < 800 and "loading" in html_lower,
    }


# ── Test: Playwright ─────────────────────────────────────────────────────────

async def test_site_with_playwright(
    target: dict[str, str],
) -> dict[str, Any]:
    """Prueba un sitio con Playwright, mide tiempos y extrae resultados."""
    result: dict[str, Any] = {
        "name": target["name"],
        "method": "playwright",
        "url": _build_search_url(target),
        "success": False,
        "error": None,
        "metrics": {},
        "content": {},
    }

    if not PLAYWRIGHT_AVAILABLE:
        result["error"] = "Playwright no instalado"
        return result

    tracemalloc.start()
    mem_before = _snapshot_current_memory_mb()
    overall_start = time.perf_counter()

    try:
        async with async_playwright() as p:  # type: ignore[union-attr]
            launch_start = time.perf_counter()
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
            context = await browser.new_context(
                user_agent=PLAYWRIGHT_USER_AGENT,
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()
            result["metrics"]["browser_launch_time_s"] = round(
                time.perf_counter() - launch_start, 2
            )

            # ── Primera carga (navegacion a busqueda) ─────────────────
            nav_start = time.perf_counter()
            search_url = _build_search_url(target)
            response = await page.goto(
                search_url,
                timeout=BROWSER_TIMEOUT_MS,
                wait_until="networkidle",
            )
            result["metrics"]["first_navigation_time_s"] = round(
                time.perf_counter() - nav_start, 2
            )
            result["metrics"]["http_status"] = (
                response.status if response else None
            )

            # Esperar renderizado de contenido dinamico
            try:
                await page.wait_for_selector(
                    "a[href], img, article, .post, .book, .result, .card",
                    timeout=8_000,
                )
            except Exception:
                result["metrics"]["selector_wait_timeout"] = True

            # Extraer HTML renderizado
            html = await page.content()
            result["content"] = _content_indicators(html)

            # Considerar exitoso si:
            # - HTTP 200
            # - HTML > 500 chars
            # - Hay enlaces o imagenes (senial de pagina renderizada)
            result["success"] = bool(
                response
                and response.status == 200
                and len(html) > 500
                and (result["content"]["has_links"] or result["content"]["has_images"])
            )

            # ── Segunda carga (request subsecuente, mismo browser) ────
            if result["success"]:
                nav2_start = time.perf_counter()
                # Navegar a la homepage como segundo request
                await page.goto(
                    target["url"],
                    timeout=BROWSER_TIMEOUT_MS,
                    wait_until="domcontentloaded",
                )
                result["metrics"]["second_navigation_time_s"] = round(
                    time.perf_counter() - nav2_start, 2
                )

            await context.close()
            await browser.close()

    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    result["metrics"]["total_time_s"] = round(
        time.perf_counter() - overall_start, 2
    )
    mem_after = _snapshot_current_memory_mb()
    if mem_before is not None and mem_after is not None:
        result["metrics"]["memory_delta_mb"] = round(mem_after - mem_before, 2)
    result["metrics"]["memory_after_mb"] = mem_after

    tracemalloc.stop()
    return result


# ── Test: HTTP simple ────────────────────────────────────────────────────────

async def test_site_with_http(
    target: dict[str, str],
) -> dict[str, Any]:
    """Prueba un sitio con HTTP simple (httpx) para comparar con Playwright."""
    result: dict[str, Any] = {
        "name": target["name"],
        "method": "http_simple",
        "url": _build_search_url(target),
        "success": False,
        "error": None,
        "metrics": {},
        "content": {},
    }

    if not HTTPX_AVAILABLE:
        result["error"] = "httpx no instalado"
        return result

    overall_start = time.perf_counter()

    try:
        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"User-Agent": HTTP_USER_AGENT},
        ) as client:
            req_start = time.perf_counter()
            search_url = _build_search_url(target)
            response = await client.get(search_url)
            result["metrics"]["request_time_s"] = round(
                time.perf_counter() - req_start, 2
            )
            result["metrics"]["http_status"] = response.status_code

            html = response.text
            result["content"] = _content_indicators(html)

            result["success"] = bool(
                response.status_code == 200
                and len(html) > 500
                and (result["content"]["has_links"] or result["content"]["has_images"])
            )

    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    result["metrics"]["total_time_s"] = round(
        time.perf_counter() - overall_start, 2
    )
    return result


# ── Comparacion ──────────────────────────────────────────────────────────────

def compare_results(
    pw: dict[str, Any],
    http: dict[str, Any],
) -> dict[str, Any]:
    """Compara los resultados de Playwright vs HTTP simple para un sitio."""
    comparison = {
        "site": pw["name"],
        "playwright_success": pw["success"],
        "http_success": http["success"],
        "playwright_html_length": pw.get("content", {}).get("html_length", 0),
        "http_html_length": http.get("content", {}).get("html_length", 0),
        "playwright_total_time_s": pw.get("metrics", {}).get("total_time_s"),
        "http_total_time_s": http.get("metrics", {}).get("total_time_s"),
        "playwright_error": pw.get("error"),
        "http_error": http.get("error"),
    }

    # Determinar si Playwright aporta valor:
    # Caso A: Playwright OK, HTTP falla → bypass anti-bot/SPA efectivo
    comparison["playwright_adds_value"] = (
        pw["success"] and not http["success"]
    )
    # Caso B: Playwright OK, HTTP OK pero con mas contenido → SPA parcial
    pw_len = comparison["playwright_html_length"]
    http_len = comparison["http_html_length"]
    comparison["playwright_richer_content"] = (
        pw["success"]
        and http["success"]
        and pw_len > http_len * 1.2
    )

    return comparison


# ── Main ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    """Ejecuta la bateria de pruebas y genera el informe."""
    timestamp = datetime.now(timezone.utc)

    print(f"=== Prototipo Playwright — {timestamp.isoformat()} ===\n")
    print(f"Playwright instalado: {PLAYWRIGHT_AVAILABLE}")
    print(f"httpx instalado:      {HTTPX_AVAILABLE}")
    print(f"psutil instalado:     {PSUTIL_AVAILABLE}")
    print()

    # Modo sin Playwright: generar informe de intencion
    if not PLAYWRIGHT_AVAILABLE:
        report = {
            "status": "PLAYWRIGHT_NOT_INSTALLED",
            "timestamp": timestamp.isoformat(),
            "message": (
                "Playwright no esta instalado en este entorno. "
                "Instalalo con: pip install playwright && playwright install chromium"
            ),
            "targets": [
                {
                    "name": t["name"],
                    "url": _build_search_url(t),
                    "reason": t["reason"],
                    "would_test": "playwright + http_comparison",
                }
                for t in TARGETS
            ],
            "metrics_that_would_be_collected": [
                "browser_launch_time_s",
                "first_navigation_time_s",
                "second_navigation_time_s",
                "memory_delta_mb",
                "http_status",
                "html_length (playwright vs http)",
                "playwright_adds_value (bool)",
                "playwright_richer_content (bool)",
            ],
        }
        print(json.dumps(report, indent=2, ensure_ascii=False))

        out_path = os.path.join(
            REPORT_DIR,
            f"playwright_report_{timestamp.strftime('%Y%m%d_%H%M%S')}.json",
        )
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nInforme guardado en: {out_path}")
        return

    # Modo completo: ejecutar todas las pruebas
    pw_results: list[dict[str, Any]] = []
    http_results: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []

    for target in TARGETS:
        name = target["name"]
        print(f"--- Probando {name} ---")

        # HTTP primero (mas rapido, sirve de baseline)
        print(f"  HTTP simple...")
        http_result = await test_site_with_http(target)
        http_results.append(http_result)
        print(f"    Success: {http_result['success']}, "
              f"HTML: {http_result.get('content', {}).get('html_length', 'N/A')} chars, "
              f"Time: {http_result.get('metrics', {}).get('total_time_s', 'N/A')}s")

        # Playwright
        print(f"  Playwright...")
        pw_result = await test_site_with_playwright(target)
        pw_results.append(pw_result)
        print(f"    Success: {pw_result['success']}, "
              f"HTML: {pw_result.get('content', {}).get('html_length', 'N/A')} chars, "
              f"Time: {pw_result.get('metrics', {}).get('total_time_s', 'N/A')}s")

        comparison = compare_results(pw_result, http_result)
        comparisons.append(comparison)
        print(f"    Playwright adds value: {comparison['playwright_adds_value']}")
        print()

    # ── Informe consolidado ──────────────────────────────────────────
    successful_pw = sum(1 for r in pw_results if r["success"])
    pw_times = [r.get("metrics", {}).get("total_time_s", 0) for r in pw_results if r["success"]]
    http_times = [r.get("metrics", {}).get("total_time_s", 0) for r in http_results if r["success"]]

    report = {
        "status": "COMPLETED",
        "timestamp": timestamp.isoformat(),
        "environment": {
            "playwright_available": PLAYWRIGHT_AVAILABLE,
            "httpx_available": HTTPX_AVAILABLE,
            "psutil_available": PSUTIL_AVAILABLE,
        },
        "results": pw_results,
        "http_baseline": http_results,
        "comparisons": comparisons,
        "summary": {
            "sites_tested": len(TARGETS),
            "playwright_successful": successful_pw,
            "playwright_success_rate": (
                round(successful_pw / len(TARGETS) * 100, 1)
                if TARGETS else 0
            ),
            "http_successful": sum(1 for r in http_results if r["success"]),
            "playwright_avg_time_s": (
                round(sum(pw_times) / len(pw_times), 2) if pw_times else None
            ),
            "http_avg_time_s": (
                round(sum(http_times) / len(http_times), 2) if http_times else None
            ),
            "playwright_adds_value_count": sum(
                1 for c in comparisons if c["playwright_adds_value"]
            ),
            "playwright_richer_content_count": sum(
                1 for c in comparisons if c["playwright_richer_content"]
            ),
        },
        "recommendations": _generate_recommendations(comparisons, pw_times),
    }

    print(json.dumps(report, indent=2, ensure_ascii=False))

    out_path = os.path.join(
        REPORT_DIR,
        f"playwright_report_{timestamp.strftime('%Y%m%d_%H%M%S')}.json",
    )
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nInforme guardado en: {out_path}")


def _generate_recommendations(
    comparisons: list[dict[str, Any]],
    pw_times: list[float],
) -> list[str]:
    """Genera recomendaciones basadas en los resultados de la evaluacion."""
    recs: list[str] = []

    adds_value = sum(1 for c in comparisons if c["playwright_adds_value"])
    richer = sum(1 for c in comparisons if c["playwright_richer_content"])

    if adds_value >= 2:
        recs.append(
            "INTEGRAR: Playwright resuelve al menos 2 sitios que HTTP simple "
            "no puede manejar. Justifica el coste de recursos."
        )
    elif adds_value == 1:
        recs.append(
            "CONSIDERAR: Playwright anade valor en 1 sitio. Evaluar si ese "
            "provider especifico justifica la dependencia."
        )
    else:
        recs.append(
            "NO_INTEGRAR: Playwright no aporta ventajas sobre HTTP simple "
            "+ cloudscraper para los sitios probados."
        )

    if pw_times:
        avg_pw = sum(pw_times) / len(pw_times)
        if avg_pw > 15:
            recs.append(
                f"RENDIMIENTO_INACEPTABLE: Tiempo medio de {avg_pw:.1f}s "
                f"por request con Playwright (>15s umbral). Considerar "
                f"pool de browsers calientes o descartar integracion."
            )
        elif avg_pw > 8:
            recs.append(
                f"RENDIMIENTO_MARGINAL: Tiempo medio de {avg_pw:.1f}s "
                f"por request. Requiere pool de browsers para ser viable."
            )
        else:
            recs.append(
                f"RENDIMIENTO_ACEPTABLE: Tiempo medio de {avg_pw:.1f}s "
                f"por request. Dentro del umbral de <10s."
            )

    if richer >= 2:
        recs.append(
            "SPA_PARCIAL: Playwright extrae mas contenido que HTTP simple "
            "en varios sitios con SSR parcial."
        )

    return recs


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    asyncio.run(main())
