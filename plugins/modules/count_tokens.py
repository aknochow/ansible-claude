#!/usr/bin/python
# Copyright: (c) 2026, Adam Knochowski (@aknochow)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

DOCUMENTATION = r"""
---
module: count_tokens
short_description: Count input tokens for a Claude request without generating
description:
  - Wraps the Anthropic Messages token-counting endpoint.
  - Useful as a pre-flight budget check before an expensive M(aknochow.claude.message) call.
version_added: "0.1.0"
author:
  - Adam Knochowski (@aknochow)
options:
  model:
    description:
      - Model identifier.
    type: str
    required: true
  messages:
    description:
      - List of message objects, each with C(role) and C(content).
    type: list
    elements: dict
    required: true
  system:
    description:
      - System prompt string.
    type: str
  tools:
    description:
      - List of tool definitions, if the real call would include tools.
    type: list
    elements: dict
extends_documentation_fragment:
  - aknochow.claude.auth
requirements:
  - "anthropic >= 0.84.0"
"""

EXAMPLES = r"""
- name: Estimate cost before generating
  aknochow.claude.count_tokens:
    model: claude-sonnet-5
    messages:
      - role: user
        content: "{{ large_prompt }}"
  register: estimate

- name: Skip the call if the prompt is too large
  aknochow.claude.message:
    model: claude-sonnet-5
    max_tokens: 1024
    messages:
      - role: user
        content: "{{ large_prompt }}"
  when: estimate.input_tokens < 50000
"""

RETURN = r"""
input_tokens:
  description: Number of input tokens the request would consume.
  type: int
  returned: always
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.aknochow.claude.plugins.module_utils.claude_client import (
    PROVIDER_ARGSPEC,
    get_client,
)


def main():
    argument_spec = dict(
        model=dict(type="str", required=True),
        messages=dict(type="list", elements="dict", required=True),
        system=dict(type="str"),
        tools=dict(type="list", elements="dict"),
    )
    argument_spec.update(PROVIDER_ARGSPEC)

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    client = get_client(module)

    kwargs = dict(
        model=module.params["model"],
        messages=module.params["messages"],
    )
    for key in ("system", "tools"):
        value = module.params.get(key)
        if value is not None:
            kwargs[key] = value

    try:
        from anthropic import AnthropicError

        response = client.messages.count_tokens(**kwargs)
        module.exit_json(changed=False, input_tokens=response.input_tokens)
    except AnthropicError as e:
        module.fail_json(msg=str(e))


if __name__ == "__main__":
    main()
