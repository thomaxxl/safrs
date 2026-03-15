from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[2]
_LOCAL_SAFRS_PATH = _ROOT / "safrs"
if str(_LOCAL_SAFRS_PATH) not in sys.path:
    sys.path.insert(0, str(_LOCAL_SAFRS_PATH))

_APPS_DIR = Path(__file__).resolve().parents[2] / "verifier" / "apps"
_MODULE_PATH = _APPS_DIR / "models.py"
_MODULE_NAME = "_safrs_tmp_verifier_models"


def _load_models_module() -> object:
    module = sys.modules.get(_MODULE_NAME)
    if module is not None:
        return module

    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _MODULE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load verifier models from {_MODULE_PATH}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


_impl = _load_models_module()

for _name in dir(_impl):
    if _name.startswith("__"):
        continue
    globals()[_name] = getattr(_impl, _name)

__all__ = [name for name in globals() if not name.startswith("__")]
