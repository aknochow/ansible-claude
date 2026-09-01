#!/usr/bin/python
# Copyright: (c) 2026, Adam Knochowski (@aknochow)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

DOCUMENTATION = r"""
---
module: message_batch
short_description: Submit, poll, or cancel a Claude Message Batch
description:
  - Wraps the Anthropic Message Batches API for bulk asynchronous requests.
  - Batches are not supported on Vertex AI or Bedrock — this module requires O(provider=anthropic).
version_added: "0.1.0"
author:
  - Adam Knochowski (@aknochow)
options:
  batch_id:
    description:
      - ID of an existing batch. Required for O(state=absent) and for polling
        an existing batch instead of submitting a new one.
    type: str
  requests:
    description:
      - List of batch requests, each a dict with C(custom_id) and C(params)
        (the same params accepted by M(aknochow.claude.message), minus provider/auth options).
      - Required when submitting a new batch (O(state=present) without O(batch_id)).
    type: list
    elements: dict
  wait:
    description:
      - If true, poll until the batch reaches a terminal C(processing_status) before returning.
    type: bool
    default: false
  wait_timeout:
    description:
      - Maximum time in seconds to wait when O(wait=true).
    type: int
    default: 600
  state:
    description:
      - Use V(present) to submit or poll a batch, V(absent) to cancel one.
    type: str
    choices: [present, absent]
    default: present
extends_documentation_fragment:
  - aknochow.claude.auth
requirements:
  - "anthropic >= 0.84.0"
"""

EXAMPLES = r"""
- name: Submit a batch of requests
  aknochow.claude.message_batch:
    api_key: "{{ anthropic_api_key }}"
    requests:
      - custom_id: file-1
        params:
          model: claude-sonnet-5
          max_tokens: 512
          messages:
            - role: user
              content: "Summarize {{ file1_content }}"
      - custom_id: file-2
        params:
          model: claude-sonnet-5
          max_tokens: 512
          messages:
            - role: user
              content: "Summarize {{ file2_content }}"
    state: present
  register: batch

- name: Poll until the batch finishes
  aknochow.claude.message_batch:
    api_key: "{{ anthropic_api_key }}"
    batch_id: "{{ batch.batch_id }}"
    wait: true
    wait_timeout: 1800
  register: finished

- name: Cancel a batch
  aknochow.claude.message_batch:
    api_key: "{{ anthropic_api_key }}"
    batch_id: "{{ batch.batch_id }}"
    state: absent
"""

RETURN = r"""
batch_id:
  description: The batch's ID.
  type: str
  returned: always
processing_status:
  description: Current processing status (in_progress, canceling, ended).
  type: str
  returned: always
results:
  description: Batch results keyed by custom_id, populated once processing_status is 'ended'.
  type: dict
  returned: when the batch has ended
"""

import time

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.aknochow.claude.plugins.module_utils.claude_client import (
    PROVIDER_ARGSPEC,
    get_client,
)


def collect_results(client, batch_id):
    results = {}
    for entry in client.messages.batches.results(batch_id):
        results[entry.custom_id] = entry.result.model_dump()
    return results


def main():
    argument_spec = dict(
        batch_id=dict(type="str"),
        requests=dict(type="list", elements="dict"),
        wait=dict(type="bool", default=False),
        wait_timeout=dict(type="int", default=600),
        state=dict(type="str", choices=["present", "absent"], default="present"),
    )
    argument_spec.update(PROVIDER_ARGSPEC)

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=False,
    )

    if module.params["provider"] != "anthropic":
        module.fail_json(
            msg="message_batch requires provider=anthropic — the Batch API is not "
            "supported on Vertex AI or Bedrock."
        )

    client = get_client(module)
    batch_id = module.params.get("batch_id")
    state = module.params["state"]

    try:
        from anthropic import AnthropicError

        if state == "absent":
            if not batch_id:
                module.fail_json(msg="'batch_id' is required when state=absent")
            batch = client.messages.batches.cancel(batch_id)
            module.exit_json(
                changed=True,
                batch_id=batch.id,
                processing_status=batch.processing_status,
            )
            return

        if batch_id:
            batch = client.messages.batches.retrieve(batch_id)
            changed = False
        else:
            requests = module.params.get("requests")
            if not requests:
                module.fail_json(
                    msg="'requests' is required to submit a new batch when 'batch_id' is not set"
                )
            batch = client.messages.batches.create(requests=requests)
            changed = True

        if module.params.get("wait"):
            timeout = module.params.get("wait_timeout") or 600
            deadline = time.monotonic() + timeout
            while batch.processing_status not in ("ended",):
                if time.monotonic() >= deadline:
                    module.fail_json(
                        msg=f"Timed out waiting for batch {batch.id} to finish "
                        f"(status={batch.processing_status})"
                    )
                time.sleep(5)
                batch = client.messages.batches.retrieve(batch.id)

        result = dict(
            changed=changed,
            batch_id=batch.id,
            processing_status=batch.processing_status,
        )
        if batch.processing_status == "ended":
            result["results"] = collect_results(client, batch.id)

        module.exit_json(**result)
    except AnthropicError as e:
        module.fail_json(msg=str(e))


if __name__ == "__main__":
    main()
