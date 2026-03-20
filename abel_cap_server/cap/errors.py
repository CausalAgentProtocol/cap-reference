from __future__ import annotations

import json

import httpx
from fastapi import FastAPI

from cap.core.errors import CAPErrorBody, CAPErrorCode, CAPErrorResponse, CAPHTTPError
from cap.server.errors import (
    CAPAdapterError,
    register_cap_exception_handlers as register_protocol_cap_exception_handlers,
)


def translate_upstream_error(exc: Exception, *, operation: str) -> CAPAdapterError:
    if isinstance(exc, httpx.TimeoutException):
        return CAPAdapterError(
            "computation_timeout",
            f"{operation} timed out while calling Abel primitives.",
            status_code=504,
        )

    if isinstance(exc, httpx.HTTPStatusError):
        detail = _extract_http_error_detail(exc)
        status_code = exc.response.status_code

        if status_code == 404:
            code: CAPErrorCode = "path_not_found" if "path" in detail.lower() else "node_not_found"
            return CAPAdapterError(
                code, detail or "Requested node was not found.", status_code=status_code
            )

        if status_code in {400, 422}:
            code = (
                "invalid_intervention"
                if operation in {"intervene", "counterfactual"}
                else "invalid_request"
            )
            return CAPAdapterError(
                code, detail or f"Invalid request for {operation}.", status_code=status_code
            )

        if status_code == 503:
            return CAPAdapterError(
                "service_unavailable",
                "Abel primitive service is unavailable.",
                status_code=status_code,
                details={"upstream_detail": detail},
            )

        return CAPAdapterError(
            "upstream_error",
            detail or f"Abel primitive {operation} request failed.",
            status_code=status_code,
            details={"upstream_detail": detail},
        )

    if isinstance(exc, httpx.HTTPError):
        return CAPAdapterError(
            "service_unavailable",
            "Abel primitive service is unavailable.",
            status_code=503,
        )

    return CAPAdapterError(
        "upstream_error",
        f"Unexpected failure while running {operation}.",
        status_code=500,
        details={"error": str(exc)},
    )


def register_cap_exception_handlers(app: FastAPI) -> None:
    register_protocol_cap_exception_handlers(app)


def _extract_http_error_detail(exc: httpx.HTTPStatusError) -> str:
    try:
        payload = exc.response.json()
    except json.JSONDecodeError:
        return exc.response.text or ""

    if isinstance(payload, dict):
        detail = payload.get("detail") or payload.get("error")
        if isinstance(detail, str):
            return detail
    return exc.response.text or ""


__all__ = [
    "CAPAdapterError",
    "CAPErrorBody",
    "CAPErrorCode",
    "CAPErrorResponse",
    "CAPHTTPError",
    "register_cap_exception_handlers",
    "translate_upstream_error",
]
