#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

TMP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TMP_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from safrs.fastapi.openapi import diff_openapi_documents, format_report

DEFAULT_FLASK_SPEC = TMP_DIR / "flask.swagger.json"
DEFAULT_FASTAPI_SPEC = TMP_DIR / "fastapi.openapi.json"


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Diff Flask Swagger2 vs FastAPI OpenAPI specs")
    parser.add_argument("--flask-spec", type=Path, default=DEFAULT_FLASK_SPEC)
    parser.add_argument("--fastapi-spec", type=Path, default=DEFAULT_FASTAPI_SPEC)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON report")
    parser.add_argument("--top", type=int, default=10, help="Maximum number of differences to print")
    args = parser.parse_args()

    if not args.flask_spec.exists():
        raise FileNotFoundError(f"Flask spec not found: {args.flask_spec}")
    if not args.fastapi_spec.exists():
        raise FileNotFoundError(f"FastAPI spec not found: {args.fastapi_spec}")

    flask_spec = _load_json(args.flask_spec)
    fastapi_spec = _load_json(args.fastapi_spec)
    report = diff_openapi_documents(flask_spec, fastapi_spec)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    print(format_report(report, top_n=args.top))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
