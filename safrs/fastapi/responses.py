# -*- coding: utf-8 -*-

from fastapi.responses import JSONResponse


class JSONAPIResponse(JSONResponse):
    """
    JSON:API requires 'application/vnd.api+json'
    """
    media_type = "application/vnd.api+json"

