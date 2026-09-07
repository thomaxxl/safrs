from contextvars import ContextVar, Token
import logging
from typing import Any, Optional
# Exception handlers keep client diagnostics independent from logger level.
#
# The exceptions will be caught in http_method_decorator and formatted, for example:
# {
#      "title": "Authorization Error: ",
#      "detail": "Authorization Error: ",
#      "code": 401
# }
#
from flask import has_request_context, request
from werkzeug.exceptions import NotFound
import safrs
from sqlalchemy.exc import DontWrapMixin
from http import HTTPStatus
from urllib.parse import urlsplit

HIDDEN_LOG = "(debug logging disabled)"
_FASTAPI_REQUEST_URL: ContextVar[Optional[str]] = ContextVar("safrs_fastapi_request_url", default=None)


def set_fastapi_request_url(url: Optional[str]) -> Token[Optional[str]]:
    if url is None:
        return _FASTAPI_REQUEST_URL.set(None)
    return _FASTAPI_REQUEST_URL.set(str(url))


def reset_fastapi_request_url(token: Token[Optional[str]]) -> None:
    try:
        _FASTAPI_REQUEST_URL.reset(token)
    except ValueError:
        # FastAPI may execute dependency cleanup in a different worker context.
        # In that case a token reset is invalid; clear the current context instead.
        _FASTAPI_REQUEST_URL.set(None)


def _current_request_url() -> Optional[str]:
    fastapi_url = _FASTAPI_REQUEST_URL.get()
    if fastapi_url:
        return fastapi_url
    if has_request_context():
        try:
            return str(request.url)
        except Exception:
            return None
    return fastapi_url


def _infer_resource_and_object_id(request_url: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if not request_url:
        return None, None

    try:
        path = urlsplit(str(request_url)).path
    except Exception:
        return None, None

    segments = [segment for segment in path.split("/") if segment]
    if not segments:
        return None, None

    if "api" in segments:
        api_index = max(index for index, segment in enumerate(segments) if segment == "api")
        segments = segments[api_index + 1 :]
        if not segments:
            return None, None

    resource = segments[0]
    object_id = None
    if len(segments) > 1 and segments[1] not in {"swagger", "swagger.json", "openapi", "openapi.json"}:
        object_id = segments[1]
    return resource, object_id


def log_integrity_error_details(
    exc: Any,
    *,
    request_url: Optional[str] = None,
    resource: Optional[str] = None,
    object_id: Optional[str] = None,
) -> None:
    if not safrs.log.isEnabledFor(logging.DEBUG):
        return

    url = request_url or _current_request_url()
    inferred_resource, inferred_object_id = _infer_resource_and_object_id(url)
    effective_resource = resource or inferred_resource
    effective_object_id = object_id or inferred_object_id
    safrs.log.debug(
        "IntegrityError diagnostics: path=%s resource=%s object_present=%s exception=%s",
        urlsplit(url).path if url else None,
        effective_resource,
        effective_object_id is not None,
        type(exc).__name__,
    )


class JsonapiError(Exception, DontWrapMixin):
    pass


class NotFoundError(JsonapiError, NotFound):
    """
    This exception is raised when an item was not found
    """

    status_code = HTTPStatus.NOT_FOUND.value
    message = "NotFoundError "

    def __init__(self: Any, message: Any='', status_code: Any=HTTPStatus.NOT_FOUND.value, api_code: Any=None) -> None:
        """
        :param message: Message to be returned in the (json) body
        :param status_code: HTTP Status code
        :param api_code: API code
        """
        JsonapiError.__init__(self)
        self.status_code = status_code
        safrs.log.info("Resource not found")
        self.message += "Resource not found"


class UnAuthorizedError(JsonapiError):
    """
    This exception is raised when an authorization error occured
    we use FORBIDDEN(403) instead of UNAUTHORIZED(401) (old http status code descriptions were not clear)
    """

    status_code = HTTPStatus.FORBIDDEN.value
    message = "Authorization Error: "

    def __init__(self: Any, message: Any='', status_code: Any=HTTPStatus.FORBIDDEN.value, api_code: Any=None) -> None:
        super().__init__()
        self.status_code = status_code
        safrs.log.warning("Authorization denied")
        self.message += "Access denied"


class GenericError(JsonapiError):
    """
    This exception is raised when an error has been detected
    """

    status_code = HTTPStatus.INTERNAL_SERVER_ERROR.value  # 500
    message = "Generic Error: "

    def __init__(self: Any, message: Any, status_code: Any=HTTPStatus.INTERNAL_SERVER_ERROR.value, api_code: Any=None) -> None:
        super().__init__()
        self.status_code = status_code
        safrs.log.error("Generic request failure (%s)", type(message).__name__)
        self.message += "Internal Server Error"


class SystemValidationError(JsonapiError):  # pragma: no cover
    """
    This exception is raised when invalid input has been detected (server side input)
    """

    status_code = HTTPStatus.BAD_REQUEST.value
    message = "Validation Error: "

    def __init__(self: Any, message: Any='', status_code: Any=HTTPStatus.BAD_REQUEST.value, api_code: Any=None) -> None:
        super().__init__()
        self.status_code = status_code
        safrs.log.error("Server-side validation failure")
        self.message += "Invalid server configuration"


class ValidationError(JsonapiError):
    """
    This exception is raised when invalid input has been detected (client side input)
    Always send back the message to the client in the response
    """

    status_code = HTTPStatus.BAD_REQUEST.value
    message = "Validation Error: "

    def __init__(self: Any, message: Any='', status_code: Any=HTTPStatus.BAD_REQUEST.value, api_code: Any=None) -> None:
        super().__init__()
        self.status_code = status_code
        safrs.log.warning("Client validation failed")
        self.message += message


class IntegerOverflowError(ValidationError):
    """
    Raised when an integer value cannot be represented by the target DB type.
    """

    status_code = HTTPStatus.BAD_REQUEST.value
    message = "Integer Overflow Error: "

    def __init__(self: Any, message: Any='', status_code: Any=HTTPStatus.BAD_REQUEST.value, api_code: Any=None) -> None:
        JsonapiError.__init__(self)
        self.status_code = status_code
        safrs.log.warning("Client integer validation failed")
        self.message += message
