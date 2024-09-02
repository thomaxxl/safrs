import datetime
import safrs
import sqlalchemy


def parse_attr(column, attr_val):
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

    """
        Parse datetime and date values for some common representations
        If another format is used, the user should create a custom column type or custom serialization
    """
    if attr_val and column.type.python_type == datetime.datetime:
        date_str = str(attr_val)
        try:
            if "." in date_str:
                # str(datetime.datetime.now()) => "%Y-%m-%d %H:%M:%S.%f"
                attr_val = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S.%f")
            else:
                # JS datepicker format
                attr_val = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        except (NotImplementedError, ValueError) as exc:
            safrs.log.warning(f'Invalid datetime.datetime {exc} for value "{attr_val}"')
            attr_val = datetime.datetime.now()
    elif attr_val and column.type.python_type == datetime.date:
        try:
            attr_val = datetime.datetime.strptime(str(attr_val), "%Y-%m-%d")
        except (NotImplementedError, ValueError) as exc:
            safrs.log.warning(f'Invalid datetime.date {exc} for value "{attr_val}"')
            attr_val = datetime.datetime.now()
    elif attr_val and column.type.python_type == datetime.time:  # pragma: no cover (todo)
        try:
            date_str = str(attr_val)
            if "." in date_str:
                # str(datetime.datetime.now()) => "%H:%M:%S.%f"
                attr_val = datetime.datetime.strptime(str(attr_val), "%H:%M:%S.%f").time()
            else:
                # JS datepicker format
                attr_val = datetime.datetime.strptime(str(attr_val), "%H:%M:%S").time()
        except (NotImplementedError, ValueError, TypeError) as exc:
            safrs.log.warning(f'Invalid datetime.time {exc} for value "{attr_val}"')
            attr_val = column.type.python_type()
    else:
        attr_val = column.type.python_type(attr_val)

    return attr_val
