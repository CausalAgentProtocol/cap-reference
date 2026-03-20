from __future__ import annotations

from typing import TYPE_CHECKING, cast

from fastapi import Request

from abel_cap_server.cap.catalog import CAPServerIdentity, DEFAULT_CAP_GRAPH_PROFILE
from cap.core.contracts import CAPProvenance
from cap.server import CAPProvenanceContext

if TYPE_CHECKING:
    from abel_cap_server.cap.service import CapService


def build_abel_provenance_context(
    server_identity: CAPServerIdentity,
    *,
    graph_timestamp: str | None = None,
) -> CAPProvenanceContext:
    return CAPProvenanceContext(
        graph_version=DEFAULT_CAP_GRAPH_PROFILE.graph_version,
        graph_timestamp=graph_timestamp,
        server_name=server_identity.server_name,
        server_version=server_identity.server_version,
    )


def get_abel_provenance_context(payload: object, request: Request) -> CAPProvenanceContext:
    del payload
    service = cast("CapService", request.app.state.cap_service)
    return service.build_provenance_context()


__all__ = [
    "CAPProvenance",
    "CAPProvenanceContext",
    "build_abel_provenance_context",
    "get_abel_provenance_context",
]
