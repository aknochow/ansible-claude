# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

DEFAULT_MODULE_PARAMS = {
    "prompt": "hello",
    "system_prompt": None,
    "model": None,
    "fallback_model": None,
    "effort": None,
    "thinking": None,
    "output_format": None,
    "tools": [],
    "allowed_tools": None,
    "disallowed_tools": None,
    "max_turns": 1,
    "max_budget_usd": None,
    "cwd": None,
    "setting_sources": [],
    "add_dirs": None,
    "settings": None,
    "timeout": 300.0,
}


class FakeClaudeSDKError(Exception):
    pass


@pytest.fixture(autouse=True)
def mock_claude_agent_sdk():
    mock_sdk = MagicMock()
    mock_sdk.ClaudeAgentOptions = MagicMock(side_effect=lambda **kw: kw)
    mock_sdk.ClaudeSDKError = FakeClaudeSDKError
    # query is patched per-test via monkeypatch on the module under test;
    # give it a harmless default so import-time access doesn't explode.
    mock_sdk.query = MagicMock()
    sys.modules["claude_agent_sdk"] = mock_sdk
    yield mock_sdk
    sys.modules.pop("claude_agent_sdk", None)


def make_text_block(text):
    block = MagicMock()
    block.__class__.__name__ = "TextBlock"
    type(block).__name__ = "TextBlock"
    block.text = text
    return block


def make_tool_use_block(id_, name, input_):
    block = MagicMock()
    type(block).__name__ = "ToolUseBlock"
    block.id = id_
    block.name = name
    block.input = input_
    return block


def make_assistant_message(content_blocks, model="claude-sonnet-5", stop_reason=None):
    msg = MagicMock()
    type(msg).__name__ = "AssistantMessage"
    msg.content = content_blocks
    msg.model = model
    msg.stop_reason = stop_reason
    return msg


def make_result_message(
    total_cost_usd=0.001,
    usage=None,
    stop_reason=None,
    structured_output=None,
):
    msg = MagicMock()
    type(msg).__name__ = "ResultMessage"
    msg.total_cost_usd = total_cost_usd
    msg.usage = usage or {}
    msg.stop_reason = stop_reason
    msg.structured_output = structured_output
    return msg


class TestNormalizeUsage:
    def test_defaults_missing_values_to_zero(self):
        from ansible_collections.aknochow.claude.plugins.modules.agent import (
            normalize_usage,
        )

        result = normalize_usage({})

        assert result == {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "thinking_tokens": 0,
            "total_tokens": 0,
        }

    def test_none_usage_defaults_to_zero(self):
        from ansible_collections.aknochow.claude.plugins.modules.agent import (
            normalize_usage,
        )

        result = normalize_usage(None)

        assert result["total_tokens"] == 0

    def test_maps_sdk_field_names(self):
        from ansible_collections.aknochow.claude.plugins.modules.agent import (
            normalize_usage,
        )

        usage = {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_creation_input_tokens": 20,
            "cache_read_input_tokens": 10,
            "output_tokens_details": {"thinking_tokens": 5},
        }
        result = normalize_usage(usage)

        assert result == {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_write_tokens": 20,
            "cache_read_tokens": 10,
            "thinking_tokens": 5,
            # input 100 + output 50. thinking (5) is a subset of
            # output_tokens, not an additional bucket -- adding it
            # here is what the original 155 got wrong.
            "total_tokens": 150,
        }


class TestNormalizeStopReason:
    def test_end_turn_passthrough(self):
        from ansible_collections.aknochow.claude.plugins.modules.agent import (
            normalize_stop_reason,
        )

        assert normalize_stop_reason("end_turn") == "end_turn"

    def test_none_defaults_to_end_turn(self):
        from ansible_collections.aknochow.claude.plugins.modules.agent import (
            normalize_stop_reason,
        )

        assert normalize_stop_reason(None) == "end_turn"

    def test_max_turns_maps_to_max_tokens(self):
        from ansible_collections.aknochow.claude.plugins.modules.agent import (
            normalize_stop_reason,
        )

        assert normalize_stop_reason("max_turns") == "max_tokens"

    def test_unknown_value_passed_through_verbatim(self):
        # Regression guard: an unrecognized SDK/API stop reason must not be
        # silently dropped or coerced to a generic value -- it should surface
        # as-is so callers can see something unexpected happened.
        from ansible_collections.aknochow.claude.plugins.modules.agent import (
            normalize_stop_reason,
        )

        assert normalize_stop_reason("some_future_reason") == "some_future_reason"


class TestFlattenMessages:
    def test_text_only(self):
        from ansible_collections.aknochow.claude.plugins.modules.agent import (
            flatten_messages,
        )

        messages = [
            make_assistant_message([make_text_block("hello ")], stop_reason="end_turn"),
            make_assistant_message([make_text_block("world")]),
            make_result_message(usage={"input_tokens": 10, "output_tokens": 5}),
        ]
        result = flatten_messages(messages)

        assert result["text"] == "hello world"
        assert result["tool_calls"] == []
        assert result["stop_reason"] == "end_turn"
        assert result["resolved_model"] == "claude-sonnet-5"
        assert result["cost_usd"] == 0.001
        assert result["usage"] == {"input_tokens": 10, "output_tokens": 5}
        assert result["usage_normalized"]["input_tokens"] == 10
        assert "structured" not in result

    def test_tool_use(self):
        from ansible_collections.aknochow.claude.plugins.modules.agent import (
            flatten_messages,
        )

        messages = [
            make_assistant_message(
                [make_tool_use_block("tu_1", "get_weather", {"city": "SF"})],
                stop_reason="tool_use",
            ),
            make_result_message(),
        ]
        result = flatten_messages(messages)

        assert result["tool_calls"] == [{"id": "tu_1", "name": "get_weather", "input": {"city": "SF"}}]
        assert result["stop_reason"] == "tool_use"

    def test_structured_output_populated_when_requested(self):
        from ansible_collections.aknochow.claude.plugins.modules.agent import (
            flatten_messages,
        )

        messages = [
            make_assistant_message([make_text_block('{"name": "x"}')]),
            make_result_message(structured_output={"name": "x"}),
        ]
        result = flatten_messages(messages, parse_structured=True)

        assert result["structured"] == {"name": "x"}

    def test_structured_output_absent_when_not_requested(self):
        # Regression guard: even if the SDK happens to populate
        # structured_output, this module must not surface it unless the
        # caller actually set output_format -- matches the RETURN doc's
        # claim that `structured` is only returned "when output_format is set".
        from ansible_collections.aknochow.claude.plugins.modules.agent import (
            flatten_messages,
        )

        messages = [
            make_assistant_message([make_text_block("hi")]),
            make_result_message(structured_output={"name": "x"}),
        ]
        result = flatten_messages(messages, parse_structured=False)

        assert "structured" not in result

    def test_no_result_message_defaults_cost_and_usage(self):
        from ansible_collections.aknochow.claude.plugins.modules.agent import (
            flatten_messages,
        )

        messages = [make_assistant_message([make_text_block("hi")])]
        result = flatten_messages(messages)

        assert result["cost_usd"] is None
        assert result["usage"] == {}
        assert result["usage_normalized"]["total_tokens"] == 0


class TestBuildOptions:
    def test_tools_default_empty_list(self, mock_claude_agent_sdk):
        from ansible_collections.aknochow.claude.plugins.modules.agent import (
            build_options,
        )

        fake_module = MagicMock()
        fake_module.params = dict(DEFAULT_MODULE_PARAMS)

        kwargs = build_options(fake_module, mock_claude_agent_sdk.ClaudeAgentOptions)

        assert kwargs["tools"] == []

    def test_optional_params_omitted_when_none(self, mock_claude_agent_sdk):
        from ansible_collections.aknochow.claude.plugins.modules.agent import (
            build_options,
        )

        fake_module = MagicMock()
        fake_module.params = dict(DEFAULT_MODULE_PARAMS)

        kwargs = build_options(fake_module, mock_claude_agent_sdk.ClaudeAgentOptions)

        assert "system_prompt" not in kwargs
        assert "model" not in kwargs
        assert "output_format" not in kwargs

    def test_optional_params_passed_through_when_set(self, mock_claude_agent_sdk):
        from ansible_collections.aknochow.claude.plugins.modules.agent import (
            build_options,
        )

        fake_module = MagicMock()
        params = dict(DEFAULT_MODULE_PARAMS)
        params.update(
            system_prompt="be terse",
            model="claude-sonnet-5",
            max_budget_usd=0.25,
        )
        fake_module.params = params

        kwargs = build_options(fake_module, mock_claude_agent_sdk.ClaudeAgentOptions)

        assert kwargs["system_prompt"] == "be terse"
        assert kwargs["model"] == "claude-sonnet-5"
        assert kwargs["max_budget_usd"] == 0.25

    def test_setting_sources_defaults_to_empty_list(self, mock_claude_agent_sdk):
        # Regression guard: this module must never fall back to the SDK's own
        # default of loading every filesystem settings source (user/project/
        # local) -- that pulls a project's own CLAUDE.md/skills into context,
        # which is both a large, invisible token cost and a review-integrity
        # risk for the primary use case (dispatching review lenses over a
        # repo's own diff). setting_sources must always be passed explicitly,
        # never omitted the way the other optional params are.
        from ansible_collections.aknochow.claude.plugins.modules.agent import (
            build_options,
        )

        fake_module = MagicMock()
        fake_module.params = dict(DEFAULT_MODULE_PARAMS)

        kwargs = build_options(fake_module, mock_claude_agent_sdk.ClaudeAgentOptions)

        assert kwargs["setting_sources"] == []

    def test_setting_sources_explicit_override_passed_through(self, mock_claude_agent_sdk):
        from ansible_collections.aknochow.claude.plugins.modules.agent import (
            build_options,
        )

        fake_module = MagicMock()
        params = dict(DEFAULT_MODULE_PARAMS)
        params["setting_sources"] = ["project"]
        fake_module.params = params

        kwargs = build_options(fake_module, mock_claude_agent_sdk.ClaudeAgentOptions)

        assert kwargs["setting_sources"] == ["project"]


class TestMain:
    def _install_fake_module(self, monkeypatch, params, mock_query):
        from ansible_collections.aknochow.claude.plugins.modules import agent as agent_module

        fake_module = MagicMock()
        fake_module.params = params
        monkeypatch.setattr(agent_module, "AnsibleModule", lambda **kwargs: fake_module)
        return agent_module, fake_module

    def test_main_reports_changed_false(self, mock_claude_agent_sdk, monkeypatch):
        async def fake_query(*, prompt, options):
            yield make_assistant_message([make_text_block("hi")])
            yield make_result_message(usage={"input_tokens": 1, "output_tokens": 1})

        mock_claude_agent_sdk.query = fake_query

        agent_module, fake_module = self._install_fake_module(
            monkeypatch, dict(DEFAULT_MODULE_PARAMS), mock_claude_agent_sdk.query
        )

        agent_module.main()

        fake_module.exit_json.assert_called_once()
        # Regression check: a query call never mutates infrastructure
        # state, so this must always be False.
        assert fake_module.exit_json.call_args.kwargs["changed"] is False
        assert fake_module.exit_json.call_args.kwargs["text"] == "hi"

    def test_main_fails_cleanly_on_timeout(self, mock_claude_agent_sdk, monkeypatch):
        import asyncio

        async def hanging_query(*, prompt, options):
            await asyncio.sleep(10)
            yield make_assistant_message([make_text_block("too slow")])

        mock_claude_agent_sdk.query = hanging_query

        params = dict(DEFAULT_MODULE_PARAMS)
        params["timeout"] = 0.01
        agent_module, fake_module = self._install_fake_module(
            monkeypatch, params, mock_claude_agent_sdk.query
        )

        agent_module.main()

        fake_module.fail_json.assert_called_once()
        assert "timed out" in fake_module.fail_json.call_args.kwargs["msg"]
        fake_module.exit_json.assert_not_called()

    def test_main_fails_cleanly_on_sdk_error(self, mock_claude_agent_sdk, monkeypatch):
        async def erroring_query(*, prompt, options):
            for dummy in ():
                yield
            raise mock_claude_agent_sdk.ClaudeSDKError("rate limit exhausted")

        mock_claude_agent_sdk.query = erroring_query

        agent_module, fake_module = self._install_fake_module(
            monkeypatch, dict(DEFAULT_MODULE_PARAMS), mock_claude_agent_sdk.query
        )

        agent_module.main()

        fake_module.fail_json.assert_called_once()
        assert "rate limit exhausted" in fake_module.fail_json.call_args.kwargs["msg"]

    def test_main_fails_cleanly_when_sdk_not_installed(self, monkeypatch):
        from ansible_collections.aknochow.claude.plugins.modules import agent as agent_module

        # Setting sys.modules[name] = None is the documented way to force
        # `import claude_agent_sdk` to raise ImportError without actually
        # uninstalling the package -- popping the entry isn't enough since
        # Python would just re-import the real (installed) package and this
        # test would end up making a real SDK/CLI call instead of exercising
        # the "not installed" failure path.
        monkeypatch.setitem(sys.modules, "claude_agent_sdk", None)
        fake_module = MagicMock()
        fake_module.params = dict(DEFAULT_MODULE_PARAMS)
        monkeypatch.setattr(agent_module, "AnsibleModule", lambda **kwargs: fake_module)

        agent_module.main()

        fake_module.fail_json.assert_called_once()
        assert "claude-agent-sdk" in fake_module.fail_json.call_args.kwargs["msg"]


class TestNormalizeUsageIterations:
    """usage["iterations"] is the real per-turn record; the top-level scalars
    report only the FINAL turn.

    Regression guard for a real defect: a two-turn lens dispatch (one turn to
    answer, one to satisfy a forced structured-output tool call) reported
    input_tokens=4 on a diff review whose first turn carried the entire diff
    plus an ~800-line system prompt. Reading the top level silently under-counts
    input by three orders of magnitude, which makes any cost or efficiency
    comparison built on it meaningless.
    """

    def test_sums_across_iterations_not_final_turn(self):
        usage = {
            "input_tokens": 4,
            "output_tokens": 2960,
            "output_tokens_details": {"thinking_tokens": 1904},
            "iterations": [
                {"input_tokens": 13733, "output_tokens": 100,
                 "output_tokens_details": {"thinking_tokens": 1804}},
                {"input_tokens": 4, "output_tokens": 2860,
                 "output_tokens_details": {"thinking_tokens": 100}},
            ],
        }
        from ansible_collections.aknochow.claude.plugins.modules.agent import (
            normalize_usage,
        )

        result = normalize_usage(usage)
        assert result["input_tokens"] == 13737
        assert result["output_tokens"] == 2960
        assert result["thinking_tokens"] == 1904
        # thinking_tokens is a subset of output_tokens, not additive
        assert result["total_tokens"] == 13737 + 2960

    def test_falls_back_to_top_level_without_iterations(self):
        """An older SDK, or a shape change, must degrade to the previous
        behaviour rather than silently reporting zero."""
        usage = {
            "input_tokens": 1738,
            "output_tokens": 199,
            "output_tokens_details": {"thinking_tokens": 190},
        }
        from ansible_collections.aknochow.claude.plugins.modules.agent import (
            normalize_usage,
        )

        result = normalize_usage(usage)
        assert result["input_tokens"] == 1738
        assert result["output_tokens"] == 199
        assert result["thinking_tokens"] == 190

    def test_sums_cache_token_fields_across_iterations(self):
        usage = {
            "iterations": [
                {"cache_read_input_tokens": 500, "cache_creation_input_tokens": 20},
                {"cache_read_input_tokens": 1500, "cache_creation_input_tokens": 5},
            ],
        }
        from ansible_collections.aknochow.claude.plugins.modules.agent import (
            normalize_usage,
        )

        result = normalize_usage(usage)
        assert result["cache_read_tokens"] == 2000
        assert result["cache_write_tokens"] == 25
