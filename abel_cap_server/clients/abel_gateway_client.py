from collections.abc import Mapping
from typing import Any

import httpx

from abel_cap_server.core.config import Settings


class AbelGatewayClient:
    def __init__(
        self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._base_url = settings.cap_upstream_base_url.rstrip("/")
        self._gateway_api_key = (
            settings.gateway_api_key.get_secret_value() if settings.gateway_api_key else None
        )
        self._timeout_seconds = settings.cap_upstream_timeout_seconds
        self._transport = transport
        # Reuse one AsyncClient to keep connection pooling warm under concurrency.
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout_seconds,
            transport=self._transport,
        )

    @property
    def base_url(self) -> str:
        return self._base_url

    async def fetch_schema_primitives(
        self,
        *,
        timeout_ms: int | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        return await self._get_json("v1/schema/primitives", timeout_ms=timeout_ms, headers=headers)

    async def fetch_schema_paths(
        self,
        *,
        source_node_id: str,
        target_node_id: str,
        timeout_ms: int | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        response = await self._client.get(
            "v1/schema/paths",
            params={"from": source_node_id, "to": target_node_id},
            headers=self._build_headers(headers),
            timeout=self._request_timeout(timeout_ms),
        )
        response.raise_for_status()
        return response.json()

    async def predict(
        self,
        payload: Mapping[str, Any],
        *,
        timeout_ms: int | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        return await self._post_json(
            "v1/predict",
            payload=payload,
            timeout_ms=timeout_ms,
            headers=headers,
        )

    async def explain(
        self,
        payload: Mapping[str, Any],
        *,
        timeout_ms: int | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        return await self._post_json(
            "v1/explain",
            payload=payload,
            timeout_ms=timeout_ms,
            headers=headers,
        )

    async def intervene(
        self,
        payload: Mapping[str, Any],
        *,
        timeout_ms: int | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        return await self._post_json(
            "v1/intervene",
            payload=payload,
            timeout_ms=timeout_ms,
            headers=headers,
        )

    async def counterfactual(
        self,
        payload: Mapping[str, Any],
        *,
        timeout_ms: int | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        return await self._post_json(
            "v1/counterfactual",
            payload=payload,
            timeout_ms=timeout_ms,
            headers=headers,
        )

    async def validate(
        self,
        payload: Mapping[str, Any],
        *,
        timeout_ms: int | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        return await self._post_json(
            "v1/validate",
            payload=payload,
            timeout_ms=timeout_ms,
            headers=headers,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get_json(
        self,
        path: str,
        *,
        timeout_ms: int | None,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        response = await self._client.get(
            path,
            headers=self._build_headers(headers),
            timeout=self._request_timeout(timeout_ms),
        )
        response.raise_for_status()
        return response.json()

    async def _post_json(
        self,
        path: str,
        *,
        payload: Mapping[str, Any],
        timeout_ms: int | None,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        response = await self._client.post(
            path,
            json=dict(payload),
            headers=self._build_headers(headers),
            timeout=self._request_timeout(timeout_ms),
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _request_timeout(timeout_ms: int | None) -> float | None:
        return (timeout_ms / 1000) if timeout_ms else None

    def _build_headers(self, headers: Mapping[str, str] | None = None) -> dict[str, str]:
        authorization = self._resolve_authorization(headers)
        if authorization is None:
            if self._gateway_api_key is None:
                raise RuntimeError("CAP_GATEWAY_API_KEY is not configured")
            authorization = self._normalize_bearer_token(self._gateway_api_key)
        return {"Authorization": authorization}

    def _resolve_authorization(self, headers: Mapping[str, str] | None) -> str | None:
        if headers is None:
            return None

        authorization = self._read_header(headers, "authorization")
        if authorization:
            return self._normalize_bearer_token(authorization)
        return None

    @staticmethod
    def _read_header(headers: Mapping[str, str], name: str) -> str | None:
        for header_name, value in headers.items():
            if header_name.lower() == name:
                return value
        return None

    @staticmethod
    def _normalize_bearer_token(value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise RuntimeError("Gateway authorization token cannot be empty")

        prefix, separator, remainder = normalized.partition(" ")
        if separator and prefix.lower() == "bearer" and remainder.strip():
            return f"Bearer {remainder.strip()}"
        return f"Bearer {normalized}"
