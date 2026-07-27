# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def mock_anthropic():
    mock_sdk = MagicMock()
    mock_sdk.Anthropic = MagicMock()
    mock_sdk.AnthropicVertex = MagicMock()
    mock_sdk.AnthropicBedrock = MagicMock()
    mock_sdk.AnthropicError = type("AnthropicError", (Exception,), {})
    sys.modules["anthropic"] = mock_sdk
    yield mock_sdk
    sys.modules.pop("anthropic", None)


class TestProviderArgspec:
    def test_provider_default(self, mock_anthropic):
        from ansible_collections.aknochow.claude.plugins.module_utils.claude_client import (
            PROVIDER_ARGSPEC,
        )

        assert PROVIDER_ARGSPEC["provider"]["default"] == "anthropic"
        assert PROVIDER_ARGSPEC["provider"]["choices"] == ["anthropic", "vertex", "bedrock"]

    def test_secrets_are_no_log(self, mock_anthropic):
        from ansible_collections.aknochow.claude.plugins.module_utils.claude_client import (
            PROVIDER_ARGSPEC,
        )

        for key in ("api_key", "auth_token", "access_token", "aws_access_key", "aws_secret_key", "aws_session_token"):
            assert PROVIDER_ARGSPEC[key]["no_log"] is True


class TestGetClient:
    def test_anthropic_provider(self, mock_anthropic):
        from ansible_collections.aknochow.claude.plugins.module_utils.claude_client import (
            get_client,
        )

        module = MagicMock()
        module.params = {
            "provider": "anthropic",
            "api_key": "sk-ant-test",
            "auth_token": None,
            "base_url": None,
            "timeout": 120.0,
            "max_retries": 2,
        }

        get_client(module)
        mock_anthropic.Anthropic.assert_called_once()
        call_kwargs = mock_anthropic.Anthropic.call_args.kwargs
        assert call_kwargs["api_key"] == "sk-ant-test"
        assert call_kwargs["timeout"] == 120.0

    def test_anthropic_requires_auth(self, mock_anthropic):
        from ansible_collections.aknochow.claude.plugins.module_utils.claude_client import (
            get_client,
        )

        module = MagicMock()
        module.params = {
            "provider": "anthropic",
            "api_key": None,
            "auth_token": None,
            "base_url": None,
            "timeout": 120.0,
            "max_retries": 2,
        }

        get_client(module)
        module.fail_json.assert_called_once()
        assert "api_key" in module.fail_json.call_args.kwargs["msg"]

    def test_vertex_provider(self, mock_anthropic):
        from ansible_collections.aknochow.claude.plugins.module_utils.claude_client import (
            get_client,
        )

        module = MagicMock()
        module.params = {
            "provider": "vertex",
            "region": "us-east5",
            "project_id": "my-project",
            "access_token": None,
            "base_url": None,
            "timeout": 120.0,
            "max_retries": 2,
        }

        get_client(module)
        mock_anthropic.AnthropicVertex.assert_called_once()
        call_kwargs = mock_anthropic.AnthropicVertex.call_args.kwargs
        assert call_kwargs["region"] == "us-east5"
        assert call_kwargs["project_id"] == "my-project"

    def test_vertex_requires_region_and_project(self, mock_anthropic):
        from ansible_collections.aknochow.claude.plugins.module_utils.claude_client import (
            get_client,
        )

        module = MagicMock()
        module.params = {
            "provider": "vertex",
            "region": None,
            "project_id": None,
            "access_token": None,
            "base_url": None,
            "timeout": 120.0,
            "max_retries": 2,
        }

        get_client(module)
        module.fail_json.assert_called_once()

    def test_bedrock_provider(self, mock_anthropic):
        from ansible_collections.aknochow.claude.plugins.module_utils.claude_client import (
            get_client,
        )

        module = MagicMock()
        module.params = {
            "provider": "bedrock",
            "aws_access_key": "AKIA...",
            "aws_secret_key": "secret",
            "aws_region": "us-east-1",
            "aws_profile": None,
            "aws_session_token": None,
            "base_url": None,
            "timeout": 120.0,
            "max_retries": 2,
        }

        get_client(module)
        mock_anthropic.AnthropicBedrock.assert_called_once()
