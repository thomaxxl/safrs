# -*- coding: utf-8 -*-

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from collections.abc import Mapping
from typing import Any


@dataclass(frozen=True)
class _TxState:
    in_request: bool = False
    auto_commit_enabled: bool = True
    writes_seen: bool = False


_TX_STATE: ContextVar[_TxState] = ContextVar("safrs_tx_state", default=_TxState())


def begin_request() -> Token[_TxState]:
    return _TX_STATE.set(_TxState(in_request=True, auto_commit_enabled=True, writes_seen=False))


def end_request(token: Token[_TxState]) -> None:
    _TX_STATE.reset(token)


def in_request() -> bool:
    return bool(_TX_STATE.get().in_request)


def has_writes() -> bool:
    state = _TX_STATE.get()
    return bool(state.in_request and state.writes_seen)


def disable_autocommit() -> None:
    state = _TX_STATE.get()
    if not state.in_request:
        return
    if not state.auto_commit_enabled:
        return
    _TX_STATE.set(
        _TxState(
            in_request=True,
            auto_commit_enabled=False,
            writes_seen=state.writes_seen,
        )
    )


def model_auto_commit_enabled(model_cls: Any) -> bool:
    class_dict = getattr(model_cls, "__dict__", None)
    if isinstance(class_dict, Mapping) and "db_commit" in class_dict:
        return bool(class_dict.get("db_commit"))
    return True


def note_write(model_cls: Any) -> None:
    state = _TX_STATE.get()
    if not state.in_request:
        return
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


def should_autocommit() -> bool:
    state = _TX_STATE.get()
    return bool(state.in_request and state.auto_commit_enabled and state.writes_seen)
