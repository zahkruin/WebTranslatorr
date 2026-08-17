# Central Error Registry

> Registro unificado de todos los errores encontrados en el proyecto.
> Mantenido por: orquestador (consolidación), auditor (verificación).
> Consulta OBLIGATORIA antes de cualquier intervención (protocolo pre-acción §3.5).

## Formato de Entrada

| ID | Fecha | Agente | Módulo | Severidad | Descripción | Solución | Lección | Estado |
|----|-------|--------|--------|-----------|-------------|----------|---------|--------|

## Estados posibles
- `detectado` — Error identificado, no se ha empezado a trabajar
- `en_progreso` — Agente asignado está trabajando en la solución
- `resuelto` — Solución implementada, pendiente de verificación
- `verificado` — Solución verificada por el auditor o tests
- `reabierto` — Error reapareció después de ser marcado como resuelto

## Errores

| ID | Fecha | Agente | Módulo | Severidad | Descripción | Solución | Lección | Estado |
|----|-------|--------|--------|-----------|-------------|----------|---------|--------|
| E-001 | — | — | — | — | (Sin entradas aún — el registro se poblará durante la operación normal) | — | — | — |

---

> **Última actualización**: 2026-06-28 (inicialización del sistema de agentes)
