# WebTranslatorr

Universal Torznab Proxy - Conecta aplicaciones *Arr con fuentes de contenido español.

## ¿Qué es?

WebTranslatorr es un proxy que traduce peticiones estándar Torznab/Newznab a scraping de sitios web de contenido en español:

- **Libros**: [EpubLibre](https://epublibre.bid), [Lectulandia](https://ww3.lectulandia.co), [HolaEbook](https://holaebook.com), [Espaebook](https://espaebook.cc), [Anna's Archive](https://annas-archive.org), [Ebookelo](https://ww2.ebookelo.com) (Extrae EPUB, MOBI, PDF).
- **Películas/Series**: [MejorTorrent](https://www42.mejortorrent.eu) / [DonTorrent](https://dontorrent.reisen) (.torrent)

### 🔥 Características Destacadas
- **Bypass Automático Múltiple**: El proxy saltea barreras de redirección base y Cloudflare mediante HTTP y simulaciones usando *cloudscraper*.
- **Resolución dinámica de Dominios (`DomainResolver`)**: Si una biblioteca pirata bloquea o tira su dominio general, la aplicación rastrea mirrors actualizados en canales de Telegram y chequea el /health para reenganchar al instante.
- **Zip-Extractor "On-the-Fly"**: Algunas web (ej. HolaEbook) sirven los EPUBs tapados en archivos `.zip`. WebTranslatorr intercepta el ZIP en la RAM del sistema en pleno vuelo, extrae el archivo maestro y se lo sirve directamente y desencriptado a Readarr.

Compatible con: Readarr, Sonarr, Radarr, y cualquier app que soporte Torznab.

## Instalación

### Docker (Recomendado)

1. **Clonar y Preparar el entorno:**
   ```bash
   cp .env.example .env
   ```
2. **Configurar tu API Key:**
   Abre el archivo `.env` recién creado y cambia `WTR_API_KEY` por una contraseña segura y los dominios o features que desees activar.
   ```bash
   WTR_API_KEY=tu_api_key_segura
   WTR_EBOOKELO_ENABLED=true
   WTR_MEJORTORRENT_ENABLED=true
   ```

3. **Desplegar:**
   ```bash
   docker-compose up -d
   ```

### Manual

```bash
cp .env.example .env
pip install -r requirements.txt
python main.py
```

## Uso en *Arr Apps

Configura como indexer Torznab:

- **URL**: `http://localhost:9811/api`
- **API Key**: La que hayas configurado en `WTR_API_KEY`
- **Categories**: 7000-8999 (libros), 2000-2999 (películas), 5000-5999 (TV)

## Endpoints

| Endpoint | Descripción |
|----------|-------------|
| `/api?t=caps` | Capabilities |
| `/api?t=search&q=...` | Búsqueda genérica |
| `/api?t=book&q=...` | Libros |
| `/api?t=movie&imdbid=...` | Películas por IMDb |
| `/api?t=tvsearch&q=...` | Series |
| `/health` | Health check |

## Estructura del Proyecto

```
WebTranslatorr/
├── app/
│   ├── api/           # Endpoints FastAPI
│   ├── core/          # Modelos y utilidades
│   ├── providers/     # Scrapers: Epublibre, AnnasArchive, HolaEbook, Lectulandia, MejorTorrent, DonTorrent...
│   ├── routing/       # Smart Router
│   ├── scraping/      # HTTP client con rate-limiting
│   └── torznab/       # Generación XML
├── tests/             # Tests pytest
├── .gemini/           # Documentación agéntica
└── docs/              # Documentación técnica
```

## Tests

```bash
pytest tests/ -v
```

## Licencia

MIT
