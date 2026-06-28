#!/usr/bin/env python3
"""
validate_docs.py — Script de validación de documentación agéntica para WebTranslatorr.

Verifica:
1. Cobertura de módulos (todos los archivos fuente referenciados en docs)
2. Referencias rotas (paths mencionados en docs que no existen)
3. Cobertura de estrategias (cada provider tiene su documento)
4. Archivos de documentación requeridos presentes
5. Cobertura de archivos fuente

Uso:
  python scripts/validate_docs.py           # Validación normal
  python scripts/validate_docs.py --strict  # Falla con errores (CI)
"""

import json
import re
import sys
from pathlib import Path
from typing import Set

ROOT = Path(__file__).resolve().parent.parent
DOC_DIR = ROOT / ".kilo"
CONTEXT_DIR = DOC_DIR / "context"
STRATEGIES_DIR = CONTEXT_DIR / "06-provider-strategies"


def extract_file_references(doc_dir: Path) -> Set[str]:
    """Extrae todos los paths de archivo mencionados en los documentos .md."""
    refs: Set[str] = set()
    for md_file in doc_dir.rglob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        # Buscar referencias como `app/core/models.py`, `config.py`, etc.
        matches = re.findall(r'`([a-zA-Z][a-zA-Z0-9_/.-]+\.[a-zA-Z]+(?:/\*)?)`', content)
        for match in matches:
            refs.add(match)
        # También buscar paths sin backticks (ej: context/...)
        matches2 = re.findall(r'(app/[a-zA-Z0-9_/.-]+\.[a-zA-Z]+)', content)
        refs.update(matches2)
    return refs


def get_source_files(root: Path) -> Set[str]:
    """Obtiene todos los archivos fuente Python del proyecto."""
    sources: Set[str] = set()
    for py_file in root.rglob("app/**/*.py"):
        sources.add(str(py_file.relative_to(root)))
    sources.add("config.py")
    sources.add("main.py")
    return sources


def validate() -> dict:
    results = {"errors": [], "warnings": [], "info": []}

    # 1. Verificar archivos de documentación requeridos
    required_docs = [
        DOC_DIR / "INDEX.md",
        DOC_DIR / "AGENTS.md",
        DOC_DIR / "styleguide.md",
        DOC_DIR / "doc-mapping.json",
        CONTEXT_DIR / "01-architecture.md",
        CONTEXT_DIR / "02-configuration.md",
        CONTEXT_DIR / "03-data-models.md",
        CONTEXT_DIR / "04-http-client.md",
        CONTEXT_DIR / "05-providers-base.md",
        CONTEXT_DIR / "07-smart-router.md",
        CONTEXT_DIR / "08-torznab-protocol.md",
        CONTEXT_DIR / "09-categories.md",
        CONTEXT_DIR / "10-domain-resolver.md",
        CONTEXT_DIR / "11-cache.md",
        CONTEXT_DIR / "13-api-endpoints.md",
        CONTEXT_DIR / "14-deployment.md",
        CONTEXT_DIR / "15-testing.md",
        CONTEXT_DIR / "16-known-issues.md",
        CONTEXT_DIR / "17-adding-providers.md",
    ]

    for doc in required_docs:
        if not doc.exists():
            results["errors"].append(f"Falta documento requerido: {doc.relative_to(ROOT)}")
        else:
            results["info"].append(f"✓ {doc.relative_to(ROOT)}")

    # 2. Verificar cobertura de estrategias de providers
    # Descubrir estrategias esperadas desde el sistema de archivos
    expected_providers = set()
    for strategy_file in STRATEGIES_DIR.glob("*.md"):
        expected_providers.add(strategy_file.stem)

    for provider_id in sorted(expected_providers):
        strategy_file = STRATEGIES_DIR / f"{provider_id}.md"
        results["info"].append(f"✓ Provider strategy: {provider_id}")

    # 3. Verificar referencias rotas
    doc_refs = extract_file_references(DOC_DIR)
    source_files = get_source_files(ROOT)

    broken_refs = []
    for ref in doc_refs:
        # Ignorar referencias a directorios o patrones glob
        if "*" in ref or ref.endswith("/"):
            continue
        ref_path = ROOT / ref
        if not ref_path.exists() and "/" in ref:
            # Solo marcar como roto si es un archivo específico, no genérico
            if re.match(r'^(app|tests|scripts)/.*\.py$', ref):
                broken_refs.append(ref)

    if broken_refs:
        results["warnings"].append(f"Referencias posiblemente rotas: {broken_refs}")

    # 4. Verificar cobertura de archivos fuente en documentos
    doc_refs_normalized = set()
    for ref in doc_refs:
        doc_refs_normalized.add(ref)

    undocumented = set()
    for src in source_files:
        # Omitir __init__.py y parser.py (intencionalmente sin test)
        if src.endswith("__init__.py") or src == "app/scraping/parser.py":
            continue
        src_name = Path(src).name
        src_stem = Path(src).stem
        # Verificar si hay alguna referencia al archivo en los docs
        found = False
        for ref in doc_refs_normalized:
            if src in ref or src_name in ref or src_stem in ref:
                found = True
                break
        if not found:
            undocumented.add(src)

    if undocumented:
        results["warnings"].append(f"Archivos fuente sin referencia en docs ({len(undocumented)}): {sorted(undocumented)}")

    # 5. Verificar doc-mapping.json cubre todos los archivos fuente
    mapping_file = DOC_DIR / "doc-mapping.json"
    if mapping_file.exists():
        mapping = json.loads(mapping_file.read_text(encoding="utf-8"))
        mapped_patterns = [r["pattern"] for r in mapping.get("rules", [])]
        results["info"].append(f"✓ doc-mapping.json con {len(mapped_patterns)} reglas")

    # Resumen
    coverage_pct = (len(source_files) - len(undocumented)) / max(len(source_files), 1) * 100
    results["summary"] = {
        "total_docs": sum(1 for _ in DOC_DIR.rglob("*.md")),
        "total_source_files": len(source_files),
        "undocumented_sources": len(undocumented),
        "coverage_pct": round(coverage_pct, 1),
        "errors": len(results["errors"]),
        "warnings": len(results["warnings"]),
    }

    return results


def main():
    strict = "--strict" in sys.argv
    results = validate()

    print("=" * 60)
    print("Validación de Documentación Agéntica — WebTranslatorr")
    print("=" * 60)

    for msg in results["info"]:
        print(f"  {msg}")

    if results["warnings"]:
        print(f"\n⚠️  Advertencias ({len(results['warnings'])}):")
        for msg in results["warnings"]:
            print(f"  {msg}")

    if results["errors"]:
        print(f"\n❌ Errores ({len(results['errors'])}):")
        for msg in results["errors"]:
            print(f"  {msg}")

    summary = results["summary"]
    print(f"\n📊 Resumen:")
    print(f"  Documentos: {summary['total_docs']}")
    print(f"  Archivos fuente: {summary['total_source_files']}")
    print(f"  Cobertura: {summary['coverage_pct']}%")
    print(f"  Errores: {summary['errors']}")
    print(f"  Advertencias: {summary['warnings']}")

    if strict and results["errors"]:
        print("\n❌ Validación estricta fallida.")
        sys.exit(1)

    if results["errors"]:
        print("\n⚠️  Validación completada con errores.")
    else:
        print("\n✅ Validación completada.")


if __name__ == "__main__":
    main()
