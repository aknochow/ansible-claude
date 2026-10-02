# SPDX-License-Identifier: Apache-2.0

"""Lock the Anthropic and Claude Agent SDK surface this collection calls.

Imports the installed SDKs. Mocked unit tests do not see a removed
constructor or a renamed query helper.
"""

from __future__ import annotations

from importlib.metadata import version

from packaging.version import Version


def test_installed_sdks_meet_the_collection_floor():
    assert Version(version("anthropic")) >= Version("1.11.0")
    assert Version(version("claude-agent-sdk")) >= Version("0.2.163")


def test_message_clients_and_agent_query_still_import():
    from anthropic import Anthropic, AnthropicBedrock, AnthropicVertex
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKError, query

    assert callable(Anthropic)
    assert callable(AnthropicVertex)
    assert callable(AnthropicBedrock)
    assert hasattr(Anthropic, "messages") or "messages" in getattr(Anthropic, "__annotations__", {})
    assert callable(query)
    assert callable(ClaudeAgentOptions)
    assert issubclass(ClaudeSDKError, Exception)
