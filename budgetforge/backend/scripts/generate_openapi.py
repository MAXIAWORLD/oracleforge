#!/usr/bin/env python3
"""
Generate OpenAPI specification and export to JSON/YAML files.
"""

import json
import yaml
from pathlib import Path

import sys

sys.path.insert(0, ".")

from main import app


def generate_openapi_spec():
    """Generate OpenAPI specification and save to files."""

    # Generate the OpenAPI spec
    openapi_spec = app.openapi()

    # Create docs directory if it doesn't exist
    docs_dir = Path("../docs")
    docs_dir.mkdir(exist_ok=True)

    # Save as JSON
    json_path = docs_dir / "openapi.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(openapi_spec, f, indent=2, ensure_ascii=False)

    # Save as YAML
    yaml_path = docs_dir / "openapi.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(openapi_spec, f, default_flow_style=False, allow_unicode=True)

    print("OpenAPI spec generated successfully!")
    print(f"Endpoints: {len(openapi_spec['paths'])}")
    print(f"JSON: {json_path}")
    print(f"YAML: {yaml_path}")

    return openapi_spec


if __name__ == "__main__":
    generate_openapi_spec()
