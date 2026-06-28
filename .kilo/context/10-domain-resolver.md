# 10 — Domain Resolver

## Propósito

Documenta el sistema de resolución dinámica de dominios. Los sitios de contenido (MejorTorrent, DonTorrent, Ebookelo, etc.) cambian de dominio frecuentemente. El `DomainResolver` mantiene actualizada la URL base de cada provider usando una cadena de estrategias de resolución.

Cuándo consultar: cuando un provider deja de funcionar por cambio de dominio, para depurar la resolución, o para añadir nuevos providers con dominios inestables.

---

## Arquitectura

```
DomainResolver
    │
    ├── DomainConfig (por provider)
    │   ├── provider_id, default_domain
    │   ├── privtree_path (ruta en privtr.ee)
    │   ├── telegram_channel (canal de Telegram)
    │   └── known_domain_pattern (regex)
    │
    ├── ResolvedDomain (estado actual)
    │   ├── url, resolved_at, source
    │   ├── healthy, last_health_check
    │   └── persistido en data/domains.json
    │
    ├── Cadena de estrategias (en orden):
    │   ├── 1. PrivtreeStrategy    (scraping de privtr.ee)
    │   ├── 2. TelegramPublicStrategy (scraping de t.me/s/)
    │   └── 3. HealthCheckStrategy    (HTTP HEAD al dominio conocido)
    │
    └── Background loop: domain_check_loop (cada 30 min)
```

---

## Flujo de Resolución

### `async resolve(provider_id) → str`

**Archivo:** `app/services/domain_resolver.py:127-194`

```
1. Obtener DomainConfig del provider
2. Intentar cada estrategia en orden:
   a. PrivtreeStrategy.resolve(config, http_client)
      - GET https://privtr.ee/{config.privtree_path}
      - Buscar enlaces que matcheen known_domain_pattern
      - Si encuentra → validar con HTTP HEAD → devolver
   
   b. TelegramPublicStrategy.resolve(config, http_client)
      - GET https://t.me/s/{config.telegram_channel}
      - Buscar en mensajes (orden inverso, más reciente primero)
      - Si encuentra → validar con HTTP HEAD → devolver
   
   c. HealthCheckStrategy.resolve(config, http_client)
      - HTTP HEAD al dominio por defecto
      - Si responde < 400 → devolver dominio (siguiendo redirects)
      - Si falla → devolver None
3. Si ninguna estrategia funciona → mantener el último dominio conocido
4. Si el dominio cambió → notificar callbacks + persistir
```

### Validación de Dominios

**Archivo:** `app/services/domain_resolver.py:227-238`

```python
async def _validate_domain(self, url: str) -> bool:
    response = await self._http_client.head(
        url, follow_redirects=True, timeout=self._validation_timeout
    )
    return response.status_code < 400
```

Las estrategias Privtree y Telegram validan el candidato con HTTP HEAD antes de aceptarlo. La estrategia HealthCheck ya valida implícitamente.

---

## Estrategias de Resolución

### 1. PrivtreeStrategy

**Archivo:** `app/services/domain_strategies.py:50-98`

- Fuente: `https://privtr.ee/{path}`
- Los sitios mantienen una landing page en privtr.ee con enlaces al dominio actual
- Busca todos los `<a href>` que matcheen `known_domain_pattern`
- Normaliza la URL a `scheme://netloc` (elimina path, query, fragment)

**Providers que usan esta estrategia:**
| Provider | privtree_path |
|----------|--------------|
| mejortorrent | `@mejortorrent` |
| dontorrent | `@dontorrent` |

### 2. TelegramPublicStrategy

**Archivo:** `app/services/domain_strategies.py:101-176`

- Fuente: `https://t.me/s/{channel}` (vista web pública de Telegram)
- No requiere API key ni autenticación
- Busca en los mensajes más recientes primero (orden inverso)
- Busca enlaces que matcheen `known_domain_pattern`
- Fallback: si no encuentra en mensajes, busca en todo el HTML

**Providers que usan esta estrategia:**
| Provider | telegram_channel |
|----------|-----------------|
| mejortorrent | `MejorTorrentAp` |
| dontorrent | `DonTorrent` |

### 3. HealthCheckStrategy

**Archivo:** `app/services/domain_strategies.py:179-220`

- Fuente: el `default_domain` del `DomainConfig`
- Hace HTTP HEAD con `follow_redirects=True`
- Si el dominio redirige, devuelve el dominio final
- Es la estrategia de último recurso (menos fiable)

---

## DomainConfig

**Archivo:** `app/services/domain_strategies.py:20-27`

```python
@dataclass
class DomainConfig:
    provider_id: str
    default_domain: str
    privtree_path: Optional[str] = None
    telegram_channel: Optional[str] = None
    known_domain_pattern: str = ""
```

Cada provider que necesita resolución dinámica se registra con su `DomainConfig` en el startup de FastAPI.

**Ejemplo (MejorTorrent):**
```python
resolver.register_provider(DomainConfig(
    provider_id="mejortorrent",
    default_domain=settings.MEJORTORRENT_DOMAIN,
    privtree_path="@mejortorrent",
    telegram_channel="MejorTorrentAp",
    known_domain_pattern=r"mejortorrent\.\w+",
))
```

**Providers registrados actualmente:**
| Provider | privtree | telegram |
|----------|----------|----------|
| mejortorrent | @mejortorrent | MejorTorrentAp |
| dontorrent | @dontorrent | DonTorrent |
| ebookelo | — | — |
| epublibre | @epublibre | — |
| lectulandia | @lectulandia | — |
| espaebook | — | — |
| holaebook | — | — |
| annasarchive | — | — |
| epubflix1 | — | — |
| libgen | — | — |
| booobook | — | — |
| lectuepublibre5 | — | — |
| mundoepublibre1 | — | — |
| zlibrary | — | — |

---

## Persistencia

**Archivo:** `app/services/domain_resolver.py:248-282`

Los dominios resueltos se persisten en `data/domains.json`:

```json
{
  "mejortorrent": {
    "url": "https://www42.mejortorrent.eu",
    "resolved_at": "2026-06-08T07:10:45+00:00",
    "source": "privtree",
    "healthy": true,
    "last_health_check": "2026-06-08T07:10:45+00:00"
  }
}
```

- Se carga al iniciar (`_load_persisted()`)
- Se guarda después de cada resolución exitosa (`_persist()`)
- Sobrevive a reinicios del servidor

---

## Background Loop

**Archivo:** `app/services/domain_resolver.py:285-307`

```python
async def domain_check_loop(resolver: DomainResolver, interval: int = 1800):
    while True:
        await asyncio.sleep(interval)
        results = await resolver.resolve_all()
```

Se ejecuta como tarea de background en el event loop de FastAPI. Por defecto cada 30 minutos (`WTR_DOMAIN_CHECK_INTERVAL`).

---

## API de Dominios

**Archivo:** `app/api/domains.py`

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/domains` | GET | Estado de todos los dominios |
| `/api/domains/refresh` | POST | Forzar resolución de todos |
| `/api/domains/refresh/{id}` | POST | Forzar resolución de un provider |
| `/api/domains/health/{id}` | GET | Health check de un provider |

---

## Callbacks de Cambio de Dominio

**Archivo:** `app/services/domain_resolver.py:90-97`

```python
def on_domain_change(self, callback: Callable[[str, str], Awaitable[None]]):
    self._callbacks.append(callback)
```

Los callbacks se notifican cuando un dominio cambia. Reciben `(provider_id, new_domain)`. Actualmente no hay callbacks registrados (posible mejora: actualizar `self.base_url` en providers automáticamente).

---

## Cómo Añadir Resolución para un Nuevo Provider

1. Añadir `DomainConfig` en `app/server.py:lifespan()`:
```python
if settings.NUEVO_ENABLED:
    resolver.register_provider(DomainConfig(
        provider_id="nuevo",
        default_domain=settings.NUEVO_DOMAIN,
        privtree_path="@nuevo",          # Si existe en privtr.ee
        telegram_channel="NuevoCanal",   # Si tiene canal de Telegram
        known_domain_pattern=r"nuevo\.\w+",
    ))
```

2. El provider debe aceptar un `domain_resolver` opcional en su constructor y usarlo para obtener el dominio actual.

---

## Trampas / Problemas Conocidos

1. **Si todas las estrategias fallan, se mantiene el último dominio conocido** — Puede estar muerto. No hay mecanismo de alerta.

2. **La validación usa HTTP HEAD** — Algunos sitios bloquean HEAD y solo responden a GET. En ese caso, la validación falla incluso si el dominio es correcto.

3. **Telegram puede cambiar su estructura HTML** — Los selectores CSS (`tgme_widget_message_wrap`) dependen de la estructura actual de la vista web de Telegram. Si Telegram la cambia, esta estrategia fallará.

4. **No todos los providers tienen privtree/telegram** — Muchos providers solo dependen del `default_domain` + `HealthCheckStrategy`.

---

## Archivos Relevantes

| Archivo | Rol |
|---------|-----|
| `app/services/domain_resolver.py` | DomainResolver principal |
| `app/services/domain_strategies.py` | Estrategias de resolución |
| `app/api/domains.py` | API REST de dominios |
| `app/server.py` | Registro de DomainConfig en startup |
| `data/domains.json` | Persistencia de dominios resueltos |
| `config.py` | Settings: DOMAIN_CHECK_INTERVAL, DOMAIN_VALIDATION_TIMEOUT |
