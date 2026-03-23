# Contributing

## Development setup

```bash
pip install uv
uv sync
cp .env.example .env  # fill in your values
az login
```

## Before submitting

```bash
make check  # runs lint, format, typecheck, and tests
```

All checks must pass. The CI pipeline runs the same commands.

## Code style

- Python 3.13+, strict mypy, ruff linting
- No comments needed — code should be self-explanatory
- No magic numbers — use `src/config.py` for configurable values
- All Azure API calls go through `src/azure_clients.py`
- New agent tools use the `@tool` decorator from `agent_framework`

## Adding a new agent

1. Create `src/agents/your_agent.py` with `INSTRUCTIONS`, `DESCRIPTION`, and `@tool` functions
2. Register in `AGENTS_CONFIG` in `src/workflow.py`
3. Add tests in `tests/test_your_agent.py`
4. Run `make check`
