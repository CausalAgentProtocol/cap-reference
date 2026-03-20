import argparse
import json

import httpx

from abel_cap_client.client import AsyncAbelCAPClient, DEFAULT_CAP_ROUTES
from abel_cap_client.example import build_parser, run_command
from cap.client import AsyncCAPClient
from cap.core import (
    ASSUMPTION_CAUSAL_SUFFICIENCY,
    IDENTIFICATION_STATUS_NOT_FORMALLY_IDENTIFIED,
    REASONING_MODE_GRAPH_PROPAGATION,
)


def test_cap_client_example_uses_single_entry_by_default() -> None:
    routes = DEFAULT_CAP_ROUTES
    assert routes.resolve("graph.neighbors") == "/cap"


def test_cap_client_example_parser_accepts_repeatable_headers() -> None:
    args = build_parser().parse_args(
        [
            "--base-url",
            "https://cap.example",
            "--header",
            "Authorization: Bearer cli-key",
            "--header",
            "X-Trace-ID: trace-123",
            "capabilities",
        ]
    )

    assert args.headers == [
        ("Authorization", "Bearer cli-key"),
        ("X-Trace-ID", "trace-123"),
    ]


def test_cap_client_example_neighbors_command_returns_json_shape(monkeypatch) -> None:
    async def _handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/cap"
        assert "Authorization" not in request.headers
        assert json.loads(request.content.decode("utf-8"))["verb"] == "graph.neighbors"
        return httpx.Response(
            200,
            json={
                "cap_version": "0.2.2",
                "request_id": "req-neighbors",
                "verb": "graph.neighbors",
                "status": "success",
                "result": {
                    "node_id": "NVDA_close",
                    "scope": "children",
                    "neighbors": [{"node_id": "AMD_close", "roles": ["child"]}],
                    "reasoning_mode": "identified_causal_effect",
                    "identification_status": "identified",
                    "assumptions": [""],
                    "edge_semantics": "identified_causal_effect",
                    "total_candidate_count": 1,
                    "truncated": False,
                },
                "provenance": {
                    "algorithm": "graph.neighbors",
                    "graph_version": "CausalNodeV2",
                    "computation_time_ms": 8,
                    "server_name": "abel-cap",
                    "server_version": "0.1.0",
                    "cap_spec_version": "0.2.2",
                },
            },
        )

    original_init = AsyncCAPClient.__init__

    def _fake_init(self, base_url: str, **kwargs) -> None:
        original_init(self, base_url, transport=httpx.MockTransport(_handler), **kwargs)

    monkeypatch.setattr(AsyncCAPClient, "__init__", _fake_init)

    payload = __import__("asyncio").run(
        run_command(
            argparse.Namespace(
                base_url="https://cap.example",
                command="neighbors",
                node_id="NVDA_close",
                scope="children",
                max_neighbors=5,
            )
        )
    )

    assert payload["verb"] == "graph.neighbors"
    assert payload["result"]["neighbors"][0]["node_id"] == "AMD_close"


def test_cap_client_example_capabilities_command_can_send_request_headers(monkeypatch) -> None:
    async def _handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer cli-key"
        assert request.headers["X-Trace-ID"] == "trace-123"
        return httpx.Response(
            200,
            json={
                "cap_version": "0.2.2",
                "request_id": "req-meta",
                "verb": "meta.capabilities",
                "status": "success",
                "result": {
                    "$schema": "https://causalagentprotocol.org/schema/capability-card/v0.2.2.json",
                    "name": "Abel CAP Test",
                    "description": "Capability card used by example client tests.",
                    "version": "0.1.0",
                    "cap_spec_version": "0.2.2",
                    "provider": {"name": "Abel AI", "url": "https://abel.ai"},
                    "endpoint": "https://cap.example/cap",
                    "conformance_level": 1,
                    "supported_verbs": {"core": ["meta.capabilities"], "convenience": []},
                    "assumptions": [],
                    "reasoning_modes_supported": [],
                    "graph": {
                        "domains": [],
                        "node_count": 1,
                        "edge_count": 0,
                        "node_types": [],
                        "edge_types_supported": [],
                        "graph_representation": "time_lagged_directed_graph",
                        "update_frequency": "unknown",
                        "temporal_resolution": "unknown",
                        "coverage_description": "test fixture",
                    },
                    "authentication": {"type": "api_key", "details": {}},
                    "access_tiers": [],
                    "disclosure_policy": {
                        "hidden_fields": [],
                        "default_response_detail": "summary",
                        "notes": [],
                    },
                },
            },
        )

    original_init = AsyncCAPClient.__init__

    def _fake_init(self, base_url: str, **kwargs) -> None:
        original_init(self, base_url, transport=httpx.MockTransport(_handler), **kwargs)

    monkeypatch.setattr(AsyncCAPClient, "__init__", _fake_init)

    payload = __import__("asyncio").run(
        run_command(
            argparse.Namespace(
                base_url="https://cap.example",
                command="capabilities",
                headers=[
                    ("Authorization", "Bearer cli-key"),
                    ("X-Trace-ID", "trace-123"),
                ],
            )
        )
    )

    assert payload["verb"] == "meta.capabilities"


def test_cap_client_example_markov_blanket_command_uses_extension_route_alias(monkeypatch) -> None:
    async def _handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/cap"
        assert json.loads(request.content.decode("utf-8")) == {
            "cap_version": "0.2.2",
            "options": {"response_detail": "summary"},
            "verb": "graph.markov_blanket",
            "params": {
                "node_id": "NVDA_close",
                "max_neighbors": 10,
            },
        }
        return httpx.Response(
            200,
            json={
                "cap_version": "0.2.2",
                "request_id": "req-markov-blanket",
                "verb": "graph.markov_blanket",
                "status": "success",
                "result": {
                    "node_id": "NVDA_close",
                    "neighbors": [
                        {"node_id": "SOXX_close", "roles": ["parent"]},
                        {"node_id": "QQQ_close", "roles": ["spouse"]},
                    ],
                    "reasoning_mode": "structural_semantics",
                    "identification_status": "not_applicable",
                    "assumptions": [ASSUMPTION_CAUSAL_SUFFICIENCY],
                    "edge_semantics": "markov_blanket_membership",
                    "total_candidate_count": 2,
                    "truncated": False,
                },
                "provenance": {
                    "algorithm": "primitive.explain",
                    "graph_version": "CausalNodeV2",
                    "computation_time_ms": 8,
                    "server_name": "abel-cap",
                    "server_version": "0.1.0",
                    "cap_spec_version": "0.2.2",
                },
            },
        )

    original_init = AsyncCAPClient.__init__

    def _fake_init(self, base_url: str, **kwargs) -> None:
        original_init(self, base_url, transport=httpx.MockTransport(_handler), **kwargs)

    monkeypatch.setattr(AsyncCAPClient, "__init__", _fake_init)

    payload = __import__("asyncio").run(
        run_command(
            argparse.Namespace(
                base_url="https://cap.example",
                command="markov-blanket",
                target_node="NVDA_close",
                max_neighbors=10,
            )
        )
    )

    assert payload["verb"] == "graph.markov_blanket"
    assert payload["result"]["neighbors"][1]["roles"] == ["spouse"]


def test_cap_client_example_observe_command_uses_core_target_only_shape(monkeypatch) -> None:
    async def _handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/cap"
        assert json.loads(request.content.decode("utf-8")) == {
            "cap_version": "0.2.2",
            "options": {"response_detail": "summary"},
            "verb": "observe.predict",
            "params": {
                "target_node": "NVDA_close",
            },
        }
        return httpx.Response(
            200,
            json={
                "cap_version": "0.2.2",
                "request_id": "req-observe",
                "verb": "observe.predict",
                "status": "success",
                "result": {
                    "target_node": "NVDA_close",
                    "prediction": 0.12,
                    "drivers": ["SOXX_close"],
                },
                "provenance": {
                    "algorithm": "primitive.predict",
                    "graph_version": "CausalNodeV2",
                    "computation_time_ms": 8,
                    "server_name": "abel-cap",
                    "server_version": "0.1.0",
                    "cap_spec_version": "0.2.2",
                },
            },
        )

    original_init = AsyncCAPClient.__init__

    def _fake_init(self, base_url: str, **kwargs) -> None:
        original_init(self, base_url, transport=httpx.MockTransport(_handler), **kwargs)

    monkeypatch.setattr(AsyncCAPClient, "__init__", _fake_init)

    payload = __import__("asyncio").run(
        run_command(
            argparse.Namespace(
                base_url="https://cap.example",
                command="observe",
                target_node="NVDA_close",
            )
        )
    )

    assert payload["verb"] == "observe.predict"
    assert payload["result"]["target_node"] == "NVDA_close"


def test_cap_client_example_observe_command_omits_optional_model_and_feature_type(
    monkeypatch,
) -> None:
    async def _handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/cap"
        assert json.loads(request.content.decode("utf-8")) == {
            "cap_version": "0.2.2",
            "options": {"response_detail": "summary"},
            "verb": "observe.predict",
            "params": {
                "target_node": "NVDA_close",
            },
        }
        return httpx.Response(
            200,
            json={
                "cap_version": "0.2.2",
                "request_id": "req-observe",
                "verb": "observe.predict",
                "status": "success",
                "result": {
                    "target_node": "NVDA_close",
                    "prediction": 0.12,
                    "drivers": ["SOXX_close"],
                },
                "provenance": {
                    "algorithm": "primitive.predict",
                    "graph_version": "CausalNodeV2",
                    "computation_time_ms": 8,
                    "server_name": "abel-cap",
                    "server_version": "0.1.0",
                    "cap_spec_version": "0.2.2",
                },
            },
        )

    original_init = AsyncCAPClient.__init__

    def _fake_init(self, base_url: str, **kwargs) -> None:
        original_init(self, base_url, transport=httpx.MockTransport(_handler), **kwargs)

    monkeypatch.setattr(AsyncCAPClient, "__init__", _fake_init)

    payload = __import__("asyncio").run(
        run_command(
            argparse.Namespace(
                base_url="https://cap.example",
                command="observe",
                target_node="NVDA_close",
            )
        )
    )

    assert payload["verb"] == "observe.predict"
    assert payload["result"]["target_node"] == "NVDA_close"


def test_abel_cap_client_time_lag_helper_posts_extension_payload() -> None:
    async def _handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/cap"
        assert json.loads(request.content.decode("utf-8")) == {
            "cap_version": "0.2.2",
            "options": {"response_detail": "summary"},
            "verb": "extensions.abel.intervene_time_lag",
            "params": {
                "treatment_node": "NVDA_close",
                "treatment_value": 0.05,
                "outcome_node": "SONY_close",
                "horizon_steps": 24,
                "model": "linear",
            },
        }
        return httpx.Response(
            200,
            json={
                "cap_version": "0.2.2",
                "request_id": "req-time-lag",
                "verb": "extensions.abel.intervene_time_lag",
                "status": "success",
                "result": {
                    "treatment_node": "NVDA_close",
                    "treatment_value": 0.05,
                    "outcome_node": "SONY_close",
                    "model": "linear",
                    "delta_unit": "delta",
                    "horizon_steps": 24,
                    "reasoning_mode": REASONING_MODE_GRAPH_PROPAGATION,
                    "outcome_summary": {
                        "node_id": "SONY_close",
                        "final_cumulative_effect": 0.08,
                        "first_arrive_step": 2,
                        "last_arrive_step": 4,
                        "event_count": 3,
                    },
                    "total_events": 3,
                    "identification_status": IDENTIFICATION_STATUS_NOT_FORMALLY_IDENTIFIED,
                    "assumptions": [ASSUMPTION_CAUSAL_SUFFICIENCY],
                },
                "provenance": {
                    "algorithm": "PCMCI",
                    "graph_version": "CausalNodeV2",
                    "computation_time_ms": 8,
                    "server_name": "abel-cap",
                    "server_version": "0.1.0",
                    "cap_spec_version": "0.2.2",
                },
            },
        )

    async def _run() -> None:
        client = AsyncAbelCAPClient("https://cap.example", transport=httpx.MockTransport(_handler))
        response = await client.intervene_time_lag(
            treatment_node="NVDA_close",
            treatment_value=0.05,
            outcome_node="SONY_close",
            horizon_steps=24,
        )
        await client.aclose()

        assert response.result.reasoning_mode == REASONING_MODE_GRAPH_PROPAGATION
        assert response.result.outcome_summary is not None
        assert response.result.outcome_summary.node_id == "SONY_close"

    __import__("asyncio").run(_run())


def test_abel_cap_client_time_lag_helper_can_send_request_headers() -> None:
    async def _handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer extension-key"
        return httpx.Response(
            200,
            json={
                "cap_version": "0.2.2",
                "request_id": "req-time-lag",
                "verb": "extensions.abel.intervene_time_lag",
                "status": "success",
                "result": {
                    "treatment_node": "NVDA_close",
                    "treatment_value": 0.05,
                    "outcome_node": "SONY_close",
                    "model": "linear",
                    "delta_unit": "delta",
                    "horizon_steps": 24,
                    "reasoning_mode": REASONING_MODE_GRAPH_PROPAGATION,
                    "outcome_summary": {
                        "node_id": "SONY_close",
                        "final_cumulative_effect": 0.0,
                        "first_arrive_step": 0,
                        "last_arrive_step": 0,
                        "event_count": 0,
                    },
                    "total_events": 0,
                    "identification_status": IDENTIFICATION_STATUS_NOT_FORMALLY_IDENTIFIED,
                    "assumptions": [ASSUMPTION_CAUSAL_SUFFICIENCY],
                },
                "provenance": {
                    "algorithm": "PCMCI",
                    "graph_version": "CausalNodeV2",
                    "computation_time_ms": 8,
                    "server_name": "abel-cap",
                    "server_version": "0.1.0",
                    "cap_spec_version": "0.2.2",
                },
            },
        )

    async def _run() -> None:
        client = AsyncAbelCAPClient("https://cap.example", transport=httpx.MockTransport(_handler))
        response = await client.intervene_time_lag(
            treatment_node="NVDA_close",
            treatment_value=0.05,
            outcome_node="SONY_close",
            horizon_steps=24,
            headers={"Authorization": "Bearer extension-key"},
        )
        await client.aclose()

        assert response.verb == "extensions.abel.intervene_time_lag"

    __import__("asyncio").run(_run())


def test_cap_client_example_intervene_time_lag_command_returns_json_shape(monkeypatch) -> None:
    async def _handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/cap"
        assert json.loads(request.content.decode("utf-8")) == {
            "cap_version": "0.2.2",
            "options": {"response_detail": "summary"},
            "verb": "extensions.abel.intervene_time_lag",
            "params": {
                "treatment_node": "NVDA_close",
                "treatment_value": 0.05,
                "outcome_node": "SONY_close",
                "horizon_steps": 24,
                "model": "linear",
            },
        }
        return httpx.Response(
            200,
            json={
                "cap_version": "0.2.2",
                "request_id": "req-time-lag-cli",
                "verb": "extensions.abel.intervene_time_lag",
                "status": "success",
                "result": {
                    "treatment_node": "NVDA_close",
                    "treatment_value": 0.05,
                    "outcome_node": "SONY_close",
                    "model": "linear",
                    "delta_unit": "delta",
                    "horizon_steps": 24,
                    "reasoning_mode": REASONING_MODE_GRAPH_PROPAGATION,
                    "outcome_summary": {
                        "node_id": "SONY_close",
                        "final_cumulative_effect": 0.08,
                        "first_arrive_step": 2,
                        "last_arrive_step": 4,
                        "event_count": 3,
                    },
                    "total_events": 3,
                    "identification_status": IDENTIFICATION_STATUS_NOT_FORMALLY_IDENTIFIED,
                    "assumptions": [ASSUMPTION_CAUSAL_SUFFICIENCY],
                },
                "provenance": {
                    "algorithm": "PCMCI",
                    "graph_version": "CausalNodeV2",
                    "computation_time_ms": 8,
                    "server_name": "abel-cap",
                    "server_version": "0.1.0",
                    "cap_spec_version": "0.2.2",
                },
            },
        )

    original_init = AsyncCAPClient.__init__

    def _fake_init(self, base_url: str, **kwargs) -> None:
        original_init(self, base_url, transport=httpx.MockTransport(_handler), **kwargs)

    monkeypatch.setattr(AsyncCAPClient, "__init__", _fake_init)

    payload = __import__("asyncio").run(
        run_command(
            argparse.Namespace(
                base_url="https://cap.example",
                command="intervene-time-lag",
                treatment_node="NVDA_close",
                treatment_value=0.05,
                outcome_node="SONY_close",
                horizon_steps=24,
                model="linear",
            )
        )
    )

    assert payload["verb"] == "extensions.abel.intervene_time_lag"
    assert payload["result"]["reasoning_mode"] == REASONING_MODE_GRAPH_PROPAGATION
    assert payload["result"]["outcome_summary"]["node_id"] == "SONY_close"
