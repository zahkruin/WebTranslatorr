# 14 — Deployment

## Propósito

Guía de despliegue de WebTranslatorr. Cubre Docker Compose, Docker build manual, despliegue bare-metal, y configuración de entorno.

Cuándo consultar: para desplegar en producción, configurar variables de entorno, o solucionar problemas de conectividad con las *Arr apps.

---

## Opciones de Despliegue

### Opción 1: Docker Compose (Recomendado)

**Archivo:** `docker-compose.yml`

```bash
# 1. Configurar variables de entorno
cp .env.example .env
# Editar .env con tu API key y dominios

# 2. Iniciar
docker-compose up -d

# 3. Verificar
curl http://localhost:9811/health
```

**Puertos:**
- Host: `9811` → Container: `9811`

**Volúmenes:**
- `./data:/app/data` — Persistencia de configuración (SQLite `webtranslatorr.db`) y dominios resueltos (`domains.json`)

**Uso de imagen pre-built:**
```yaml
image: ghcr.io/zahkruin/webtranslatorr:latest
```

**Uso de build local:**
```yaml
# Comentar la línea 'image' y descomentar:
build: .
```

### Opción 2: Docker Manual

```bash
# Build
docker build -t webtranslatorr .

# Run
docker run -d \
  --name webtranslatorr \
  -p 9811:9811 \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  webtranslatorr
```

### Opción 3: Bare-Metal

**Archivo:** `deploy.sh`

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Configurar entorno
cp .env.example .env
# Editar .env

# 3. Ejecutar
python main.py
```

El servidor escucha en `http://0.0.0.0:9811`.

---

## Variables de Entorno Requeridas

### Variables críticas (sin defaults seguros)

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `WTR_API_KEY` | API key para autenticación *Arr | `a1b2c3d4e5f6...` |

### Variables con defaults (opcionales)

| Variable | Default | Cuándo cambiar |
|----------|---------|---------------|
| `WTR_EXTERNAL_URL` | `http://localhost:9811` | Si WebTranslatorr está en otro host/container |
| `WTR_PORT` | `9811` | Si el puerto está en uso |
| `WTR_LOG_LEVEL` | `INFO` | A `DEBUG` para troubleshooting |

Ver `context/02-configuration.md` para la lista completa.

---

## Configuración del Entorno para *Arr Apps

### Si WebTranslatorr y las *Arr están en el mismo Docker network:

```yaml
# docker-compose.yml de las *Arr
networks:
  - webtranslatorr_webtranslatorr
```

URL en *Arr: `http://webtranslatorr:9811/api`

### Si WebTranslatorr está en otro host:

1. Asegurarse de que `WTR_EXTERNAL_URL` apunte a una IP accesible:
   ```bash
   WTR_EXTERNAL_URL=http://192.168.1.100:9811
   ```

2. Configurar la URL en las *Arr apps con esa IP.

---

## Panel de Administración Web (v0.3.0+)

A partir de v0.3.0, WebTranslatorr incluye un panel de administración accesible en la raíz:

```bash
# Acceder al panel de administración
open http://localhost:9811/
```

El panel permite:
- Habilitar/deshabilitar providers sin editar `.env` ni reiniciar
- Gestionar API keys, URLs externas y proxy
- Configurar instancias Readarr y sincronizar indexers one-click

La configuración se persiste en `data/webtranslatorr.db` (SQLite) y sobrevive a reinicios del contenedor gracias al volumen `./data:/app/data`.

---

## Verificación de Salud

```bash
# Health check básico
curl http://localhost:9811/health
# {"status":"healthy","service":"WebTranslatorr"}

# Verificar capabilities
curl "http://localhost:9811/api?t=caps&apikey=xxx"

# Verificar dominios resueltos
curl http://localhost:9811/api/domains

# Forzar resolución de dominios
curl -X POST http://localhost:9811/api/domains/refresh
```

---

## Dockerfile

**Archivo:** `Dockerfile`

- Base: `python:3.11-slim`
- Puerto expuesto: `9811`
- Comando: `python main.py`
- WORKDIR: `/app`

---

## CI/CD

**Archivo:** `.github/workflows/docker.yml`

- Build automático de imagen Docker en cada push
- Publicación en `ghcr.io/zahkruin/webtranslatorr`

---

## Troubleshooting de Despliegue

### "Connection refused" desde las *Arr
1. Verificar que WebTranslatorr está corriendo: `docker ps | grep webtranslatorr`
2. Verificar conectividad de red entre contenedores
3. Verificar `WTR_EXTERNAL_URL` (no usar `0.0.0.0` o `localhost` si las *Arr están en otro host)

### "API Key incorrect" en *Arr
1. Verificar que `WTR_API_KEY` coincide en `.env` y en la configuración de la *Arr app
2. La API key se pasa como query param: `?apikey=xxx`

### Providers no devuelven resultados
1. Verificar dominios: `GET /api/domains`
2. Forzar resolución: `POST /api/domains/refresh`
3. Revisar logs: `docker logs webtranslatorr`

---

## Archivos Relevantes

| Archivo | Rol |
|---------|-----|
| `Dockerfile` | Definición de imagen Docker |
| `docker-compose.yml` | Orquestación Docker Compose |
| `deploy.sh` | Script de despliegue bare-metal |
| `.env.example` | Template de variables de entorno |
| `.github/workflows/docker.yml` | CI/CD |
| `main.py` | Entry point |
| `config.py` | Configuración Pydantic |
| `app/persistence/` | Persistencia SQLite |
| `static/` | Frontend de administración |
