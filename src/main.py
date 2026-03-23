"""Azure Cost Agent — entry point.

Usage:
    CLI mode:    uv run python -m src.main
    Hosted mode: FOUNDRY_HOSTED=true uv run python -m src.main
"""

from __future__ import annotations

import logging
import os

from src.workflow import create_workflow


def _run_hosted() -> None:
    from azure.ai.agentserver.agentframework import from_agent_framework

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    builder, _ = create_workflow(inject_clients=True)
    from_agent_framework(builder.build).run()


def main() -> None:
    if os.getenv("FOUNDRY_HOSTED"):
        _run_hosted()
    else:
        from src.cli import run_cli

        run_cli()


if __name__ == "__main__":
    main()
