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


def make_block(type_, **kwargs):
    block = MagicMock()
    block.type = type_
    for k, v in kwargs.items():
        setattr(block, k, v)
    return block


def make_message(content_blocks, stop_reason="end_turn", usage_kwargs=None):
    message = MagicMock()
    message.content = content_blocks
    message.stop_reason = stop_reason
    usage = MagicMock()
    defaults = dict(
        input_tokens=10,
        output_tokens=5,
        cache_creation_input_tokens=None,
        cache_read_input_tokens=None,
    )
    defaults.update(usage_kwargs or {})
    for k, v in defaults.items():
        setattr(usage, k, v)
    message.usage = usage
    message.model_dump.return_value = {"id": "msg_123", "role": "assistant"}
    return message


class TestFlattenResponse:
    def test_text_only_response(self, mock_anthropic):
        from ansible_collections.aknochow.claude.plugins.modules.message import (
            flatten_response,
        )

        message = make_message([make_block("text", text="hello world")])
        result = flatten_response(message)

        assert result["text"] == "hello world"
        assert result["tool_calls"] == []
        assert result["stop_reason"] == "end_turn"
        assert result["usage"]["input_tokens"] == 10
        assert "structured" not in result

    def test_tool_use_response(self, mock_anthropic):
        from ansible_collections.aknochow.claude.plugins.modules.message import (
            flatten_response,
        )

        message = make_message(
            [make_block("tool_use", id="tu_1", name="get_weather", input={"city": "SF"})],
            stop_reason="tool_use",
        )
        result = flatten_response(message)

        assert result["tool_calls"] == [{"id": "tu_1", "name": "get_weather", "input": {"city": "SF"}}]
        assert result["stop_reason"] == "tool_use"

    def test_structured_output_parsed(self, mock_anthropic):
        from ansible_collections.aknochow.claude.plugins.modules.message import (
            flatten_response,
        )

        message = make_message([make_block("text", text='{"name": "bug-1", "severity": "high"}')])
        result = flatten_response(message)

        assert result["structured"] == {"name": "bug-1", "severity": "high"}

    def test_non_json_text_has_no_structured_key(self, mock_anthropic):
        from ansible_collections.aknochow.claude.plugins.modules.message import (
            flatten_response,
        )

        message = make_message([make_block("text", text="just plain text")])
        result = flatten_response(message)

        assert "structured" not in result

    def test_cache_usage_fields(self, mock_anthropic):
        from ansible_collections.aknochow.claude.plugins.modules.message import (
            flatten_response,
        )

        message = make_message(
            [make_block("text", text="hi")],
            usage_kwargs={"cache_creation_input_tokens": 100, "cache_read_input_tokens": 50},
        )
        result = flatten_response(message)

        assert result["usage"]["cache_creation_input_tokens"] == 100
        assert result["usage"]["cache_read_input_tokens"] == 50


class TestMainReportsChanged:
    def test_main_reports_changed_false(self, mock_anthropic, monkeypatch):
        from ansible_collections.aknochow.claude.plugins.modules import message as message_module

        fake_module = MagicMock()
        fake_module.params = {
            "model": "claude-sonnet-5",
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 100,
            "system": None,
            "cache_system": False,
            "temperature": None,
            "top_p": None,
            "top_k": None,
            "stop_sequences": None,
            "tools": None,
            "tool_choice": None,
            "output_config": None,
            "metadata": None,
            "provider": "anthropic",
            "api_key": "sk-ant-test",
            "auth_token": None,
            "base_url": None,
            "timeout": 120.0,
            "max_retries": 2,
        }
        mock_anthropic.Anthropic.return_value.messages.create.return_value = make_message(
            [make_block("text", text="hi")]
        )
        monkeypatch.setattr(message_module, "AnsibleModule", lambda **kwargs: fake_module)

        message_module.main()

        fake_module.exit_json.assert_called_once()
        # Regression check: a query call never mutates infrastructure
        # state, so this must always be False -- not just "whatever the
        # response happened to produce". Fails against the pre-fix
        # hardcoded changed=True.
        assert fake_module.exit_json.call_args.kwargs["changed"] is False
