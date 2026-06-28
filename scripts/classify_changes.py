#!/usr/bin/env python3
"""
classify_changes.py — Clasifica cambios en archivos fuente para determinar
impacto en la documentación agéntica.

Uso:
  python scripts/classify_changes.py                          # Usa git diff HEAD~1
  python scripts/classify_changes.py --files a.py,b.py        # Archivos específicos
  python scripts/classify_changes.py --base main              # Rama base
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
MAPPING_FILE = ROOT / ".kilo" / "doc-mapping.json"


class ChangeSeverity:
    NEW_COMPONENT = "new_component"
    CONTRACT_CHANGE = "contract_change"
    API_CHANGE = "api_change"
    IMPLEMENTATION = "implementation"
    COSMETIC = "cosmetic"


def get_changed_files(base: str = "HEAD~1") -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", base],
        capture_output=True, text=True, cwd=ROOT
    )
    if result.returncode != 0:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--cached"],
            capture_output=True, text=True, cwd=ROOT
        )
    return [f.strip() for f in result.stdout.split("\n") if f.strip()]


def get_diff_content(file_path: str, base: str = "HEAD~1") -> str:
    result = subprocess.run(
        ["git", "diff", base, "--", file_path],
        capture_output=True, text=True, cwd=ROOT
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def load_mapping() -> dict:
    if MAPPING_FILE.exists():
        return json.loads(MAPPING_FILE.read_text(encoding="utf-8"))
    return {"rules": []}


def match_rule(file_path: str, rule: dict) -> bool:
    pattern = rule["pattern"]
    if "*" in pattern:
        regex = "^" + re.escape(pattern).replace(r"\*", ".*") + "$"
        if pattern.endswith("/*.py"):
            regex = "^" + re.escape(pattern).replace(r"\*\*", "__DOUBLE__").replace(r"\*", r"[^/]+").replace("__DOUBLE__", ".*") + "$"
        return bool(re.match(regex, file_path))
    return file_path == pattern


def classify_change(file_path: str, diff_content: str) -> tuple[str, str]:
    if not (ROOT / file_path).exists():
        return ChangeSeverity.COSMETIC, "File deleted"

    if diff_content:
        if "class " in diff_content and ("ABC" in diff_content or "abstractmethod" in diff_content or "@abstractmethod" in diff_content):
            return ChangeSeverity.CONTRACT_CHANGE, "Abstract class/interface modified"
        if "@router." in diff_content and ("def " in diff_content):
            return ChangeSeverity.API_CHANGE, "Endpoint added or modified"
        if "def " in diff_content and ("async def" in diff_content):
            return ChangeSeverity.IMPLEMENTATION, "Function/method modified"
        if "import " in diff_content:
            return ChangeSeverity.IMPLEMENTATION, "Import changes"
        lines_changed = len([l for l in diff_content.split("\n") if l.startswith("+") or l.startswith("-")])
        if lines_changed < 5:
            return ChangeSeverity.COSMETIC, f"Minor change ({lines_changed} lines)"

    if not (ROOT / file_path).exists():
        return ChangeSeverity.NEW_COMPONENT, "New file created"

    return ChangeSeverity.IMPLEMENTATION, "File modified"


def classify_changes(files: list[str], base: str = "HEAD~1") -> dict:
    mapping = load_mapping()
    results = {"changes": [], "affected_docs": set(), "severity": "low"}

    severity_order = {
        ChangeSeverity.COSMETIC: 0,
        ChangeSeverity.IMPLEMENTATION: 1,
        ChangeSeverity.API_CHANGE: 2,
        ChangeSeverity.CONTRACT_CHANGE: 3,
        ChangeSeverity.NEW_COMPONENT: 4,
    }

    max_severity = 0

    for file_path in files:
        if not file_path.endswith(('.py', '.yml', '.yaml', '.json', 'Dockerfile')):
            continue
        if file_path.startswith(('.kilo/', '.gemini/', 'docs/', '.plans/', 'plans/')):
            continue

        diff = get_diff_content(file_path, base)
        severity, reason = classify_change(file_path, diff)

        docs = []
        for rule in mapping.get("rules", []):
            if match_rule(file_path, rule) and rule.get("documents"):
                docs.extend(rule["documents"])

        results["changes"].append({
            "file": file_path,
            "severity": severity,
            "reason": reason,
            "affected_docs": list(set(docs)) if docs else None,
        })

        results["affected_docs"].update(docs if docs else [])
        max_severity = max(max_severity, severity_order.get(severity, 0))

    severity_labels = {0: "low", 1: "medium", 2: "high", 3: "critical", 4: "critical"}
    results["severity"] = severity_labels.get(max_severity, "low")
    results["affected_docs"] = sorted(results["affected_docs"])
    results["docs_update_required"] = max_severity > 0

    return results


def main():
    parser = argparse.ArgumentParser(description="Classify source changes for doc impact")
    parser.add_argument("--files", help="Comma-separated file list (bypasses git)")
    parser.add_argument("--base", default="HEAD~1", help="Git base ref for diff")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.files:
        files = [f.strip() for f in args.files.split(",") if f.strip()]
    else:
        files = get_changed_files(args.base)

    if not files:
        result = {"changes": [], "severity": "low", "docs_update_required": False,
                  "affected_docs": []}
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("No source file changes detected.")
        return

    results = classify_changes(files, args.base)

    if args.json:
        results["affected_docs"] = list(results["affected_docs"])
        print(json.dumps(results, indent=2))
    else:
        severity_emoji = {
            "low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"
        }
        print(f"{severity_emoji.get(results['severity'], '⚪')} Severity: {results['severity']}")
        print(f"   Docs update needed: {'Yes' if results['docs_update_required'] else 'No'}")
        print()
        for change in results["changes"]:
            print(f"  {change['file']} → {change['severity']} ({change['reason']})")
            if change["affected_docs"]:
                for doc in change["affected_docs"]:
                    print(f"    ↳ {doc}")
        if results["affected_docs"]:
            print(f"\n  All affected docs ({len(results['affected_docs'])}):")
            for doc in results["affected_docs"]:
                print(f"    - {doc}")


if __name__ == "__main__":
    main()
