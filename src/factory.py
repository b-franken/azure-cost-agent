"""Agent factory — creates the AI client and agents."""

from __future__ import annotations

import logging
import os

from agent_framework.azure import AzureOpenAIResponsesClient

from src.azure_clients import get_credential

logger = logging.getLogger(__name__)


def create_client() -> AzureOpenAIResponsesClient:
    """Create an AzureOpenAIResponsesClient with explicit credential selection."""
    deployment_name = (
        os.getenv("AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME") or "gpt-4.1-mini"
    )
    endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")

    if api_key:
        return AzureOpenAIResponsesClient(
            deployment_name=deployment_name,
            api_key=api_key,
        )

    credential = get_credential()

    if endpoint and "/api/projects/" in endpoint:
        return AzureOpenAIResponsesClient(
            deployment_name=deployment_name,
            credential=credential,
            project_endpoint=endpoint,
        )

    if endpoint:
        return AzureOpenAIResponsesClient(
            deployment_name=deployment_name,
            credential=credential,
            endpoint=endpoint,
        )

    return AzureOpenAIResponsesClient(
        deployment_name=deployment_name,
        credential=credential,
    )
