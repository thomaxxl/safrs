# Response class
from flask import Response


class SAFRSResponse(Response):
    """
    Response class
    """

    safrs_headers = {"Content-Type": "application/vnd.api+json"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
