#!/usr/bin/python
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

DOCUMENTATION = r"""
---
module: message
short_description: Send a message to Claude and return the response
description:
  - Calls the Anthropic Messages API directly via the official Python SDK.
  - Returns both the raw response and flattened convenience fields for use with O(register).
version_added: "0.1.0"
author:
  - Adam Knochowski (@aknochow)
options:
  model:
    description:
      - Model identifier (e.g., V(claude-opus-4-8), V(claude-sonnet-5)).
    type: str
    required: true
  messages:
    description:
      - List of message objects, each with C(role) (V(user) or V(assistant)) and C(content).
      - C(content) may be a plain string or a list of content block dicts.
    type: list
    elements: dict
    required: true
  max_tokens:
    description:
      - Maximum number of tokens to generate. There is no default — an explicit
        budget must be chosen for every call.
    type: int
    required: true
  system:
    description:
      - System prompt string.
    type: str
  cache_system:
    description:
      - If true, mark the system prompt as ephemeral-cacheable via C(cache_control).
      - Reduces input token cost on repeated calls with the same system prompt.
    type: bool
    default: false
  temperature:
    description:
      - Sampling temperature (0.0-1.0).
    type: float
  top_p:
    description:
      - Nucleus sampling parameter.
    type: float
  top_k:
    description:
      - Top-k sampling parameter.
    type: int
  stop_sequences:
    description:
      - List of strings that stop generation when encountered.
    type: list
    elements: str
  tools:
    description:
      - List of tool definitions (JSON Schema style) available to the model.
    type: list
    elements: dict
  tool_choice:
    description:
      - 'Controls tool-use behavior, e.g. C({"type": "auto"}) or C({"type": "tool", "name": "..."}).'
    type: dict
  output_config:
    description:
      - 'Native structured-output configuration, e.g. C({"format": {"type": "json_schema", "schema": {...}}}).'
      - When set, the response text is parsed as JSON into the RV(structured) return value.
    type: dict
  metadata:
    description:
      - 'Request metadata, e.g. C({"user_id": "..."}).'
    type: dict
extends_documentation_fragment:
  - aknochow.claude.auth
requirements:
  - "anthropic >= 0.84.0"
"""

EXAMPLES = r"""
- name: Basic message
  aknochow.claude.message:
    model: claude-sonnet-5
    max_tokens: 512
    messages:
      - role: user
        content: "Summarize this changelog in one sentence: {{ changelog }}"
  register: result

- name: Structured extraction with output_config
  aknochow.claude.message:
    model: claude-sonnet-5
    max_tokens: 1024
    messages:
      - role: user
        content: "Extract the name and severity from this bug report: {{ bug_text }}"
    output_config:
      format:
        type: json_schema
        schema:
          type: object
          properties:
            name: {type: string}
            severity: {type: string, enum: [low, medium, high, critical]}
          required: [name, severity]
  register: result

- name: Use structured result directly
  ansible.builtin.debug:
    msg: "{{ result.structured.name }} is {{ result.structured.severity }}"

- name: Call via Vertex AI
  aknochow.claude.message:
    provider: vertex
    region: us-east5
    project_id: my-gcp-project
    model: claude-sonnet-5
    max_tokens: 512
    messages:
      - role: user
        content: "Hello"
"""

RETURN = r"""
message:
  description: Full raw response from the Messages API.
  type: dict
  returned: always
text:
  description: Concatenated text from all text content blocks.
  type: str
  returned: always
tool_calls:
  description: List of tool_use blocks, each with id, name, and input.
  type: list
  returned: always
structured:
  description: Parsed JSON object when O(output_config) requested structured output.
  type: dict
  returned: when output_config is set
stop_reason:
  description: Why generation stopped.
  type: str
  returned: always
usage:
  description: Token usage for the request.
  type: dict
  returned: always
  contains:
    input_tokens:
      description: Number of input tokens billed for this request.
      type: int
    output_tokens:
      description: Number of output tokens generated.
      type: int
    cache_creation_input_tokens:
      description: Input tokens written to the prompt cache on this request.
      type: int
    cache_read_input_tokens:
      description: Input tokens read from the prompt cache on this request.
      type: int
"""

import json

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.aknochow.claude.plugins.module_utils.claude_client import (
    PROVIDER_ARGSPEC,
    get_client,
)


def flatten_response(message):
    text_parts = []
    tool_calls = []
    for block in message.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "tool_use":
            tool_calls.append(dict(id=block.id, name=block.name, input=block.input))

    text = "".join(text_parts)
    structured = None
    if text:
        try:
            structured = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            structured = None

    usage = message.usage
    result = dict(
        message=message.model_dump(),
        text=text,
        tool_calls=tool_calls,
        stop_reason=message.stop_reason,
        usage=dict(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_creation_input_tokens=usage.cache_creation_input_tokens,
            cache_read_input_tokens=usage.cache_read_input_tokens,
        ),
    )
    if structured is not None:
        result["structured"] = structured
    return result


def main():
    argument_spec = dict(
        model=dict(type="str", required=True),
        messages=dict(type="list", elements="dict", required=True),
        max_tokens=dict(type="int", required=True),
        system=dict(type="str"),
        cache_system=dict(type="bool", default=False),
        temperature=dict(type="float"),
        top_p=dict(type="float"),
        top_k=dict(type="int"),
        stop_sequences=dict(type="list", elements="str"),
        tools=dict(type="list", elements="dict"),
        tool_choice=dict(type="dict"),
        output_config=dict(type="dict"),
        metadata=dict(type="dict"),
    )
    argument_spec.update(PROVIDER_ARGSPEC)

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=False,
    )

    client = get_client(module)

    kwargs = dict(
        model=module.params["model"],
        messages=module.params["messages"],
        max_tokens=module.params["max_tokens"],
    )

    system = module.params.get("system")
    if system:
        if module.params.get("cache_system"):
            kwargs["system"] = [
                dict(type="text", text=system, cache_control=dict(type="ephemeral"))
            ]
        else:
            kwargs["system"] = system

    for key in ("temperature", "top_p", "top_k", "stop_sequences", "tools", "tool_choice", "output_config", "metadata"):
        value = module.params.get(key)
        if value is not None:
            kwargs[key] = value

    try:
        from anthropic import AnthropicError

        response = client.messages.create(**kwargs)
        module.exit_json(changed=True, **flatten_response(response))
    except AnthropicError as e:
        module.fail_json(msg=str(e))


if __name__ == "__main__":
    main()
