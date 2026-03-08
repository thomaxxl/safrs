from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import safrs
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

Base = declarative_base()


class SAFRSDBWrapper:
    """Minimal DB wrapper expected by SAFRS internals."""

    def __init__(self, session: Any, model: Any) -> None:
        self.session = session
        self.Model = model


@dataclass
class RuntimeDB:
    engine: Any
    session: Any
    wrapper: SAFRSDBWrapper


def create_runtime(db_path: Path) -> RuntimeDB:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        future=True,
    )
    session = scoped_session(session_factory)
    wrapper = SAFRSDBWrapper(session, Base)
    safrs.DB = wrapper
    Base.metadata.create_all(engine)
    return RuntimeDB(engine=engine, session=session, wrapper=wrapper)
