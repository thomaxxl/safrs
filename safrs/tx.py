# -*- coding: utf-8 -*-

"""Request transaction (unit-of-work) helpers.

SAFRS supports request-boundary commit in both Flask and FastAPI:
- model-layer writes flush and mark request state
- commit/rollback happens at the request boundary
- models can opt out with ``db_commit = False``

State storage backends:
- Flask: ContextVar-backed request state
- FastAPI: SQLAlchemy session-backed request state
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Optional

_SESSION_ACTIVE_KEY = "_safrs_uow_active"
_SESSION_WRITES_KEY = "_safrs_writes_seen"
_SESSION_AUTOCOMMIT_KEY = "_safrs_auto_commit_enabled"


@dataclass(frozen=True)
class _TxState:
    in_request: bool = False
    auto_commit_enabled: bool = True
    writes_seen: bool = False


_TX_STATE: ContextVar[_TxState] = ContextVar("safrs_tx_state", default=_TxState())


def _active_session_state() -> Optional[MutableMapping[str, Any]]:
    """Return active request state stored on the SQLAlchemy session."""
    try:
        import safrs

        session = safrs.DB.session
    except Exception:
        return None

    try:
        info = getattr(session, "info", None)
        if isinstance(info, dict) and bool(info.get(_SESSION_ACTIVE_KEY, False)):
            return info

        state = getattr(session, "_safrs_uow_state", None)
        if isinstance(state, dict) and bool(state.get(_SESSION_ACTIVE_KEY, False)):
            return state
    except Exception:
        return None

    return None


def begin_request() -> Token[_TxState]:
    """Begin ContextVar-backed request state (Flask)."""
    return _TX_STATE.set(_TxState(in_request=True, auto_commit_enabled=True, writes_seen=False))


def end_request(token: Token[_TxState]) -> None:
    """End ContextVar-backed request state (Flask)."""
    _TX_STATE.reset(token)


def in_request() -> bool:
    """Return True when a SAFRS request UoW is active."""
    state = _TX_STATE.get()
    if state.in_request:
        return True
    return _active_session_state() is not None


def has_writes() -> bool:
    """Return True if writes were observed during the active request."""
    state = _TX_STATE.get()
    if state.in_request:
        return bool(state.writes_seen)

    session_state = _active_session_state()
    if session_state is None:
        return False
    return bool(session_state.get(_SESSION_WRITES_KEY, False))


def disable_autocommit() -> None:
    """Disable request auto-commit for the active request."""
    state = _TX_STATE.get()
    if state.in_request:
        if state.auto_commit_enabled:
            _TX_STATE.set(
                _TxState(
                    in_request=True,
                    auto_commit_enabled=False,
                    writes_seen=state.writes_seen,
                )
            )
        return

    session_state = _active_session_state()
    if session_state is None:
        return
    session_state[_SESSION_AUTOCOMMIT_KEY] = False


def model_auto_commit_enabled(model_cls: Any) -> bool:
    """Return model auto-commit flag, defaulting to True."""
    class_dict = getattr(model_cls, "__dict__", None)
    if isinstance(class_dict, Mapping) and "db_commit" in class_dict:
        return bool(class_dict.get("db_commit"))
    return True


def note_write(model_cls: Any) -> None:
    """Record a write and apply model-level db_commit opt-out."""
    state = _TX_STATE.get()
    if state.in_request:
        auto_commit_enabled = state.auto_commit_enabled
        if auto_commit_enabled and model_auto_commit_enabled(model_cls) is False:
            auto_commit_enabled = False
        _TX_STATE.set(
            _TxState(
                in_request=True,
                auto_commit_enabled=auto_commit_enabled,
                writes_seen=True,
            )
        )
        return

    session_state = _active_session_state()
    if session_state is None:
        return

    session_state[_SESSION_WRITES_KEY] = True
    if bool(session_state.get(_SESSION_AUTOCOMMIT_KEY, True)) and model_auto_commit_enabled(model_cls) is False:
        session_state[_SESSION_AUTOCOMMIT_KEY] = False


def should_autocommit() -> bool:
    """Return True when request-boundary commit should happen."""
    state = _TX_STATE.get()
    if state.in_request:
        return bool(state.auto_commit_enabled and state.writes_seen)

    session_state = _active_session_state()
    if session_state is None:
        return False
    return bool(session_state.get(_SESSION_AUTOCOMMIT_KEY, True) and session_state.get(_SESSION_WRITES_KEY, False))
