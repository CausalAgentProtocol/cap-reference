# Contributing

Thanks for contributing to `cap-reference`.

This repository is the public CAP HTTP wrapper around Abel primitives. The best contributions keep that boundary clear: public protocol surface here, causal computation upstream.

## Before You Start

Please read:

- `README.md`
- `docs/architecture.md`
- `docs/api-reference.md`
- `docs/development.md`

If you are changing the public surface, treat the Capability Card and public docs as part of the code change.

## Project Principles

Keep these rules in mind:

- keep the service thin
- do not re-implement Abel compute logic here
- keep gateway HTTP calls inside `abel_cap_server/clients/abel_gateway_client.py`
- keep public verb registration centralized in `abel_cap_server/cap/catalog.py`
- enforce disclosure policy in code, not only in docs

## Development Setup

Install dependencies:

```bash
make install
```

Create local config:

```bash
make init-env
```

Start the app:

```bash
make dev
```

Useful validation commands:

```bash
make test
make lint
make check
```

Preferred targeted validation:

```bash
uv run pytest -q tests/test_cap_protocol_sdk.py tests/test_cap_graph.py tests/test_health.py tests/test_config.py tests/test_cap_client_example.py
uv run python -m ruff check abel_cap_server tests abel_cap_client
```

## Branch Naming

Use:

```text
<type>/<short-description>
```

Examples:

- `feat/add-capability-card-binding`
- `fix/normalize-bearer-header`
- `docs/expand-api-reference`
- `refactor/centralize-dispatch-registry`
- `test/add-counterfactual-contract-coverage`

Allowed types:

- `feat`
- `fix`
- `docs`
- `refactor`
- `test`
- `chore`
- `perf`
- `style`
- `revert`
- `hotfix`
- `build`

Rules:

- use lowercase only
- use `-` to separate words
- keep it short and descriptive

## Commit Messages

Use:

```text
<type>: <short summary>
```

Examples:

- `feat: add graph.markov_blanket adapter`
- `fix: reject unsupported graph versions`
- `docs: expand architecture and API guides`
- `refactor: keep capability card metadata in catalog`
- `test: cover gateway authorization fallback`

Allowed types:

- `feat`
- `fix`
- `docs`
- `refactor`
- `test`
- `chore`
- `perf`
- `style`
- `revert`
- `build`

Notes:

- avoid vague prefixes like `add:` or `update:`
- use a clear action-oriented summary
- keep the message concise

## Change Workflow

For CAP surface changes, prefer this order:

1. confirm the behavior belongs in this wrapper
2. add or update tests under `tests/`
3. update DTOs
4. update adapter logic
5. update gateway client logic if needed
6. register the surface in `abel_cap_server/cap/catalog.py`
7. update docs and examples

Layering guidance:

- protocol-generic contracts belong in `cap-protocol`
- Abel-only contracts belong in `abel_cap_server/cap/contracts/extensions.py`
- upstream compute semantics belong in the upstream Abel engine

## Pull Request Expectations

A good PR should:

- explain the user-facing or protocol-facing change
- call out any Capability Card impact
- mention which tests were run
- update docs when behavior changed
- avoid unrelated refactors

If your PR changes a public verb, include:

- request shape changes
- response shape changes
- disclosure or honesty changes
- upstream mapping changes

## Documentation Expectations

Update documentation whenever the public contract changes.

Common files to update:

- `README.md`
- `docs/api-reference.md`
- `docs/architecture.md`
- `docs/configuration.md`
- `docs/development.md`

## Security And Secrets

- never commit real gateway keys or internal upstream URLs
- use placeholder values in examples
- follow `SECURITY.md` for reporting security issues
