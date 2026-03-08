from typing import Any
# Response class
from flask import Response


class SAFRSResponse(Response):
    """
    Response class
    """

    safrs_headers = {"Content-Type": "application/vnd.api+json"}

    def __init__(self: Any, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
