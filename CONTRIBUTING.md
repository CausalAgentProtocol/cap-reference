# Contributing

## Branch Naming

Format:

```text
<type>/<short-description>
```

Examples:

- `feat/user-login`
- `fix/token-refresh`
- `docs/api-auth-guide`
- `refactor/split-router-logic`
- `test/add-login-tests`
- `chore/update-dependencies`

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

Format:

```text
<type>: <short summary>
```

Examples:

- `feat: add JWT login endpoint`
- `fix: handle empty token response`
- `docs: update auth setup guide`
- `refactor: split auth logic into service layer`
- `test: add unit tests for token parser`

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

- do not use vague prefixes like `add:` or `update:`
- use a clear action-oriented summary
- keep the message concise
