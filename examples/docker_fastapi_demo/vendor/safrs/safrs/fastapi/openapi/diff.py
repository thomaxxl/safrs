# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from .normalize import InternalSpec, load_any_spec_as_internal


def diff_internal_specs(reference: InternalSpec, candidate: InternalSpec) -> Dict[str, Any]:
    reference_ops = reference["operations"]
    candidate_ops = candidate["operations"]

    missing_operations = sorted([list(op) for op in reference_ops.keys() - candidate_ops.keys()])
    extra_operations = sorted([list(op) for op in candidate_ops.keys() - reference_ops.keys()])

    status_code_mismatches: List[Dict[str, Any]] = []
    missing_parameters: List[Dict[str, Any]] = []
    missing_request_body: List[Dict[str, Any]] = []
    missing_response_media_types: List[Dict[str, Any]] = []

    for op_key in sorted(reference_ops.keys() & candidate_ops.keys()):
        ref_op = reference_ops[op_key]
        cand_op = candidate_ops[op_key]
        op_path, op_method = op_key

        ref_status_codes = set(ref_op["responses"].keys())
        cand_status_codes = set(cand_op["responses"].keys())
        status_missing = sorted(ref_status_codes - cand_status_codes)
        if status_missing:
            status_code_mismatches.append(
                {"operation": [op_path, op_method], "missing_status_codes": status_missing}
            )

        ref_params = {(param["in_"], param["name"]) for param in ref_op["parameters"]}
        cand_params = {(param["in_"], param["name"]) for param in cand_op["parameters"]}
        param_missing = sorted([list(param) for param in ref_params - cand_params])
        if param_missing:
            missing_parameters.append({"operation": [op_path, op_method], "missing_parameters": param_missing})

        ref_request_media = set(ref_op["request_body"].keys())
        cand_request_media = set(cand_op["request_body"].keys())
        request_media_missing = sorted(ref_request_media - cand_request_media)
        if request_media_missing:
            missing_request_body.append(
                {"operation": [op_path, op_method], "missing_media_types": request_media_missing}
            )

        for status_code, ref_media_types in ref_op["responses"].items():
            cand_media_types = cand_op["responses"].get(status_code, {})
            if not ref_media_types:
                continue
            missing_media = sorted(set(ref_media_types.keys()) - set(cand_media_types.keys()))
            if missing_media:
                missing_response_media_types.append(
                    {
                        "operation": [op_path, op_method],
                        "status_code": status_code,
                        "missing_media_types": missing_media,
                    }
                )

    ref_tags = reference.get("tags", {})
    cand_tags = candidate.get("tags", {})
    missing_tags = sorted(tag for tag in ref_tags.keys() if tag not in cand_tags)

    return {
        "missing_operations": missing_operations,
        "extra_operations": extra_operations,
        "status_code_mismatches": status_code_mismatches,
        "missing_parameters": missing_parameters,
        "missing_request_body": missing_request_body,
        "missing_response_media_types": missing_response_media_types,
        "missing_tags": missing_tags,
    }


def diff_openapi_documents(reference_spec: Dict[str, Any], candidate_spec: Dict[str, Any]) -> Dict[str, Any]:
    reference = load_any_spec_as_internal(reference_spec)
    candidate = load_any_spec_as_internal(candidate_spec)
    return diff_internal_specs(reference, candidate)


def _count(item: Any) -> int:
    if isinstance(item, list):
        return len(item)
    return 0


def format_report(report: Dict[str, Any], top_n: int = 10) -> str:
    lines = [
        "Spec Diff Summary",
        f"- missing_operations: {_count(report.get('missing_operations'))}",
        f"- status_code_mismatches: {_count(report.get('status_code_mismatches'))}",
        f"- missing_parameters: {_count(report.get('missing_parameters'))}",
        f"- missing_request_body: {_count(report.get('missing_request_body'))}",
        f"- missing_response_media_types: {_count(report.get('missing_response_media_types'))}",
        f"- missing_tags: {_count(report.get('missing_tags'))}",
        "",
        f"Top {top_n} differences:",
    ]

    ranked: List[Tuple[str, Dict[str, Any]]] = []
    for category in (
        "missing_operations",
        "status_code_mismatches",
        "missing_parameters",
        "missing_request_body",
        "missing_response_media_types",
    ):
        for entry in report.get(category, [])[:top_n]:
            ranked.append((category, entry))

    if not ranked:
        lines.append("- none")
    else:
        for category, entry in ranked[:top_n]:
            lines.append(f"- [{category}] {json.dumps(entry, sort_keys=True)}")

    return "\n".join(lines)
