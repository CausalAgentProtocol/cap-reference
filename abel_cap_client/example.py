from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence
from typing import Any

from abel_cap_client.client import AsyncAbelCAPClient


def _parse_header_argument(value: str) -> tuple[str, str]:
    name, separator, header_value = value.partition(":")
    if not separator:
        raise argparse.ArgumentTypeError("Headers must use 'Name: Value' format.")

    normalized_name = name.strip()
    normalized_value = header_value.strip()
    if not normalized_name:
        raise argparse.ArgumentTypeError("Header name cannot be empty.")
    if not normalized_value:
        raise argparse.ArgumentTypeError("Header value cannot be empty.")
    return normalized_name, normalized_value


def _build_headers(header_pairs: Sequence[tuple[str, str]] | None) -> dict[str, str] | None:
    if not header_pairs:
        return None
    return {name: value for name, value in header_pairs}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cap_client",
        description="Example CAP client built on top of cap.client.",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8081",
        help="CAP server base URL.",
    )
    parser.add_argument(
        "--header",
        dest="headers",
        action="append",
        default=[],
        metavar="NAME:VALUE",
        type=_parse_header_argument,
        help=(
            "Optional request header to send to the CAP server, for example "
            "\"Authorization: Bearer <api-key>\". Repeatable. If Authorization "
            "is omitted, the server-side CAP_GATEWAY_API_KEY fallback can still be used."
        ),
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("capabilities", help="Fetch the capability card via meta.capabilities.")

    neighbors = subparsers.add_parser("neighbors", help="Call graph.neighbors.")
    neighbors.add_argument("node_id")
    neighbors.add_argument(
        "--scope",
        choices=("parents", "children"),
        default="parents",
    )
    neighbors.add_argument("--max-neighbors", type=int, default=5)

    paths = subparsers.add_parser("paths", help="Call graph.paths.")
    paths.add_argument("source_node_id")
    paths.add_argument("target_node_id")
    paths.add_argument("--max-paths", type=int, default=3)

    observe = subparsers.add_parser("observe", help="Call observe.predict.")
    observe.add_argument("target_node")

    markov_blanket = subparsers.add_parser(
        "markov-blanket",
        help="Call graph.markov_blanket.",
    )
    markov_blanket.add_argument("target_node")
    markov_blanket.add_argument("--max-neighbors", type=int, default=10)

    intervene_time_lag = subparsers.add_parser(
        "intervene-time-lag",
        help="Call Abel's time-lag intervention extension.",
    )
    intervene_time_lag.add_argument("treatment_node")
    intervene_time_lag.add_argument("treatment_value", type=float)
    intervene_time_lag.add_argument("--outcome-node")
    intervene_time_lag.add_argument("--horizon-steps", type=int, default=24)
    intervene_time_lag.add_argument("--model", default="linear")

    return parser


async def run_command(args: argparse.Namespace) -> dict[str, Any]:
    client = AsyncAbelCAPClient(args.base_url)
    headers = _build_headers(getattr(args, "headers", None))
    try:
        if args.command == "capabilities":
            response = await client.meta_capabilities(headers=headers)
        elif args.command == "neighbors":
            response = await client.graph_neighbors(
                node_id=args.node_id,
                scope=args.scope,
                max_neighbors=args.max_neighbors,
                headers=headers,
            )
        elif args.command == "paths":
            response = await client.graph_paths(
                source_node_id=args.source_node_id,
                target_node_id=args.target_node_id,
                max_paths=args.max_paths,
                headers=headers,
            )
        elif args.command == "observe":
            response = await client.observe_predict(
                target_node=args.target_node,
                headers=headers,
            )
        elif args.command == "markov-blanket":
            response = await client.graph_markov_blanket(
                node_id=args.target_node,
                max_neighbors=args.max_neighbors,
                headers=headers,
            )
        elif args.command == "intervene-time-lag":
            response = await client.intervene_time_lag(
                treatment_node=args.treatment_node,
                treatment_value=args.treatment_value,
                outcome_node=args.outcome_node,
                horizon_steps=args.horizon_steps,
                model=args.model,
                headers=headers,
            )
        else:
            raise ValueError(f"Unsupported command: {args.command}")

        return response.model_dump(mode="json", by_alias=True, exclude_none=True)
    finally:
        await client.aclose()


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    payload = asyncio.run(run_command(args))
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0
