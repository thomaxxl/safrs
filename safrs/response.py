"""
safrs response
"""
from flask import Response


class SAFRSResponse(Response):
    """
        Response class
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
