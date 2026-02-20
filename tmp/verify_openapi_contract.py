#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run a demo API app and verify it matches a given OpenAPI / Swagger spec.

This script is designed for the SAFRS demo apps in `safrs/tmp/` but works for
any app that:
  - can be started as: `python app.py <host> <port>`
  - exposes a readiness endpoint at `/health`

It auto-detects the API base path from the spec:
  - Swagger / OpenAPI 2.0: uses `basePath`
  - OpenAPI 3.x: uses the first server URL path if it is relative (e.g. "/api")

Schemathesis v4 uses `--url` (NOT `--base-url`).

Important: The app process can get *very* chatty under fuzzing (stack traces,
validation errors, etc.). If you start it with stdout=PIPE and don't drain that
pipe continuously, the OS pipe buffer will fill up and the app will block on
logging. That looks like "random" read timeouts / connection failures.

This verifier therefore drains the app's stdout in a background thread and keeps
only a small ring buffer of the last N lines for reporting at the end.

Usage examples:
  python verify_openapi_contract.py --app fastapi_app.py --spec fastapi.openapi.json
  python verify_openapi_contract.py --app flask_app.py  --spec flask.swagger.json

Auth:
  export API_AUTHORIZATION='Bearer ...'  # or pass --auth

Exit codes:
  0  success (all checks passed)
  1  contract mismatch / test failure
  2  setup / runtime error
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque
from pathlib import Path
from urllib.parse import urlparse
from typing import Any


def _find_free_port(host: str) -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, 0))
        return int(s.getsockname()[1])
    finally:
        s.close()


def _wait_http_ok(url: str, timeout_s: float) -> None:
    try:
        import requests
    except Exception as e:
        raise RuntimeError("Missing dependency 'requests' (pip install requests)") from e

    deadline = time.time() + timeout_s
    last_err = None
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=0.5)
            if r.status_code < 500:
                return
        except Exception as e:
            last_err = e
        time.sleep(0.1)

    msg = "Service didn't become ready: %s" % url
    if last_err is not None:
        msg += " (last error: %r)" % (last_err,)
    raise RuntimeError(msg)


def _load_spec(spec_path: Path) -> dict:
    with spec_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _extract_base_path_from_spec(spec: dict) -> str:
    """Return an API base path prefix (e.g. '/api') if present, else ''."""

    # Swagger / OpenAPI 2.0
    if str(spec.get("swagger", "")) == "2.0":
        base_path = spec.get("basePath", "")
        if isinstance(base_path, str):
            return base_path
        return ""

    # OpenAPI 3.x
    if "openapi" in spec:
        servers = spec.get("servers")
        if isinstance(servers, list) and servers:
            first = servers[0]
            if isinstance(first, dict):
                url = first.get("url", "")
                if isinstance(url, str) and url:
                    # Relative server URL like "/api" is common in FastAPI
                    if url.startswith("/"):
                        return url
                    # Absolute server URL like "http://localhost:8000/api"
                    if url.startswith("http://") or url.startswith("https://"):
                        try:
                            parsed = urlparse(url)
                            return parsed.path or ""
                        except Exception:
                            return ""
        return ""

    return ""


def _join_base_url(base_url: str, base_path: str) -> str:
    """Join 'http://host:port' + '/api' -> 'http://host:port/api'."""

    if not base_path:
        return base_url

    # Normalize
    if base_path == "/":
        return base_url

    return base_url.rstrip("/") + "/" + base_path.lstrip("/")


def _coerce_seed_values(values: list[Any], schema_type: str) -> list[Any]:
    if schema_type == "integer":
        result: list[Any] = []
        for value in values:
            try:
                result.append(int(value))
            except Exception:
                continue
        return result
    return [str(value) for value in values]


def _seed_key_for_field(field_name: str) -> str:
    parts = [part for part in str(field_name).split("_") if part]
    return "".join(part[:1].upper() + part[1:] for part in parts)


def _patch_schema_with_seed(schema: dict[str, Any], seed: dict[str, Any]) -> None:
    schema_type = str(schema.get("type", ""))
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        items = schema.get("items")
        if isinstance(items, dict):
            _patch_schema_with_seed(items, seed)
        return

    relationship_ids: list[Any] = []
    for key in ("PersonId", "FriendId"):
        if key in seed:
            relationship_ids.append(seed[key])

    for field_name, field_schema in properties.items():
        if not isinstance(field_schema, dict):
            continue
        _patch_schema_with_seed(field_schema, seed)

        field_type = str(field_schema.get("type", "string"))
        enum_values: list[Any] = []
        seed_key = str(field_name)
        if seed_key in seed:
            enum_values = [seed[seed_key]]
        else:
            camel_key = _seed_key_for_field(str(field_name))
            if camel_key in seed:
                enum_values = [seed[camel_key]]
            elif str(field_name) == "id" and relationship_ids:
                enum_values = relationship_ids
            elif str(field_name).endswith("_id") and relationship_ids:
                enum_values = relationship_ids

        coerced_values = _coerce_seed_values(enum_values, field_type)
        if coerced_values:
            field_schema["enum"] = coerced_values
            field_schema.setdefault("default", coerced_values[0])


def _patch_spec_with_seed(spec: dict[str, Any], seed: dict[str, Any]) -> dict[str, Any]:
    patched = json.loads(json.dumps(spec))
    paths = patched.get("paths")
    if not isinstance(paths, dict):
        return patched

    for _path, operations in paths.items():
        if not isinstance(operations, dict):
            continue
        for _method, operation in operations.items():
            if not isinstance(operation, dict):
                continue
            parameters = operation.get("parameters")
            if not isinstance(parameters, list):
                continue
            for parameter in parameters:
                if not isinstance(parameter, dict):
                    continue
                if str(parameter.get("in")) == "path":
                    name = str(parameter.get("name", ""))
                    if name in seed:
                        value = seed[name]
                        parameter["enum"] = [value]
                        parameter.setdefault("default", value)
                    continue
                if str(parameter.get("in")) == "body":
                    schema = parameter.get("schema")
                    if isinstance(schema, dict):
                        _patch_schema_with_seed(schema, seed)
    return patched


def _fetch_seed_payload(base_url: str, request_timeout_s: float) -> dict[str, Any]:
    try:
        import requests
    except Exception:
        return {}

    seed_url = base_url.rstrip("/") + "/seed"
    timeout_s = max(0.5, min(float(request_timeout_s), 5.0))
    try:
        response = requests.get(seed_url, timeout=timeout_s)
        if response.status_code >= 400:
            return {}
        payload = response.json()
        if isinstance(payload, dict):
            return payload
    except Exception:
        return {}
    return {}


def _prepare_spec_for_run(spec_path: Path, base_url: str, request_timeout_s: float) -> tuple[Path, bool]:
    seed = _fetch_seed_payload(base_url, request_timeout_s)
    if not seed:
        return spec_path, False

    spec = _load_spec(spec_path)
    patched = _patch_spec_with_seed(spec, seed)
    fd, tmp_path = tempfile.mkstemp(prefix="safrs_contract_spec_", suffix=".json")
    os.close(fd)
    patched_path = Path(tmp_path)
    patched_path.write_text(json.dumps(patched), encoding="utf-8")
    return patched_path, True


def _start_app_log_drain(
    proc: subprocess.Popen,
    ring: deque,
    tee: bool,
    log_fp: object,
) -> threading.Thread:
    """Continuously drain proc.stdout so the child can't block on log writes."""

    def _reader() -> None:
        if proc.stdout is None:
            return
        try:
            for raw in proc.stdout:
                # `raw` includes the trailing newline.
                line = raw.rstrip("\n")
                ring.append(line)
                if log_fp is not None:
                    try:
                        log_fp.write(raw)
                    except Exception:
                        # Don't let log file I/O kill the verifier.
                        pass
                if tee:
                    try:
                        sys.stdout.write(raw)
                        sys.stdout.flush()
                    except Exception:
                        pass
        finally:
            try:
                if log_fp is not None:
                    log_fp.flush()
            except Exception:
                pass

    t = threading.Thread(target=_reader, name="app-log-drain", daemon=True)
    t.start()
    return t


def _run_contract_tests(
    spec_path: Path,
    effective_url: str,
    max_examples: int,
    request_timeout_s: float,
    phases: str,
    auth_header: str,
    content_type: str,
) -> int:
    """Run schemathesis against the effective_url using a local spec file."""

    st = shutil.which("schemathesis")
    base_cmd = [st] if st else [sys.executable, "-m", "schemathesis"]

    cmd = (
        base_cmd
        + [
            "run",
            str(spec_path),
            "--url",
            effective_url,
            "--checks",
            "not_a_server_error,status_code_conformance,content_type_conformance,response_headers_conformance,response_schema_conformance",
            "--phases",
            phases,
            "--max-examples",
            str(max_examples),
            "--request-timeout",
            str(request_timeout_s),
            "--header",
            "Accept: application/vnd.api+json",
            "--header",
            "Content-Type: " + str(content_type),
        ]
    )

    if auth_header:
        cmd.extend(["--header", "Authorization: " + auth_header])

    print("[+] Running:")
    print("    " + " ".join(cmd))
    return subprocess.call(cmd)


def main() -> int:
    here = Path(__file__).resolve().parent

    ap = argparse.ArgumentParser()
    ap.add_argument("--app", required=True, help="Path to app entrypoint (python file)")
    ap.add_argument("--spec", required=True, help="Path to OpenAPI / Swagger JSON")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=0, help="0 means auto-select free port")
    ap.add_argument("--startup-timeout", type=float, default=15.0)
    ap.add_argument("--max-examples", type=int, default=25)
    ap.add_argument("--request-timeout", type=float, default=10.0)
    ap.add_argument(
        "--phases",
        default="examples,fuzzing",
        help="Schemathesis phases (e.g. 'examples,fuzzing' or add 'stateful')",
    )
    ap.add_argument(
        "--auth",
        default=os.environ.get("API_AUTHORIZATION", ""),
        help="Authorization header value (e.g. 'Bearer ...'). Can also be set via API_AUTHORIZATION env var.",
    )
    ap.add_argument(
        "--force-base-path",
        default="",
        help="Override the base path from the spec (example: '/api'). Useful if your spec is wrong.",
    )
    ap.add_argument(
        "--content-type",
        default="application/vnd.api+json",
        help="Content-Type header to send on all requests (default: JSON:API media type).",
    )
    ap.add_argument(
        "--app-log-lines",
        type=int,
        default=200,
        help="How many app log lines to keep and print at the end.",
    )
    ap.add_argument(
        "--tee-app-logs",
        action="store_true",
        help="Stream app logs to stdout while tests run (can be very noisy).",
    )
    ap.add_argument(
        "--app-log-file",
        default="",
        help="Optional file path to write the full app logs.",
    )
    args = ap.parse_args()

    app_path = Path(args.app).resolve()
    spec_path = Path(args.spec).resolve()

    if not app_path.exists():
        print("[-] App file not found: %s" % app_path, file=sys.stderr)
        return 2
    if not spec_path.exists():
        print("[-] Spec file not found: %s" % spec_path, file=sys.stderr)
        return 2

    host = args.host
    port = int(args.port) if int(args.port) != 0 else _find_free_port(host)

    try:
        spec = _load_spec(spec_path)
    except Exception as e:
        print("[-] Failed to load spec JSON: %s" % (e,), file=sys.stderr)
        return 2

    base_path = args.force_base_path.strip() or _extract_base_path_from_spec(spec)
    base_url = "http://%s:%d" % (host, port)
    effective_url = _join_base_url(base_url, base_path)

    env = dict(os.environ)
    env.setdefault("PYTHONUNBUFFERED", "1")

    cmd = [sys.executable, str(app_path), host, str(port)]
    print("[+] Starting app:")
    print("    " + " ".join(cmd))
    print("[+] Spec base path:")
    print("    %s" % (base_path if base_path else "<empty>",))
    print("[+] Schemathesis URL:")
    print("    %s" % (effective_url,))

    # Ring buffer + optional logfile. Keep this outside of the try/finally so
    # we can always print a useful tail.
    ring = deque(maxlen=max(1, int(args.app_log_lines)))
    log_fp = None
    if args.app_log_file:
        try:
            log_fp = open(str(args.app_log_file), "w", encoding="utf-8", errors="replace")
            print("[+] App log file:")
            print("    %s" % str(args.app_log_file))
        except Exception as e:
            print("[-] Failed to open app log file: %s" % (e,), file=sys.stderr)
            return 2

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=env,
        cwd=str(here),
    )

    log_thread = _start_app_log_drain(proc, ring, bool(args.tee_app_logs), log_fp)

    runtime_spec_path = spec_path
    remove_runtime_spec = False
    try:
        _wait_http_ok("%s/health" % base_url, args.startup_timeout)
        runtime_spec_path, remove_runtime_spec = _prepare_spec_for_run(
            spec_path=spec_path,
            base_url=base_url,
            request_timeout_s=float(args.request_timeout),
        )
        rc = _run_contract_tests(
            spec_path=runtime_spec_path,
            effective_url=effective_url,
            max_examples=args.max_examples,
            request_timeout_s=float(args.request_timeout),
            phases=str(args.phases),
            auth_header=str(args.auth),
            content_type=str(args.content_type),
        )
        return 0 if rc == 0 else 1
    except KeyboardInterrupt:
        return 2
    except Exception as e:
        print("[-] Error: %s" % (e,), file=sys.stderr)
        return 2
    finally:
        try:
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)
                try:
                    proc.wait(timeout=5)
                except Exception:
                    proc.kill()
        finally:
            if remove_runtime_spec:
                try:
                    runtime_spec_path.unlink(missing_ok=True)
                except Exception:
                    pass
            # Give the log drain thread a moment to read the final lines.
            try:
                log_thread.join(timeout=2.0)
            except Exception:
                pass

            try:
                if log_fp is not None:
                    log_fp.flush()
                    log_fp.close()
            except Exception:
                pass

            if ring:
                print("\n[+] App output (tail):")
                for line in ring:
                    print(line)


if __name__ == "__main__":
    raise SystemExit(main())
