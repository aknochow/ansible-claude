#!/usr/bin/python
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

DOCUMENTATION = r"""
---
module: agent
short_description: Invoke Claude through the Claude Agent SDK (Claude Code as a library)
description:
  - Calls Claude via the C(claude-agent-sdk) Python package, the same library that
    powers the C(claude) CLI. Unlike M(aknochow.claude.message), which talks to the
    Messages API directly and bills API/Console credits, this module authenticates
    the way the C(claude) CLI does — including, when set up on the host, the OAuth
    session backing a C(claude.ai) Pro/Max subscription — so calls draw on
    subscription usage rather than pay-per-token API credits.
  - This is the sanctioned way to reuse subscription auth from automation -- the SDK
    itself performs the OAuth handshake used by the official C(claude) CLI. Contrast
    with M(aknochow.claude.message)'s README, which warns against manually extracting
    a subscription OAuth token and feeding it to the raw Messages API -- that is out
    of scope for what this module does.
  - Runs a single query via the SDK's C(query()) entry point and collects every
    message the SDK yields for that query, then flattens the result into the same
    return shape used across this collection's other modules.
  - By default O(tools=[]), so a call runs with no tool access and cannot touch the
    filesystem, network, or shell -- it behaves like a plain one-shot completion.
    Set O(tools) explicitly to opt into agentic behavior; understand the security
    implications before doing so (see Security below).
  - "Harness overhead: even with O(tools=[]), O(max_turns=1), and no O(system_prompt),
    every call carries fixed harness overhead measured against C(claude-haiku-4-5)
    -- this is the CLI's own framing, not billable API content -- and it is
    dominated by O(setting_sources), not the harness baseline itself. With
    O(setting_sources=[]) (this module's default) a call measured ~234 input
    tokens. With O(setting_sources) left unset (the SDK default of loading every
    filesystem settings source) the same call, run with C(cwd) pointed at a real
    project directory carrying its own C(CLAUDE.md)/skills, measured ~2,485 input
    tokens -- roughly 2,250 extra tokens of that project's own instructions
    silently pulled into context. A custom O(system_prompt) adds on top of
    whichever baseline applies. Consumers benchmarking this module's token cost
    against M(aknochow.claude.message) should account for this floor, and should
    know it moves by an order of magnitude depending on O(setting_sources)."
  - Security -- this module can execute tools if O(tools) is set to anything other
    than an empty list. Never pass secrets in O(prompt) or O(system_prompt) that
    should not be visible to whatever tools are enabled. This module does not log
    credentials or environment contents.
version_added: "0.2.0"
author:
  - Adam Knochowski (@aknochow)
options:
  prompt:
    description:
      - The prompt to send.
    type: str
    required: true
  system_prompt:
    description:
      - Custom system prompt. When unset, the SDK's own default framing (if any)
        applies. Adds to the fixed harness overhead documented above.
    type: str
  model:
    description:
      - Model identifier (e.g. V(claude-sonnet-5), V(claude-haiku-4-5)). Defaults to
        the CLI's own default model when unset.
    type: str
  fallback_model:
    description:
      - Model to fall back to if O(model) fails or is unavailable.
    type: str
  effort:
    description:
      - How much effort Claude puts into its response. Works with adaptive thinking
        to guide thinking depth.
    type: str
    choices: [low, medium, high, xhigh, max]
  thinking:
    description:
      - "Thinking/reasoning configuration, passed through to the SDK's C(thinking)
        option verbatim, e.g. C({\"type\": \"adaptive\"}) or
        C({\"type\": \"enabled\", \"budget_tokens\": 4096}) or C({\"type\": \"disabled\"})."
    type: dict
  output_format:
    description:
      - "Schema-constrained structured output configuration, e.g.
        C({\"type\": \"json_schema\", \"schema\": {...}}). When set, RV(structured) is
        populated from the SDK's own parsed C(structured_output) field -- this is
        native schema enforcement (a forced C(StructuredOutput) tool call) by the
        underlying API, not best-effort text parsing on this module's side, so a
        populated RV(structured) really did conform to the schema."
      - "Two real gotchas confirmed by live testing, both load-bearing for retry
        logic: (1) Claude can still *decline* to call the structured-output tool at
        all (the same way it can decline any tool call) -- when that happens the
        query still completes successfully (C(is_error=false)), but RV(structured)
        is simply absent and the refusal text lands in RV(text) instead. Check for
        a missing RV(structured), not just failure, to detect this. (2) if the
        model's first turn doesn't produce a schema-conforming call, the CLI needs
        an additional turn to retry it -- with the default O(max_turns=1) this
        turn budget is exhausted before that retry can happen and the whole query
        fails with a raised error (C(error_max_turns)) instead of returning a
        clean non-match. Set O(max_turns) to at least 2 whenever O(output_format)
        is set."
    type: dict
  tools:
    description:
      - "Base set of built-in tools available to the session. Defaults to V([])
        (no tools at all) so the module is inert by default -- set this explicitly
        to opt into tool access. Pass a list of tool names (e.g. V([\"Read\", \"Bash\"]))
        or a preset dict such as C({\"type\": \"preset\", \"preset\": \"claude_code\"}) to
        enable the CLI's full default tool set."
    type: raw
    default: []
  allowed_tools:
    description:
      - Tool names that are auto-allowed without a permission prompt. Only relevant
        when O(tools) grants tools in the first place.
    type: list
    elements: str
  disallowed_tools:
    description:
      - Tool names removed from the model's context entirely, even if O(tools) or
        O(allowed_tools) would otherwise permit them.
    type: list
    elements: str
  max_turns:
    description:
      - Maximum number of conversation turns before the query stops. Defaults to a
        single turn, since the primary use case is one-shot lens dispatch, not an
        open-ended agent loop.
    type: int
    default: 1
  max_budget_usd:
    description:
      - Hard cost ceiling in USD for the query. The SDK stops the query and reports
        an C(error_max_budget_usd) result subtype if this is exceeded. Real safety
        feature for unattended automation -- set it whenever cost risk matters.
    type: float
  cwd:
    description:
      - "Working directory for the underlying Claude Code session. Prefer setting
        this over relying on the calling process's own working directory -- a
        C(claude) CLI subprocess started inside a directory that carries Claude
        Code project configuration (a C(.claude/) tree, C(CLAUDE.md), etc.) can
        stall its own C(initialize) control-request handshake, where the same
        directory passed explicitly via O(cwd) does not reproduce that stall.
        See O(setting_sources) for the related, and much larger, token-overhead
        concern with running against a real project directory."
    type: path
  setting_sources:
    description:
      - "Which filesystem settings sources the underlying Claude Code session
        loads -- V(user) (C(~/.claude/settings.json)), V(project)
        (C(.claude/settings.json)), V(local) (C(.claude/settings.local.json)).
        Defaults to V([]) (load none of them), which differs from the SDK's own
        default of loading everything when this is left unset."
      - "Two independent reasons for that default, both confirmed by live
        testing against a real project directory (see O(cwd)): (1) token cost --
        a call with O(setting_sources=[]) measured ~234 input tokens; the same
        call with every settings source loaded measured ~2,485 input tokens,
        meaning roughly 2,250 tokens of that project's own C(CLAUDE.md) and
        skills were pulled into context on every single call, silently. (2)
        review integrity -- the primary intended use of this module is dispatching
        code-review lenses over a repository's diff. If that repository's own
        C(CLAUDE.md)/skills load into the reviewing session's context, the
        repository being reviewed can steer its own review, deliberately or
        not. Diff content already has to be treated as untrusted input for a
        review tool; silently loading project-authored instructions on top of
        it is the same category of risk. Set this explicitly (e.g. V([\"project\"]))
        only when you specifically want that project's own configuration
        applied and have reasoned about both costs above."
    type: list
    elements: str
    choices: [user, project, local]
    default: []
  add_dirs:
    description:
      - Additional directories the session may access beyond O(cwd).
    type: list
    elements: path
  settings:
    description:
      - Path to an additional settings JSON file to load, merged at the highest
        priority layer (equivalent to the CLI's C(--settings) flag).
    type: path
  timeout:
    description:
      - Maximum time in seconds to wait for the query to complete. The underlying
        CLI subprocess can hang (e.g. on an interactive prompt it never receives);
        this bounds how long the task blocks. The module fails with a clear message
        on timeout rather than hanging the play indefinitely.
    type: float
    default: 300.0
requirements:
  - "claude-agent-sdk >= 0.2.144"
  - "The C(claude) CLI must be discoverable (bundled with the SDK, or on PATH), and
    authenticated on the host running this module -- either via C(claude) CLI's own
    subscription OAuth login, or by an C(ANTHROPIC_API_KEY) in the environment."
notes:
  - "If C(ANTHROPIC_API_KEY) is present in the process environment, the underlying
    C(claude) CLI uses it and bypasses subscription OAuth entirely, silently
    defeating the reason to use this module over M(aknochow.claude.message). If you
    want subscription usage, ensure C(ANTHROPIC_API_KEY) is unset for the task, e.g.
    C(environment: {ANTHROPIC_API_KEY: \"\"}) or by not exporting it on the host/run."
  - "Confirmed live: with no C(ANTHROPIC_API_KEY) in the environment, the CLI's own
    control-protocol handshake reports back C(subscriptionType: \"Claude Pro\") and
    C(apiProvider: \"firstParty\") for the authenticated account -- this is genuine
    subscription OAuth, the same session the interactive C(claude) CLI uses, not a
    Console API key routed through a different door."
  - "Confirmed live: C(claude-agent-sdk) 0.2.144's C(initialize) control request
    can stall indefinitely, and the reproducing variable is the underlying
    C(claude) CLI subprocess's own working directory, not the Python interpreter
    version -- same interpreter, only C(cwd) differed. Starting that subprocess
    inside a directory carrying Claude Code project configuration (a
    C(.claude/) tree, C(CLAUDE.md), etc.) stalled the handshake; the identical
    call from a plain directory with no such configuration completed normally.
    Passing the project directory via the O(cwd) *option* instead (so the SDK
    launches the subprocess elsewhere and directs it at the project path) did
    not reproduce the stall. Prefer O(cwd) over relying on the calling process's
    own directory for this reason as well as the token-overhead one documented
    under O(setting_sources). O(timeout) bounds the damage if a host hits this
    regardless."
  - "Rate-limit exhaustion was not reproduced live (it would require actually
    exhausting the subscription's quota, which this module's own testing
    deliberately avoided). Based on the SDK's typed surface: a hard rejection
    raises as a subclass of C(claude_agent_sdk.ClaudeSDKError) which this module
    catches and reports via C(fail_json) with the SDK's message text; a
    softer/approaching-limit signal streams as a C(RateLimitEvent) with
    C(status) of V(allowed_warning) or V(rejected), and a failing turn's
    C(ResultMessage) may carry C(api_error_status) (e.g. V(429)). This module
    does not currently special-case rate-limit errors -- they surface as a
    generic failure message; treat any M(aknochow.claude.agent) failure as worth inspecting for
    a 429/rate-limit signature before retrying in a loop."
"""

EXAMPLES = r"""
- name: One-shot completion against the claude.ai subscription, no tools
  aknochow.claude.agent:
    prompt: "Summarize this changelog in one sentence: {{ changelog }}"
  register: result
# result.text, result.usage_normalized.{input_tokens,output_tokens,...}

- name: Structured extraction via output_format
  aknochow.claude.agent:
    prompt: "Extract the name and severity from this bug report: {{ bug_text }}"
    output_format:
      type: json_schema
      schema:
        type: object
        properties:
          name: {type: string}
          severity: {type: string, enum: [low, medium, high, critical]}
        required: [name, severity]
  register: result
# result.structured.name, result.structured.severity

- name: Explicitly opt into tool access with a cost ceiling
  aknochow.claude.agent:
    prompt: "Look at the files in this directory and summarize what this project does."
    tools:
      - Read
      - Glob
    cwd: /path/to/project
    max_turns: 5
    max_budget_usd: 0.50
  register: result

- name: Force subscription auth by clearing any inherited API key
  aknochow.claude.agent:
    prompt: "{{ lens_prompt }}"
  environment:
    ANTHROPIC_API_KEY: ""
  register: result
"""

RETURN = r"""
text:
  description: Concatenated text from all assistant text content blocks across the query.
  type: str
  returned: always
structured:
  description: Parsed structured output when O(output_format) was set and the SDK
    populated a structured result. Absent otherwise.
  type: dict
  returned: when output_format is set and parsing succeeded
tool_calls:
  description: List of tool_use blocks, each with id, name, and input. Empty list when none occurred.
  type: list
  returned: always
stop_reason:
  description: >-
    Normalized stop reason -- one of V(end_turn), V(tool_use), V(max_tokens),
    V(refusal), or the raw SDK/API value when it doesn't map to a known normalized
    form.
  type: str
  returned: always
resolved_model:
  description: The model actually used, as reported by the SDK.
  type: str
  returned: always
cost_usd:
  description: Total cost in USD for the query, as reported by the SDK's result message.
  type: float
  returned: always
usage:
  description: Raw usage dict verbatim from the SDK's result message.
  type: dict
  returned: always
usage_normalized:
  description: Usage counts normalized to a fixed set of keys across this collection's modules.
  type: dict
  returned: always
  contains:
    input_tokens:
      description: Number of input tokens.
      type: int
    output_tokens:
      description: Number of output tokens generated.
      type: int
    cache_read_tokens:
      description: Input tokens read from the prompt cache.
      type: int
    cache_write_tokens:
      description: Input tokens written to the prompt cache.
      type: int
    thinking_tokens:
      description: Tokens spent on extended thinking.
      type: int
    total_tokens:
      description:
        - Sum of input and output tokens for this query.
        - Thinking tokens are NOT added. The SDK reports them under
          C(output_tokens_details), so they are already counted inside
          C(output_tokens) -- adding them again double-counts.
      type: int
"""

import asyncio

from ansible.module_utils.basic import AnsibleModule

# Stop reasons the SDK/API may report, normalized to a small fixed vocabulary.
# Anything not in this map is passed through verbatim rather than dropped, so
# a future/unknown value from the SDK doesn't silently disappear.
_STOP_REASON_MAP = {
    "end_turn": "end_turn",
    "stop": "end_turn",
    "success": "end_turn",
    "tool_use": "tool_use",
    "max_tokens": "max_tokens",
    "max_turns": "max_tokens",
    "refusal": "refusal",
    "error_max_turns": "max_tokens",
    "error_max_budget_usd": "max_tokens",
}


def normalize_stop_reason(raw):
    if raw is None:
        return "end_turn"
    return _STOP_REASON_MAP.get(raw, raw)


def normalize_usage(usage):
    """Map the SDK's raw usage dict onto this collection's fixed usage_normalized shape.

    Sums across usage["iterations"] rather than reading the top-level scalars.
    On a multi-turn run the top-level fields report only the FINAL turn, so a
    two-turn lens dispatch (one turn to answer, one to satisfy a forced
    structured-output tool call) reports a handful of input tokens instead of
    thousands -- observed as input_tokens=4 on a real diff review whose first
    turn carried the whole diff plus an ~800-line system prompt. Confirmed
    against a live single-turn call where the top-level input_tokens (1738)
    equalled iterations[0]'s, so the top level is the last iteration, not a
    total.

    Falls back to the top-level scalars when "iterations" is absent, so an
    older SDK or a shape change degrades to the previous behaviour rather
    than silently reporting zero.

    Missing values default to 0 rather than being omitted, per the collection's
    return contract -- consumers should be able to rely on every key existing.
    """
    usage = usage or {}
    iterations = usage.get("iterations") or [usage]

    def _sum(key, nested=None):
        total = 0
        for turn in iterations:
            turn = turn or {}
            if nested:
                turn = turn.get(nested) or {}
            total += turn.get(key) or 0
        return total

    input_tokens = _sum("input_tokens")
    output_tokens = _sum("output_tokens")
    cache_read_tokens = _sum("cache_read_input_tokens")
    cache_write_tokens = _sum("cache_creation_input_tokens")
    thinking_tokens = _sum("thinking_tokens", nested="output_tokens_details")

    return dict(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
        thinking_tokens=thinking_tokens,
        # thinking_tokens is a NESTED SUBSET of output_tokens (the SDK
        # reports it under output_tokens_details), not an additional
        # bucket -- a live call returned output_tokens 199 of which
        # thinking_tokens was 190. Adding it here double-counted it.
        total_tokens=input_tokens + output_tokens,
    )


def flatten_messages(messages, parse_structured=False):
    """Flatten a list of SDK messages (AssistantMessage/ResultMessage/...) into
    this collection's standard return shape.
    """
    text_parts = []
    tool_calls = []
    resolved_model = None
    stop_reason = None
    cost_usd = None
    usage = None
    structured = None

    for msg in messages:
        msg_type = type(msg).__name__

        if msg_type == "AssistantMessage":
            for block in msg.content:
                block_type = type(block).__name__
                if block_type == "TextBlock":
                    text_parts.append(block.text)
                elif block_type == "ToolUseBlock":
                    tool_calls.append(dict(id=block.id, name=block.name, input=block.input))
            if getattr(msg, "model", None):
                resolved_model = msg.model
            if getattr(msg, "stop_reason", None):
                stop_reason = msg.stop_reason

        elif msg_type == "ResultMessage":
            cost_usd = getattr(msg, "total_cost_usd", None)
            usage = getattr(msg, "usage", None)
            result_stop_reason = getattr(msg, "stop_reason", None)
            if result_stop_reason:
                stop_reason = result_stop_reason
            if parse_structured:
                structured_output = getattr(msg, "structured_output", None)
                if structured_output is not None:
                    structured = structured_output

    result = dict(
        text="".join(text_parts),
        tool_calls=tool_calls,
        stop_reason=normalize_stop_reason(stop_reason),
        resolved_model=resolved_model,
        cost_usd=cost_usd,
        usage=usage or {},
        usage_normalized=normalize_usage(usage),
    )
    if structured is not None:
        result["structured"] = structured
    return result


def build_options(module, ClaudeAgentOptions):
    params = module.params
    kwargs = dict(
        tools=params["tools"],
        max_turns=params["max_turns"],
        # Always passed explicitly, never left to the SDK's own default of
        # loading every filesystem settings source -- see the module's
        # setting_sources documentation for why an empty list is the safe
        # default (token overhead and review-integrity risk both measured
        # live against a real project directory).
        setting_sources=params["setting_sources"],
    )

    for key in ("system_prompt", "model", "fallback_model", "effort", "thinking",
                "output_format", "allowed_tools", "disallowed_tools",
                "max_budget_usd", "cwd", "add_dirs", "settings"):
        value = params.get(key)
        if value is not None:
            kwargs[key] = value

    return ClaudeAgentOptions(**kwargs)


async def run_query(prompt, options, query_fn):
    messages = []
    async for message in query_fn(prompt=prompt, options=options):
        messages.append(message)
    return messages


def main():
    argument_spec = dict(
        prompt=dict(type="str", required=True),
        system_prompt=dict(type="str"),
        model=dict(type="str"),
        fallback_model=dict(type="str"),
        effort=dict(type="str", choices=["low", "medium", "high", "xhigh", "max"]),
        thinking=dict(type="dict"),
        output_format=dict(type="dict"),
        tools=dict(type="raw", default=[]),
        allowed_tools=dict(type="list", elements="str"),
        disallowed_tools=dict(type="list", elements="str"),
        max_turns=dict(type="int", default=1),
        max_budget_usd=dict(type="float"),
        cwd=dict(type="path"),
        setting_sources=dict(
            type="list", elements="str", choices=["user", "project", "local"], default=[]
        ),
        add_dirs=dict(type="list", elements="path"),
        settings=dict(type="path"),
        timeout=dict(type="float", default=300.0),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=False,
    )

    try:
        from claude_agent_sdk import ClaudeAgentOptions, query
    except ImportError:
        module.fail_json(
            msg="The claude-agent-sdk Python package is required. Install it with: "
            "pip install claude-agent-sdk"
        )
        return

    try:
        from claude_agent_sdk import ClaudeSDKError
    except ImportError:
        ClaudeSDKError = Exception

    options = build_options(module, ClaudeAgentOptions)
    prompt = module.params["prompt"]
    timeout = module.params["timeout"]

    try:
        messages = asyncio.run(
            asyncio.wait_for(run_query(prompt, options, query), timeout=timeout)
        )
    except asyncio.TimeoutError:
        module.fail_json(
            msg=f"aknochow.claude.agent timed out after {timeout} seconds waiting on "
            "the Claude Agent SDK/CLI subprocess. This does not consume subscription "
            "usage, but a hung CLI subprocess may still be running -- check for "
            "orphaned 'claude' processes on this host."
        )
        return
    except ClaudeSDKError as e:
        module.fail_json(msg=f"Claude Agent SDK error: {e}")
        return

    # A query call never mutates infrastructure state -- it's a query, same
    # as aknochow.claude.message and aknochow.gemini's generate module.
    # changed is always False, not conditional on the response.
    module.exit_json(
        changed=False,
        **flatten_messages(messages, parse_structured=bool(module.params.get("output_format"))),
    )


if __name__ == "__main__":
    main()
