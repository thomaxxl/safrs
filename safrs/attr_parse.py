from typing import Any
import datetime
import safrs
import sqlalchemy


def _coerce_datetime_value(attr_val: Any) -> Any:
    date_str = str(attr_val)
    if "." in date_str:
        # str(datetime.datetime.now()) => "%Y-%m-%d %H:%M:%S.%f"
        return datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S.%f")
    # JS datepicker format
    return datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")


def _coerce_date_value(attr_val: Any) -> Any:
    return datetime.datetime.strptime(str(attr_val), "%Y-%m-%d")


def _coerce_time_value(attr_val: Any) -> Any:
    date_str = str(attr_val)
    if "." in date_str:
        # str(datetime.datetime.now()) => "%H:%M:%S.%f"
        return datetime.datetime.strptime(date_str, "%H:%M:%S.%f").time()
    # JS datepicker format
    return datetime.datetime.strptime(date_str, "%H:%M:%S").time()


def _column_python_type(column: Any) -> Any:
    try:
        python_type = column.type.python_type
    except NotImplementedError as exc:
        """
        This happens when a custom type has been implemented, in which case the user/dev should know how to handle it:
        override this method and implement the parsing
        https://docs.python.org/2/library/exceptions.html#exceptions.NotImplementedError :
        In user defined base classes, abstract methods should raise this exception when they require derived classes to override the method.
        => simply return None for user-defined classes
        """
        safrs.log.debug(exc)
        return None

    # skip type coercion on JSON columns, since they could be anything
    if type(column.type) is sqlalchemy.sql.sqltypes.JSON:
        return None

    return python_type


def _coerce_attr_with_type(python_type: Any, attr_val: Any) -> Any:
    if attr_val and python_type == datetime.datetime:
        try:
            return _coerce_datetime_value(attr_val)
        except (NotImplementedError, ValueError) as exc:
            safrs.log.warning(f'Invalid datetime.datetime {exc} for value "{attr_val}"')
            return datetime.datetime.now()

    if attr_val and python_type == datetime.date:
        try:
            return _coerce_date_value(attr_val)
        except (NotImplementedError, ValueError) as exc:
            safrs.log.warning(f'Invalid datetime.date {exc} for value "{attr_val}"')
            return datetime.datetime.now()

    if attr_val and python_type == datetime.time:  # pragma: no cover (todo)
        try:
            return _coerce_time_value(attr_val)
        except (NotImplementedError, ValueError, TypeError) as exc:
            safrs.log.warning(f'Invalid datetime.time {exc} for value "{attr_val}"')
            return python_type()

    return python_type(attr_val)


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
        attr_val = column.python_type(attr_val)

    python_type = _column_python_type(column)
    if python_type is None:
        return attr_val

    """
    Parse datetime/date/time values for common representations.
    For other types, apply the SQLAlchemy column python type directly.
    """
    return _coerce_attr_with_type(python_type, attr_val)
