from typing import Any
import datetime
import safrs
import sqlalchemy
from .errors import ValidationError


def _parse_datetime_value(attr_val: Any) -> datetime.datetime:
    date_str = str(attr_val)
    if "." in date_str:
        return datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S.%f")
    return datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")


def _parse_time_value(attr_val: Any) -> datetime.time:
    date_str = str(attr_val)
    if "." in date_str:
        return datetime.datetime.strptime(str(attr_val), "%H:%M:%S.%f").time()
    return datetime.datetime.strptime(str(attr_val), "%H:%M:%S").time()


def _parse_temporal_attr(column: Any, attr_val: Any) -> tuple[bool, Any]:
    if attr_val and column.type.python_type == datetime.datetime:
        try:
            return True, _parse_datetime_value(attr_val)
        except (NotImplementedError, ValueError) as exc:
            safrs.log.warning(f'Invalid datetime.datetime {exc} for value "{attr_val}"')
            return True, datetime.datetime.now()
    if attr_val and column.type.python_type == datetime.date:
        try:
            return True, datetime.datetime.strptime(str(attr_val), "%Y-%m-%d")
        except (NotImplementedError, ValueError) as exc:
            safrs.log.warning(f'Invalid datetime.date {exc} for value "{attr_val}"')
            return True, datetime.datetime.now()
    if attr_val and column.type.python_type == datetime.time:  # pragma: no cover (todo)
        try:
            return True, _parse_time_value(attr_val)
        except (NotImplementedError, ValueError, TypeError) as exc:
            safrs.log.warning(f'Invalid datetime.time {exc} for value "{attr_val}"')
            return True, column.type.python_type()
    return False, attr_val


def parse_attr(column: Any, attr_val: Any) -> Any:
    """
    Parse the supplied `attr_val` so it can be saved in the SQLAlchemy `column`

    :param attr: SQLAlchemy column
    :param attr_val: jsonapi attribute value
    :return: processed value
    """
    if attr_val is None and column.default:
        attr_val = column.default.arg
        return attr_val

    if attr_val is None:
        return attr_val

    if getattr(column, "python_type", None):
        # It's possible for a column to specify a custom python_type to use for deserialization
        try:
            attr_val = column.python_type(attr_val)
        except (TypeError, ValueError, OverflowError) as exc:
            column_name = getattr(column, "name", getattr(column, "key", "<unknown>"))
            raise ValidationError(f'Invalid value "{attr_val}" for attribute "{column_name}"') from exc

    try:
        column.type.python_type
    except NotImplementedError as exc:
        """
        This happens when a custom type has been implemented, in which case the user/dev should know how to handle it:
        override this method and implement the parsing
        https://docs.python.org/2/library/exceptions.html#exceptions.NotImplementedError :
        In user defined base classes, abstract methods should raise this exception when they require derived classes to override the method.
        => simply return the attr_val for user-defined classes
        """
        safrs.log.debug(exc)
        return attr_val

    # skip type coercion on JSON columns, since they could be anything
    if type(column.type) is sqlalchemy.sql.sqltypes.JSON:
        return attr_val

    parsed, parsed_value = _parse_temporal_attr(column, attr_val)
    if parsed:
        return parsed_value
    try:
        attr_val = column.type.python_type(attr_val)
    except (TypeError, ValueError, OverflowError) as exc:
        column_name = getattr(column, "name", getattr(column, "key", "<unknown>"))
        raise ValidationError(f'Invalid value "{attr_val}" for attribute "{column_name}"') from exc

    return attr_val
