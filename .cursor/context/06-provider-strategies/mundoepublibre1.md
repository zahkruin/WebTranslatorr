# Estrategia: MundoEpubLibre1

## Provider ID: `mundoepublibre1`

## Propósito

Documenta la estrategia de scraping para MundoEpubLibre1 (`mundoepublibre1.com`), un sitio WordPress de libros electrónicos en español. Provider nuevo añadido en la expansión multi-indexer. Similar a EpubLibre y LectuEpubLibre5.

## URLs del Sitio

| Componente | Patrón URL | Ejemplo |
|------------|------------|---------|
| Búsqueda | `/?s={query}` | `https://mundoepublibre1.com/?s=quijote` |
| Detalle | `/book/{slug}/` o `/libro/{slug}/` | Variable |
| Descarga | Enlace directo o archivo | Variable |

## Constructor

```python
def __init__(self, http_client, domain_resolver=None):
    domain = settings.MUNDOEPUBLIBRE1_DOMAIN
    if domain_resolver:
        active_domain = domain_resolver.get_current("mundoepublibre1")
        if active_domain:
            domain = active_domain
    super().__init__(
        provider_id="mundoepublibre1",
        display_name="MundoEpubLibre1",
        base_url=domain,
        http_client=http_client,
        categories=[7000, 7020, 8000, 8010]
    )
```

## Estrategia de Búsqueda (`search()`)

Idéntica a `LectuEpubLibre5Provider`:

- URL: `/?s={query}`
- Selectores: `a[href*="/book/"]`, `a[href*="/libro/"]`, `h2.entry-title a`, `h3.entry-title a`
- Filtrado: `biblioteca`, `inicio`, `home`
- Internal ID: regex `/(?:book|libro)/([^/]+)/`

## Estrategia de Descarga (`get_download_url()`)

Idéntica a `LectuEpubLibre5Provider`:

- Triple path: `/book/`, `/libro/`, `/descargar/`
- Doble búsqueda: texto "DESCARGAR" / "DOWNLOAD" + enlaces directos a archivos
- Filtrado: excluye `/genre/`, `/autor/`

## Diferencias con Otros Providers Similares

| Característica | MundoEpubLibre1 | LectuEpubLibre5 | Epubflix1 | EpubLibre |
|---------------|-----------------|-----------------|-----------|-----------|
| URL búsqueda | `/?s=` | `/?s=` | `/?s=` | `/?s=` |
| Paths detalle | `/book/`, `/libro/`, `/descargar/` | `/book/`, `/libro/`, `/descargar/` | `/book/`, `/libro/` | `/book/` |
| Filtro navegación | `/genre/`, `/autor/` | `/genre/`, `/autor/` | No | No |
| Cloudscraper | Sí | Sí | Sí | Sí |

## Trampas

1. **Código casi idéntico a LectuEpubLibre5** — Si uno falla, probablemente el otro también.
2. **Provider nuevo** — Sin tests.

## Archivos
- `app/providers/books/mundoepublibre1.py`
- `config.py` — `MUNDOEPUBLIBRE1_ENABLED`, `MUNDOEPUBLIBRE1_DOMAIN`
