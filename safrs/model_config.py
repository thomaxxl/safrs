"""Model-level SAFRS configuration.

This module contains the configuration object used by :class:`~safrs.base.SAFRSBase`.

Phase 1 refactor goal:
- Provide a single configuration object instead of multiple ``_s_*`` class attributes.
- Keep backwards compatibility by allowing legacy ``_s_*`` overrides to be resolved
  into this configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class SAFRSModelConfig:
    """Configuration for a single SAFRS model class.

    All fields are intentionally immutable to avoid cache coherency issues.
    """

    expose: bool = True
    upsert: bool = True
    allow_add_rels: bool = True
    pk_delimiter: str = "_"
    url_root: Optional[str] = None
    # Optional knob: referenced in SAFRSBase._s_query
    stateless: bool = False

    def with_overrides(self, overrides: Mapping[str, Any]) -> "SAFRSModelConfig":
        """Return a new config where known fields are replaced by ``overrides``."""
        valid = {k: v for k, v in overrides.items() if k in self.__dataclass_fields__}
        if not valid:
            return self
        return replace(self, **valid)
