# Registro de Errores — planificador

> Catálogo de errores de planificación detectados (pasos omitidos, riesgos no identificados, estimaciones incorrectas, dependencias no detectadas).
> Consultar ANTES de cada nueva planificación (protocolo pre-acción §3.5).

## Formato de Entrada

```markdown
## [ERROR-XXX] Título descriptivo

- **Fecha detección**: YYYY-MM-DD
- **Detectado por**: {planificador | orquestador | auditor | agente especialista}
- **Severidad**: crítica | alta | media | baja
- **Plan afectado**: PLAN-YYYYMMDD-NNN
- **Síntomas**: qué falló en la planificación (paso omitido, riesgo no detectado, orden incorrecto, agente equivocado)
- **Causa raíz**: por qué ocurrió el error de planificación
- **Solución**: cómo se corrigió el plan o la ejecución
- **Verificado por**: {agente auditor o tests}
- **Lección**: aprendizaje extraído para prevenir recurrencia en futuras planificaciones
- **Estado**: detectado | en_progreso | resuelto | verificado | reabierto
```

## Errores

_Sin entradas aún — se poblará durante la operación normal._
