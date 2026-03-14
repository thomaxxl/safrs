from __future__ import annotations

import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from safrs_verify import verify_openapi_contract as _impl

sys.modules[__name__] = _impl
