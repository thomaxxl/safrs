#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unified contract verifier.

This wrapper keeps the historical helper function names used by tests while
running the new shared harness from `safrs_verify`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

TMP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TMP_DIR.parent
WORKSPACE_ROOT = PROJECT_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from safrs_verify.config import ContractTarget
from safrs_verify.contract import ContractRunOptions, run_contract_target
from safrs_verify.db import BackendUnavailable, resolve_db_backends
from safrs_verify.seed_patch import fetch_seed_payload, patch_spec_with_seed
from safrs_verify.spec import extract_base_path_from_spec, join_base_url


def _extract_base_path_from_spec(spec: dict[str, Any]) -> str:
    return extract_base_path_from_spec(spec)


def _join_base_url(base_url: str, base_path: str) -> str:
    return join_base_url(base_url, base_path)


def _patch_spec_with_seed(spec: dict[str, Any], seed: dict[str, Any]) -> dict[str, Any]:
    return patch_spec_with_seed(spec, seed)


def _fetch_seed_payload(base_url: str, request_timeout_s: float) -> dict[str, Any]:
    return fetch_seed_payload(base_url, request_timeout_s, seed_path="/seed")


def _prepare_spec_for_run(spec_path: Path, base_url: str, request_timeout_s: float) -> tuple[Path, bool]:
    seed = _fetch_seed_payload(base_url, request_timeout_s)
    if not seed:
        return spec_path, False

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    patched = _patch_spec_with_seed(spec, seed)
    fd, tmp_path = tempfile.mkstemp(prefix="safrs_contract_spec_", suffix=".json")
    os.close(fd)
    prepared = Path(tmp_path)
    prepared.write_text(json.dumps(patched), encoding="utf-8")
    return prepared, True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", required=True, help="Path to app entrypoint (python file)")
    parser.add_argument("--spec", default="", help="Deprecated; ignored (spec is discovered at runtime)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0, help="0 means auto-select free port")
    parser.add_argument("--startup-timeout", type=float, default=15.0)
    parser.add_argument("--max-examples", type=int, default=25)
    parser.add_argument("--request-timeout", type=float, default=10.0)
    parser.add_argument("--phases", default="examples,fuzzing")
    parser.add_argument("--auth", default=os.environ.get("API_AUTHORIZATION", ""))
    parser.add_argument("--force-base-path", default="")
    parser.add_argument("--content-type", default="application/vnd.api+json")
    parser.add_argument("--app-log-lines", type=int, default=200)
    parser.add_argument("--tee-app-logs", action="store_true")
    parser.add_argument("--app-log-file", default="")
    parser.add_argument("--db", default="sqlite", choices=("sqlite",), help="DB backend name")
    parser.add_argument(
        "--spec-candidate",
        action="append",
        default=[],
        help="Candidate spec endpoint (repeatable). Defaults to /openapi.json then /api/swagger.json",
    )
    args = parser.parse_args()

    app_path = Path(args.app).resolve()
    if not app_path.exists():
        print(f"[-] App file not found: {app_path}", file=sys.stderr)
        return 2

    if args.spec:
        print("[!] --spec is deprecated and ignored; runtime discovery is used.")

    try:
        backend = resolve_db_backends(args.db)[0]
    except Exception as exc:
        print(f"[-] Invalid db backend '{args.db}': {exc}", file=sys.stderr)
        return 2

    spec_candidates = tuple(args.spec_candidate) if args.spec_candidate else ("/openapi.json", "/api/swagger.json")
    target = ContractTarget(
        name=app_path.stem,
        app_path=app_path,
        spec_candidates=spec_candidates,
        health_path="/health",
        seed_path="/seed",
    )

    app_log_file = Path(args.app_log_file).resolve() if args.app_log_file else None
    options = ContractRunOptions(
        host=str(args.host),
        port=int(args.port),
        startup_timeout_s=float(args.startup_timeout),
        request_timeout_s=float(args.request_timeout),
        max_examples=int(args.max_examples),
        phases=str(args.phases),
        auth_header=str(args.auth),
        content_type=str(args.content_type),
        app_log_lines=int(args.app_log_lines),
        tee_app_logs=bool(args.tee_app_logs),
        app_log_file=app_log_file,
        force_base_path=str(args.force_base_path),
    )

    try:
        result = run_contract_target(target, backend, options=options)
    except BackendUnavailable as exc:
        print(f"[-] Backend unavailable: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"[-] Error: {exc}", file=sys.stderr)
        return 2

    print("[+] Spec endpoint:")
    print(f"    {result.spec_endpoint}")
    print("[+] Base URL:")
    print(f"    {result.base_url}")
    print("[+] Effective URL:")
    print(f"    {result.effective_url}")
    print("[+] Running:")
    print("    " + " ".join(result.command))

    if result.returncode != 0:
        print(f"[+] Runtime spec artifact: {result.runtime_spec_path}")
        if result.app_log_tail:
            print("\n[+] App output (tail):")
            for line in result.app_log_tail:
                print(line)
        print("\n[-] Schemathesis output:")
        print(result.schemathesis_output)
        return 1

    if result.app_log_tail:
        print("\n[+] App output (tail):")
        for line in result.app_log_tail:
            print(line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
