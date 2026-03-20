# Security Policy

## Reporting A Vulnerability

Please do not open a public issue for suspected security problems.

Instead, report privately to the project maintainers with:

- a clear description of the issue
- affected endpoints or files
- reproduction steps or proof of concept
- impact assessment
- any suggested mitigation

If the issue involves credentials, rotate them first when possible.

## What Counts As Sensitive In This Repo

Please treat the following as sensitive:

- real `CAP_GATEWAY_API_KEY` values
- internal gateway base URLs that are not meant for public docs
- raw upstream payloads that may include hidden graph fields
- logs or traces that expose production headers or internal topology

## Safe Contribution Guidelines

When contributing:

- use placeholder keys in examples and screenshots
- do not paste production secrets into issues or pull requests
- preserve the hidden-field disclosure policy in `abel_cap_server/cap/disclosure.py`
- avoid documenting internal-only upstream semantics as if they were public guarantees

## Scope

Security-sensitive areas in this repository include:

- request header forwarding to the upstream gateway
- fallback authorization via `CAP_GATEWAY_API_KEY`
- public response sanitization of hidden fields
- error translation that should not leak internal details

## Supported Fix Target

Unless maintainers say otherwise, prepare security fixes against the latest default branch so they can be reviewed and released quickly.
