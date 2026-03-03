# -*- coding: utf-8 -*-

import json
from fastapi.responses import JSONResponse
from safrs.json_encoder import SAFRSJSONEncoder


class JSONAPIResponse(JSONResponse):
    """
    JSON:API requires 'application/vnd.api+json'
    """
    media_type = "application/vnd.api+json"

    def render(self, content: object) -> bytes:
        return json.dumps(content, cls=SAFRSJSONEncoder, ensure_ascii=False).encode("utf-8")
