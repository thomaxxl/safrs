from __future__ import annotations

import pytest

from safrs.base import SAFRSBase
from safrs.errors import GenericError, IntegerOverflowError


class _IdType:
    @staticmethod
    def get_pks(value: object) -> dict[str, object]:
        return {"id": value}


class _OverflowQuery:
    def filter_by(self, **_kwargs: object) -> "_OverflowQuery":
        return self

    def first(self) -> object:
        raise OverflowError("Python int too large to convert to SQLite INTEGER")


class _GenericQuery:
    def filter_by(self, **_kwargs: object) -> "_GenericQuery":
        return self

    def first(self) -> object:
        raise RuntimeError("boom")


class _OverflowModel:
    _s_type = "OverflowModel"
    id_type = _IdType()
    _s_query = _OverflowQuery()


class _GenericModel:
    _s_type = "GenericModel"
    id_type = _IdType()
    _s_query = _GenericQuery()


def test_get_instance_raises_jsonapi_integer_overflow_error() -> None:
    with pytest.raises(IntegerOverflowError) as exc_info:
        SAFRSBase.get_instance.__func__(_OverflowModel, 10**200)

    assert exc_info.value.status_code == 400
    assert "Invalid integer value in id filter" in exc_info.value.message


def test_get_instance_keeps_generic_error_path_for_non_overflow_exceptions() -> None:
    with pytest.raises(GenericError) as exc_info:
        SAFRSBase.get_instance.__func__(_GenericModel, 1)

    assert exc_info.value.status_code == 500
    assert exc_info.value.message.startswith("Generic Error:")
