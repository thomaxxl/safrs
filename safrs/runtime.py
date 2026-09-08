"""Request-local SAFRS runtime bindings.

The public ``safrs.DB`` attribute remains for backward compatibility, but
request handling must not consult mutable process-global application state.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from collections.abc import Iterator
from typing import Any, Optional

import safrs

_CURRENT_DB: ContextVar[Optional[Any]] = ContextVar("safrs_current_db", default=None)


def get_db() -> Any:
    current = _CURRENT_DB.get()
    return current if current is not None else safrs.DB


def set_db(db: Any) -> Token[Optional[Any]]:
    return _CURRENT_DB.set(db)


def reset_db(token: Token[Optional[Any]]) -> None:
    try:
        _CURRENT_DB.reset(token)
    except (RuntimeError, ValueError):
        # Flask can emit teardown signals more than once while handling an
        # exception.  A ContextVar token is single-use; ignoring an already
        # consumed or cross-context token preserves the currently active
        # binding instead of corrupting a surrounding application's context.
        return


@contextmanager
def bind_db(db: Any) -> Iterator[None]:
    """Bind a SAFRS database explicitly for a background task or script."""
    token = set_db(db)
    try:
        yield
    finally:
        reset_db(token)
