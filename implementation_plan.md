# Plan de Integración: Expansión de Ebooks (Anna's Archive & Tracker Hispanos)

El objetivo es convertir WebTranslatorr en el proxy definitivo de Torznab para contenido de libros en español, integrando los proveedores más consolidados del panorama "shadow library" y bibliotecas libres.

---

## 1. Anna's Archive (El Meta-Buscador Total)

Anna's Archive es un buscador masivo sin ánimo de lucro que consolida Library Genesis, Z-Library, Sci-Hub e infinidad de bases de datos. Ofrece una cobertura prácticamente total.

### Mecanismos
*   **Búsqueda:** Búsquedas GET simples: `https://annas-archive.org/search?q={query}&lang=es&ext=epub`
*   **Capacidades Panzers:** Búsqueda exacta por ISBN o DOI (perfecto para las automatizaciones de Readarr).
*   **Descarga:** La página del libro tiene enlaces a múltiples pasarelas ("Slow Partner Server", "Z-Lib", "Libgen").
*   **Desafío Principal:** Anna's Archive a veces utiliza bloqueos Cloudflare (que requieren uso de bibliotecas como `cloudscraper` o configuraciones específicas en `httpx`). Además, los enlaces "Slow" involucran tiempos de espera de 1-3 minutos, lo que requerirá que el `get_download_url()` devuelva la URL final sorteando los capchas internos o tiempos de espera, o usando los *mirrors* directos compatibles.

## 2. Los Grandes Clásicos: EpubLibre y Lectulandia

(Para más detalle técnico consultar las revisiones previas)
*   **EpubLibre (`epublibre.bid`)**:
    *   Búsqueda muy sencilla (`/?s=query`).
    *   Para llegar al archivo final hay que dar dos pasos: 1) Página del libro, 2) Botón de descarga de cada formato (que redirige al real).
*   **Lectulandia (`ww3.lectulandia.co`)**:
    *   Búsqueda: `/search/{query}`
    *   Ofuscamiento intermedio: El botón descarga a un `/download.php?t=1...` que genera en JavaScript un código en base64 (`var linkCode="X"`), el cual reenvía a una página final `/download/X`. A implementar parseando el HTML con regex.

## 3. Espaebook

Junto con Epublibre, es uno de los mayores contenedores de habla hispana.
*   **Estructura**: Muy similar a Lectulandia (suelen incluso compartir arquitecturas).
*   **Mecanismo**: Búsquedas por POST o GET según el mirror. Usa páginas intermedias con timers de 10-15 segundos. Se puede hacer "bypass" extrayendo la URL final alojada en servidores de descargas como Mega, Zippyshare (históricamente) o servidores privados.

## 4. HolaEbook / MegaEpub

Portales más directos y especializados en "Best-Sellers" y novedades.
*   **Mecanismo**: Búsqueda por `GET`. Los enlaces de los libros dirigen a un ZIP que en su interior tiene el EPUB, PDF o MOBI.
*   **Desafío**: Puede que si ofrecen el formato directo como `.zip`, debamos manejar en Readarr que el Content-Type sea `application/zip` o, en un nivel de abstracción mayor, que WebTranslatorr descargue el ZIP en memoria, extraiga el EPUB y se lo devuelva directamente a Readarr en caliente. (Recomendado: devolver el `.epub` desempaquetado al vuelo para ser 100% compatibles con el importador automático de Readarr).

## 5. Elejandría / Proyecto Gutenberg

Plataformas completamente gratis, 100% legales y sin DRM (Dominio Público).
*   **Elejandría**:
    *   Búsqueda directa `GET` `/buscar?q={query}`.
    *   Descarga directa de los archivos EPUB alojados en sus propios servidores amazon s3 sin ofuscación. Muy fácil integración.
*   **Proyecto Gutenberg**:
    *   Se puede buscar directamente por API o por un listado en texto plano.
    *   Descarga directa sin restricciones.

---

## Estrategia de Implementación

Dado que hablamos de **más de 6 nuevos proveedores** con sus particularidades:

1.  **Framework de ByPass:** Mejorar el `HttpClient` agregando `cloudscraper` (librería externa) al `requirements.txt` para lidiar transparentemente con Cloudflare (especialmente crucial para Anna's Archive).
2.  **Extracción de Archivos al Vuelo (`ZipExtractor`):** Muchos proveedores menores (HolaEbook) distribuyen el EPUB dentro de un archivo `.zip` para esquivar la detección directa de formatos. WebTranslatorr debería integrar una utilidad nativa para extraer el EPUB del buffer ZIP en RAM antes de devolverlo a Readarr.
3.  **Registro de Providers:** Desarrollaremos iterativamente, empezando por los de acceso directo (Elejandría, EpubLibre), pasando a los de redirect (Lectulandia, Espaebook), los de zip (HolaEbook) y finalmente el "Coloso" (Anna's Archive), asegurándonos de que cada uno esté protegido bajo banderas booleanas del `.env` (`HOLAEBOOK_ENABLED=true`, etc.).

> [!NOTE]
> **Usuario**: Por favor revisa este plan ampliado. Si estás de acuerdo con incorporar estas mejoras (como Cloudscraper y la extracción de ZIP en memoria para servir ePubs nativamente a Readarr), confirmámelo y procederé con la implementación.
