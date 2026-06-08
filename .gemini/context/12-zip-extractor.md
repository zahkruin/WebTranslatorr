# 12 — ZIP Extractor

## Propósito

Documenta el `ZipExtractor`, un extractor on-the-fly de archivos EPUB desde archivos ZIP en memoria. Algunos providers (HolaEbook) sirven los libros como archivos ZIP que contienen el EPUB. El extractor busca y extrae el EPUB sin escribir en disco.

Cuándo consultar: para modificar la lógica de extracción, añadir soporte para otros formatos, o depurar problemas con providers que usan ZIP.

---

## Interfaz

**Archivo:** `app/utils/zip_extractor.py`

```python
class ZipExtractor:
    @staticmethod
    def extract_epub_from_memory(zip_bytes: bytes) -> bytes | None:
```

### Parámetros
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `zip_bytes` | `bytes` | Contenido binario del archivo ZIP |

### Retorno
- `bytes` — Contenido del primer archivo `.epub` encontrado en el ZIP
- `None` — Si no se encuentra ningún EPUB o el ZIP es inválido

---

## Algoritmo

**Archivo:** `app/utils/zip_extractor.py:9-27`

```python
@staticmethod
def extract_epub_from_memory(zip_bytes: bytes) -> bytes | None:
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for file_info in zf.infolist():
                if file_info.filename.lower().endswith('.epub'):
                    logger.info(f"Extracting EPUB: {file_info.filename}")
                    with zf.open(file_info) as f:
                        return f.read()
    except zipfile.BadZipFile:
        logger.error("Los bytes proporcionados no corresponden a un archivo ZIP válido.")
    except Exception as e:
        logger.error(f"Error al extraer ZIP en memoria: {e}")
    
    return None
```

**Pasos:**
1. Envolver `zip_bytes` en `io.BytesIO` (procesar en memoria)
2. Abrir como `zipfile.ZipFile`
3. Iterar `infolist()` buscando archivos con extensión `.epub`
4. Devolver los bytes del primer EPUB encontrado
5. Si no hay EPUBs o el ZIP es inválido → `None`

**Manejo de errores:**
- `zipfile.BadZipFile` → loggear error, devolver `None`
- Cualquier otra excepción → loggear error, devolver `None`

---

## Integración con el Download Proxy

**Archivo:** `app/api/torznab.py:317-321`

```python
# En download_proxy():
if getattr(prov, 'is_zipped', False):
    extracted = ZipExtractor.extract_epub_from_memory(file_bytes)
    if extracted:
        file_bytes = extracted
        fmt = "epub"
```

**Flujo de descarga con ZIP:**
1. `provider.get_download_url()` devuelve la URL del ZIP
2. `http_client.download_file()` descarga los bytes del ZIP
3. Si el provider tiene `is_zipped = True`:
   - `ZipExtractor.extract_epub_from_memory()` extrae el EPUB
   - Si tiene éxito, los bytes del EPUB reemplazan a los del ZIP
   - El Content-Type se ajusta a `application/epub+zip`
4. Los bytes (EPUB extraído o ZIP original) se sirven al *Arr

---

## Providers que Usan ZIP

| Provider | Flag `is_zipped` | Comportamiento |
|----------|-----------------|----------------|
| HolaEbook | `True` | Descarga ZIPs, extrae EPUB on-the-fly |

**Cómo añadir soporte ZIP a un nuevo provider:**
1. Añadir `self.is_zipped = True` en el constructor del provider
2. Asegurarse de que `get_download_url()` devuelva la URL de un ZIP
3. El download proxy manejará la extracción automáticamente

---

## Limitaciones

1. **Solo extrae EPUB** — Si el ZIP contiene MOBI, PDF u otros formatos, se ignoran. El extractor solo busca `.epub`.
2. **Primer EPUB encontrado** — Si el ZIP contiene múltiples EPUBs, solo se extrae el primero.
3. **En memoria** — Archivos ZIP muy grandes pueden causar alto consumo de memoria.
4. **No hay soporte para ZIPs con contraseña** — Si el ZIP está protegido, fallará con `BadZipFile` u otra excepción.

---

## Archivos Relevantes

| Archivo | Rol |
|---------|-----|
| `app/utils/zip_extractor.py` | Implementación del extractor |
| `app/api/torznab.py:317-321` | Integración en download proxy |
| `app/providers/books/holaebook.py` | Ejemplo de provider con `is_zipped = True` |
