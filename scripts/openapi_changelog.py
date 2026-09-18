#!/usr/bin/env python3
"""OpenAPI Changelog & Breaking Change Detector for TitanRAG.

Compares two OpenAPI 3.x specifications or the live FastAPI application
against a baseline specification to detect breaking changes and schema evolutions.

Exit codes:
- 0: Clean / No breaking changes detected (or baseline generated)
- 1: Breaking API contract violations detected in strict mode
"""

import argparse
import json
import os
import sys
from typing import Any


def extract_schema_fields(schema: dict[str, Any], components: dict[str, Any], depth: int = 0) -> set[str]:
    """Extract all property names from an OpenAPI schema, resolving $ref if present."""
    if depth > 5:
        return set()
    if "$ref" in schema:
        ref_path = schema["$ref"].split("/")
        if len(ref_path) >= 4 and ref_path[1] == "components" and ref_path[2] == "schemas":
            model_name = ref_path[3]
            schema = components.get(model_name, {})

    fields = set()
    props = schema.get("properties", {})
    for prop_name, prop_val in props.items():
        fields.add(prop_name)
        if isinstance(prop_val, dict) and "properties" in prop_val:
            nested = extract_schema_fields(prop_val, components, depth + 1)
            fields.update(f"{prop_name}.{n}" for n in nested)
    return fields


def compare_specs(
    old_spec: dict[str, Any],
    new_spec: dict[str, Any],
) -> tuple[list[str], list[str], list[str]]:
    """Compare two OpenAPI specs.

    Returns:
        Tuple of (breaking_changes, additions, modifications)
    """
    breaking: list[str] = []
    additions: list[str] = []
    modifications: list[str] = []

    old_paths: dict[str, Any] = old_spec.get("paths", {})
    new_paths: dict[str, Any] = new_spec.get("paths", {})

    old_components = old_spec.get("components", {}).get("schemas", {})
    new_components = new_spec.get("components", {}).get("schemas", {})

    http_methods = {"get", "post", "put", "delete", "patch", "options", "head"}

    # 1. Check for removed paths
    for path in old_paths:
        if path not in new_paths:
            breaking.append(f"Removed endpoint path: `{path}`")

    # 2. Check for added paths
    for path in new_paths:
        if path not in old_paths:
            additions.append(f"Added endpoint path: `{path}`")

    # 3. Check methods on overlapping paths
    for path in old_paths:
        if path not in new_paths:
            continue

        old_methods = {k.lower(): v for k, v in old_paths[path].items() if k.lower() in http_methods}
        new_methods = {k.lower(): v for k, v in new_paths[path].items() if k.lower() in http_methods}

        for m in old_methods:
            if m not in new_methods:
                breaking.append(f"Removed method `{m.upper()}` on `{path}`")

        for m in new_methods:
            if m not in old_methods:
                additions.append(f"Added method `{m.upper()}` on `{path}`")

        for m in old_methods:
            if m not in new_methods:
                continue

            old_op = old_methods[m]
            new_op = new_methods[m]

            # Compare parameters
            old_params = {
                f"{p.get('in')}:{p.get('name')}": p.get("required", False)
                for p in old_op.get("parameters", [])
                if isinstance(p, dict) and "name" in p
            }
            new_params = {
                f"{p.get('in')}:{p.get('name')}": p.get("required", False)
                for p in new_op.get("parameters", [])
                if isinstance(p, dict) and "name" in p
            }

            # Check if any previously optional/absent parameter is now required
            for param_key, is_required in new_params.items():
                if is_required and not old_params.get(param_key, False):
                    breaking.append(f"New required parameter `{param_key}` added to `{m.upper()} {path}`")

            # Check removed response status codes
            old_responses = old_op.get("responses", {})
            new_responses = new_op.get("responses", {})
            for code in old_responses:
                if code.startswith("2") and code not in new_responses:
                    breaking.append(f"Success response code `{code}` removed from `{m.upper()} {path}`")

    # 4. Check schema models for removed properties
    for model_name, old_model in old_components.items():
        if model_name in new_components:
            old_fields = extract_schema_fields(old_model, old_components)
            new_fields = extract_schema_fields(new_components[model_name], new_components)
            removed = old_fields - new_fields
            added = new_fields - old_fields
            for field in removed:
                breaking.append(f"Removed property `{field}` in schema `{model_name}`")
            for field in added:
                modifications.append(f"Added property `{field}` to schema `{model_name}`")
        else:
            modifications.append(f"Removed component schema `{model_name}`")

    return breaking, additions, modifications


def main() -> int:
    parser = argparse.ArgumentParser(description="TitanRAG OpenAPI Changelog & Breaking Change Detector")
    parser.add_argument("--baseline", type=str, default="docs/openapi_baseline.json", help="Path to baseline OpenAPI JSON")
    parser.add_argument("--current", type=str, default=None, help="Path to current OpenAPI JSON (defaults to live app)")
    parser.add_argument("--save-baseline", action="store_true", help="Save live app OpenAPI schema as new baseline")
    parser.add_argument("--strict", action="store_true", default=True, help="Exit with code 1 if breaking changes found")
    parser.add_argument("--markdown", type=str, default=None, help="Optional output markdown file for changelog")

    args = parser.parse_args()

    # Load current spec
    if args.current and os.path.exists(args.current):
        with open(args.current, encoding="utf-8") as f:
            current_spec = json.load(f)
    else:
        from titan_backend.main import app
        current_spec = app.openapi()

    # Save baseline action
    if args.save_baseline:
        os.makedirs(os.path.dirname(os.path.abspath(args.baseline)), exist_ok=True)
        with open(args.baseline, "w", encoding="utf-8") as f:
            json.dump(current_spec, f, indent=2)
        print(f"✅ Saved baseline OpenAPI specification to `{args.baseline}` ({len(current_spec.get('paths', {}))} paths)")
        return 0

    if not os.path.exists(args.baseline):
        print(f"⚠️ Baseline file `{args.baseline}` does not exist yet. Initializing with current specification...")
        os.makedirs(os.path.dirname(os.path.abspath(args.baseline)), exist_ok=True)
        with open(args.baseline, "w", encoding="utf-8") as f:
            json.dump(current_spec, f, indent=2)
        print(f"✅ Initialized baseline at `{args.baseline}`. Re-run without changes to verify.")
        return 0

    with open(args.baseline, encoding="utf-8") as f:
        baseline_spec = json.load(f)

    breaking, additions, modifications = compare_specs(baseline_spec, current_spec)

    print("\n=======================================================")
    print("        TITANRAG OPENAPI SPECIFICATION AUDIT           ")
    print("=======================================================\n")
    print(f"Baseline: {args.baseline} (OpenAPI {baseline_spec.get('openapi')})")
    print(f"Current:  {len(current_spec.get('paths', {}))} paths, {len(current_spec.get('components', {}).get('schemas', {}))} schemas\n")

    if breaking:
        print(f"🚨 BREAKING CHANGES DETECTED ({len(breaking)}):")
        for b in breaking:
            print(f"  ❌ {b}")
        print()
    else:
        print("✅ No breaking changes detected!\n")

    if additions:
        print(f"✨ ADDITIONS & NEW FEATURES ({len(additions)}):")
        for a in additions:
            print(f"  ➕ {a}")
        print()

    if modifications:
        print(f"🔄 SCHEMA MODIFICATIONS ({len(modifications)}):")
        for m in modifications[:15]:
            print(f"  ℹ️  {m}")
        if len(modifications) > 15:
            print(f"  ... and {len(modifications) - 15} more field modifications.")
        print()

    if args.markdown:
        os.makedirs(os.path.dirname(os.path.abspath(args.markdown)), exist_ok=True)
        with open(args.markdown, "w", encoding="utf-8") as f:
            f.write("# OpenAPI Contract Changelog\n\n")
            if breaking:
                f.write("## 🚨 Breaking Changes\n\n")
                for b in breaking:
                    f.write(f"- ❌ {b}\n")
                f.write("\n")
            else:
                f.write("## ✅ Contract Status\n\nNo breaking changes detected.\n\n")

            if additions:
                f.write("## ✨ Additions\n\n")
                for a in additions:
                    f.write(f"- ➕ {a}\n")
                f.write("\n")

            if modifications:
                f.write("## 🔄 Schema Evolutions\n\n")
                for m in modifications:
                    f.write(f"- ℹ️ {m}\n")
                f.write("\n")
        print(f"📝 Changelog written to `{args.markdown}`")

    if breaking and args.strict:
        print("❌ Audit failed: breaking changes are not permitted without version increment.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
