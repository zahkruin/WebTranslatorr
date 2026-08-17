# Estrategia de Scraping - Ebookelo

## URLs del Sitio

| Componente | Patrón URL |
|------------|------------|
| Búsqueda | `/buscar/{query}` |
| Detalle | `/ebook/{id}/{slug}` |
| Descarga | `/download/{id}/{format}` |
| Magnet | `/download/{id}/magnet` |

## Selectores CSS Clave

```python
# Resultados de búsqueda
soup.select('a[href*="/ebook/"]')

# Autor en página de detalle
soup.select_one('a[href*="/ebooks/autor/"]')

# Género
soup.select_one('a[href*="/ebooks/genero/"]')

# Formatos disponibles (reales)
soup.select('a[href*="/download/"]')
```

## Trampa del Ad-Gate

**IMPORTANTE**: La página de detalle tiene **dos sets** de botones de descarga:

1. **Enlaces SUPERIORES (TRAMPA)**: Apuntan a `profitablecpmgate.com`
   - Son publicidad
   - **IGNORAR COMPLETAMENTE**
   - Selector: `a[href*="profitablecpmgate"]`

2. **Enlaces INFERIORES (REALES)**: Apuntan a `/download/{id}/{format}`
   - Son los enlaces de descarga directa
   - Usar estos exclusivamente

## Flujo de Descarga

```python
# 1. Hacer GET a /download/{id}/{format} SIN seguir redirects
response = await http_client.get(
    download_url,
    follow_redirects=False,
    headers={"Referer": f"{BASE_URL}/ebook/{book_id}/"}
)

# 2. Si responde 302 → Location es la URL del archivo
if response.status_code in (301, 302, ...):
    return response.headers.get("Location")

# 3. Si responde 200 con binario → es el archivo directo
# 4. Si responde 200 con HTML → buscar URL real en el HTML
```

## Formatos Soportados

Prioridad: EPUB > MOBI > PDF > Magnet

```python
PREFERRED_FORMAT_ORDER = ["epub", "mobi", "pdf"]
```

## Deduplicación

El sitio puede listar el mismo libro en diferentes idiomas. Deduplicar por `book_id`.
