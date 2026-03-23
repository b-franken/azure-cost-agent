"""Interactive CLI REPL for local development."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from agent_framework.orchestrations import HandoffAgentUserRequest

from src.workflow import create_workflow


async def _read_input(prompt: str) -> str:
    return (await asyncio.to_thread(input, prompt)).strip()


def _extract_pending(events: list[Any]) -> list[Any]:
    pending = []
    for event in events:
        if event.type == "request_info" and isinstance(
            event.data, HandoffAgentUserRequest
        ):
            pending.append(event)
            for msg in event.data.agent_response.messages[-3:]:
                if msg.text:
                    print(f"\n{msg.author_name}: {msg.text}")
    return pending


async def _run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        builder, azure_clients = create_workflow(inject_clients=True)
    except ValueError as e:
        print(str(e))
        return

    workflow = builder.build()

    print("=" * 60)
    print("Azure Cost Agent")
    print(f"Subscriptions: {', '.join(azure_clients.subscription_ids)}")
    if azure_clients.management_group_id:
        print(f"Management Group: {azure_clients.management_group_id}")
    print("Type 'exit' to stop")
    print("=" * 60)
    print()

    user_input = await _read_input("You > ")
    if not user_input or user_input.lower() in {"exit", "quit"}:
        return

    while True:
        events = [e async for e in workflow.run(user_input, stream=True)]
        pending = _extract_pending(events)

        while pending:
            try:
                user_input = await _read_input("\nYou > ")
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                return

            if user_input.lower() in {"exit", "quit"}:
                print("Goodbye!")
                return

            responses = {
                req.request_id: HandoffAgentUserRequest.create_response(user_input)
                for req in pending
            }
            events = [e async for e in workflow.run(stream=True, responses=responses)]
            pending = _extract_pending(events)

        try:
            user_input = await _read_input("\nYou > ")
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            return

        if user_input.lower() in {"exit", "quit"}:
            print("Goodbye!")
            return


def run_cli() -> None:
    asyncio.run(_run())
