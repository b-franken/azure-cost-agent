"""Session memory using Agent Framework's InMemoryHistoryProvider.

Provides multi-turn conversation context so users can ask follow-up
questions like "what do you mean by that disk?" and the agent remembers.

See: https://learn.microsoft.com/agent-framework/agents/conversations/context-providers
"""

from __future__ import annotations

from agent_framework import InMemoryHistoryProvider


def create_history_provider() -> InMemoryHistoryProvider:
    return InMemoryHistoryProvider("in_memory", load_messages=True)
