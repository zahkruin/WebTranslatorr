# WebTranslatorr

Universal Torznab Proxy - Conecta aplicaciones *Arr con fuentes de contenido español.

## ¿Qué es?

WebTranslatorr es un proxy que traduce peticiones estándar Torznab/Newznab a scraping de sitios web de contenido en español:

- **Libros**: [Ebookelo](https://ww2.ebookelo.com) (EPUB, MOBI, PDF)
- **Películas/Series**: [MejorTorrent](https://www42.mejortorrent.eu) / [DonTorrent](https://dontorrent.reisen) (.torrent)

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
│   ├── providers/     # Scrapers (Ebookelo, MejorTorrent, DonTorrent)
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
