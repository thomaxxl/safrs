from __future__ import annotations

import importlib.metadata
import os

from fastapi import FastAPI
from safrs import SAFRSAPI
from safrs.fastapi.api import RelationshipItemMode, SafrsFastAPI


def main() -> None:
    expected_version = os.environ.get("SAFRS_EXPECTED_VERSION", "3.2.0")
    installed_version = importlib.metadata.version("safrs")
    if installed_version != expected_version:
        raise SystemExit(
            f"Installed safrs version mismatch: expected {expected_version}, got {installed_version}"
        )

    import safrs

    if safrs.__version__ != expected_version:
        raise SystemExit(f"Runtime safrs.__version__ mismatch: expected {expected_version}, got {safrs.__version__}")

    # Smoke import checks for both Flask and FastAPI adapters.
    if SAFRSAPI.__name__ != "SAFRSAPI":
        raise SystemExit("Unable to import SAFRSAPI from safrs")

    app = FastAPI(title="SAFRS Release Smoke Test")
    adapter = SafrsFastAPI(app, prefix="/api", relationship_item_mode=RelationshipItemMode.HIDDEN)
    if adapter is None:
        raise SystemExit("Unable to initialize SafrsFastAPI")

    print(f"OK: installed safrs {installed_version}")
    print("OK: FastAPI adapter import and initialization succeeded")


if __name__ == "__main__":
    main()
