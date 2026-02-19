# -*- coding: utf-8 -*-

from .diff import diff_internal_specs, diff_openapi_documents, format_report
from .normalize import load_openapi3_as_internal, load_swagger2_as_internal

__all__ = (
    "load_swagger2_as_internal",
    "load_openapi3_as_internal",
    "diff_internal_specs",
    "diff_openapi_documents",
    "format_report",
)
