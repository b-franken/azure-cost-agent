"""Tests for AI client factory."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from src.factory import create_client


class TestCreateClient:
    @patch("src.factory.AzureOpenAIResponsesClient")
    @patch.dict(os.environ, {"AZURE_OPENAI_API_KEY": "test-key"}, clear=False)
    def test_api_key_path(self, mock_client_cls: MagicMock) -> None:
        create_client()
        mock_client_cls.assert_called_once()
        _, kwargs = mock_client_cls.call_args
        assert kwargs["api_key"] == "test-key"

    @patch("src.factory.AzureOpenAIResponsesClient")
    @patch("src.factory.get_credential")
    @patch.dict(
        os.environ,
        {
            "AZURE_AI_PROJECT_ENDPOINT": "https://hub.openai.azure.com/api/projects/p1",
            "AZURE_OPENAI_API_KEY": "",
        },
        clear=False,
    )
    def test_project_endpoint_path(
        self, mock_cred: MagicMock, mock_client_cls: MagicMock
    ) -> None:
        create_client()
        _, kwargs = mock_client_cls.call_args
        assert "project_endpoint" in kwargs

    @patch("src.factory.AzureOpenAIResponsesClient")
    @patch("src.factory.get_credential")
    @patch.dict(
        os.environ,
        {
            "AZURE_AI_PROJECT_ENDPOINT": "https://hub.openai.azure.com/",
            "AZURE_OPENAI_API_KEY": "",
        },
        clear=False,
    )
    def test_generic_endpoint_path(
        self, mock_cred: MagicMock, mock_client_cls: MagicMock
    ) -> None:
        create_client()
        _, kwargs = mock_client_cls.call_args
        assert "endpoint" in kwargs

    @patch("src.factory.AzureOpenAIResponsesClient")
    @patch("src.factory.get_credential")
    @patch.dict(
        os.environ,
        {"AZURE_AI_PROJECT_ENDPOINT": "", "AZURE_OPENAI_API_KEY": ""},
        clear=False,
    )
    def test_default_path(
        self, mock_cred: MagicMock, mock_client_cls: MagicMock
    ) -> None:
        create_client()
        _, kwargs = mock_client_cls.call_args
        assert "endpoint" not in kwargs
        assert "project_endpoint" not in kwargs
        assert "api_key" not in kwargs
