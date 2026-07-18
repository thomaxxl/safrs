import datetime
from http import HTTPStatus
from typing import Any

import pytest
import sqlalchemy
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from safrs import SAFRSBase, SafrsApi
from safrs.attr_parse import parse_attr
from safrs.errors import ValidationError


JSONAPI_HEADERS = {
    "Accept": "application/vnd.api+json",
    "Content-Type": "application/vnd.api+json",
}


@pytest.mark.parametrize(
    ("column_type", "type_name"),
    [
        (sqlalchemy.DateTime, "datetime.datetime"),
        (sqlalchemy.Date, "datetime.date"),
        (sqlalchemy.Time, "datetime.time"),
    ],
)
@pytest.mark.parametrize("invalid_value", ["not-a-date", ""])
def test_parse_attr_rejects_invalid_temporal_values(
    column_type: type[Any], type_name: str, invalid_value: str
) -> None:
    column = sqlalchemy.Column("temporal_value", column_type)

    with pytest.raises(ValidationError) as exc_info:
        parse_attr(column, invalid_value)

    assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST
    assert f'Invalid {type_name} value "{invalid_value}"' in exc_info.value.message


@pytest.mark.parametrize(
    ("column_type", "value", "expected"),
    [
        (
            sqlalchemy.DateTime,
            "2024-02-29 01:02:03",
            datetime.datetime(2024, 2, 29, 1, 2, 3),
        ),
        (
            sqlalchemy.DateTime,
            "2024-02-29 01:02:03.456789",
            datetime.datetime(2024, 2, 29, 1, 2, 3, 456789),
        ),
        (sqlalchemy.Date, "2024-02-29", datetime.datetime(2024, 2, 29)),
        (sqlalchemy.Time, "01:02:03", datetime.time(1, 2, 3)),
        (sqlalchemy.Time, "01:02:03.456789", datetime.time(1, 2, 3, 456789)),
    ],
)
def test_parse_attr_accepts_supported_temporal_values(
    column_type: type[Any], value: str, expected: Any
) -> None:
    column = sqlalchemy.Column("temporal_value", column_type)

    assert parse_attr(column, value) == expected


@pytest.mark.parametrize("column_type", [sqlalchemy.DateTime, sqlalchemy.Date, sqlalchemy.Time])
def test_parse_attr_preserves_null_temporal_values(column_type: type[Any]) -> None:
    column = sqlalchemy.Column("temporal_value", column_type)

    assert parse_attr(column, None) is None


def test_invalid_date_requests_return_400_without_persisting_the_value() -> None:
    db = SQLAlchemy()

    class TemporalResource(SAFRSBase, db.Model):
        __tablename__ = "temporal_resources"

        id = db.Column(db.Integer, primary_key=True)
        some_date = db.Column(db.Date)

    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)

    with app.app_context():
        db.create_all()
        api = SafrsApi(app, host="localhost", swaggerui_blueprint=False)
        api.expose_object(TemporalResource)

    resource_url = f"/{TemporalResource._s_collection_name}/"
    client = app.test_client()
    invalid_response = client.post(
        resource_url,
        headers=JSONAPI_HEADERS,
        json={
            "data": {
                "type": TemporalResource._s_type,
                "attributes": {"some_date": "not-a-date"},
            }
        },
    )

    assert invalid_response.status_code == HTTPStatus.BAD_REQUEST
    assert invalid_response.get_json()["errors"][0]["code"] == str(HTTPStatus.BAD_REQUEST)
    with app.app_context():
        assert db.session.query(TemporalResource).count() == 0

    valid_response = client.post(
        resource_url,
        headers=JSONAPI_HEADERS,
        json={
            "data": {
                "type": TemporalResource._s_type,
                "attributes": {"some_date": "2024-02-29"},
            }
        },
    )

    assert valid_response.status_code == HTTPStatus.CREATED
    resource_id = valid_response.get_json()["data"]["id"]
    invalid_patch_response = client.patch(
        f"{resource_url}{resource_id}/",
        headers=JSONAPI_HEADERS,
        json={
            "data": {
                "type": TemporalResource._s_type,
                "id": resource_id,
                "attributes": {"some_date": "not-a-date"},
            }
        },
    )

    assert invalid_patch_response.status_code == HTTPStatus.BAD_REQUEST
    with app.app_context():
        resource = db.session.get(TemporalResource, int(resource_id))
        assert resource.some_date == datetime.date(2024, 2, 29)
