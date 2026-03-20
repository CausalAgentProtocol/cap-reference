from __future__ import annotations

from typing import Literal

from pydantic import Field

from cap.core.contracts import (
    CAPProvenancedSuccessResponse,
    GraphPath,
    GraphPathEdge,
    GraphPathNode,
    GraphPathsResult,
)


class AbelGraphPathEdge(GraphPathEdge):
    tau: int | None = None
    tau_duration: str | None = None


class AbelGraphPath(GraphPath):
    nodes: list[GraphPathNode] = Field(default_factory=list)
    edges: list[AbelGraphPathEdge] = Field(default_factory=list)


class AbelGraphPathsResult(GraphPathsResult):
    paths: list[AbelGraphPath] = Field(default_factory=list)


class AbelGraphPathsResponse(CAPProvenancedSuccessResponse[AbelGraphPathsResult]):
    verb: Literal["graph.paths"] = "graph.paths"


__all__ = [
    "AbelGraphPath",
    "AbelGraphPathEdge",
    "AbelGraphPathsResponse",
    "AbelGraphPathsResult",
]
