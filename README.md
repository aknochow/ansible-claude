# aknochow.claude

Ansible collection for calling Claude directly via the official
[Anthropic Python SDK](https://pypi.org/project/anthropic/) — not the
`claude` CLI. Built for deterministic, structured invocation from
Ansible tasks (`register`, `set_fact`, `when`, loops), across three
auth backends: direct Anthropic API, Google Vertex AI, and AWS Bedrock.

Companion collection: [`aknochow.openshell`](https://github.com/aknochow/ansible-openshell)
manages sandboxed execution environments. The two are deliberately
decoupled — this collection has no knowledge of OpenShell at all — but
compose cleanly via `delegate_to`; see
[Combining with aknochow.openshell](#combining-with-aknochowopenshell).

## Why this instead of `claude -p`?

`claude -p` gives you a full agentic session (tools, file access,
multi-turn reasoning) at the cost of a large, fixed per-invocation
overhead: in measured testing, a trivial one-shot question burned
**~39,000 cache-creation tokens** on system prompt + tool definitions
alone — and that overhead did **not** get reused across separate `claude
-p` process invocations (no cache hit on repeated calls), regardless of
how small the actual task was.

For well-defined, structured tasks — classification, extraction,
scoring, anything with a single clear input/output — a raw
`messages.create()` call sends only what you put in `messages`. A
side-by-side benchmark (3 structured tasks, same model, same
correctness) measured **aknochow.claude.message at ~$0.0007 total vs.
claude -p at ~$0.15 total for the same 3 calls — roughly 227× cheaper**,
with identical accuracy on both sides. The CLI's overhead only pays for
itself when you actually need its tools; for single-shot structured
work, it doesn't.

Use `claude -p` (or Claude Code skills, which assume a full
Claude Code session with tool access) when you need multi-step
reasoning, file/repo access, or sub-agent orchestration. Use this
collection when the task is a bounded, structured call you want to run
deterministically inside an Ansible pipeline — including in a tight
loop over many items, where the CLI's per-call tax adds up fast.

## Modules

| Module | Purpose |
|---|---|
| `message` | Call the Messages API — structured output (`output_config` or forced `tool_choice`), prompt caching, flattened return values |
| `count_tokens` | Pre-flight token counting to budget calls before spending output tokens |
| `message_batch` | Submit/poll/cancel bulk requests via the Message Batches API (direct Anthropic API only — not supported on Vertex or Bedrock; the module fails cleanly with a clear message if you try) |

## Requirements

```
pip install 'anthropic[vertex]>=0.84.0'
```

## Auth

Set `provider` to `anthropic` (default), `vertex`, or `bedrock`. Each
mode's credentials can be passed as module params or via environment
variables — see each module's documentation
(`ansible-doc aknochow.claude.message`) for the full list.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
# or, for Vertex:
export ANSIBLE_CLAUDE_PROVIDER=vertex
export CLOUD_ML_REGION=us-east5
export ANTHROPIC_VERTEX_PROJECT_ID=my-gcp-project
```

**Do not** attempt to reuse a `claude.ai` Pro/Max subscription's OAuth
token as auth here. Claude Code's own use of that token to call the
Messages API is specific to the official client; routing your own API
traffic through it is against the terms of that consumer plan, which
is a different product/billing model from the pay-per-token Console
API this collection is built around. Use a Console API key (or
Vertex/Bedrock) instead — it's inexpensive for this kind of workload
(see the cost comparison above).

### `message` — basic call

```yaml
- name: Basic message
  aknochow.claude.message:
    model: claude-sonnet-5
    max_tokens: 512
    messages:
      - role: user
        content: "Summarize this changelog in one sentence: {{ changelog }}"
  register: result
# result.text, result.usage.{input_tokens,output_tokens,...}
```

### Structured output — two mechanisms, pick based on your platform

**`output_config`** (native structured output, preferred when available):

```yaml
- aknochow.claude.message:
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
            name: { type: string }
            severity: { type: string, enum: [low, medium, high, critical] }
          required: [name, severity]
          additionalProperties: false   # required by the API for object schemas
  register: result
# result.structured.name, result.structured.severity
```

**Forced `tool_choice`** (functionally equivalent, works everywhere):

Some GCP projects gate Vertex AI's `structured_outputs` partner-model
feature separately from basic model access via the
`constraints/vertexai.allowedPartnerModelFeatures` org policy — we hit
this directly during testing (`output_config` calls failed with
`FAILED_PRECONDITION` while plain messages and forced tool use worked
fine on the *same* project). If you hit the same wall and don't control
the GCP org policy, use forced tool use instead — same result shape,
no policy dependency:

```yaml
- aknochow.claude.message:
    model: claude-sonnet-5
    max_tokens: 1024
    messages:
      - role: user
        content: "Extract the name and severity from this bug report: {{ bug_text }}"
    tools:
      - name: report_extraction
        description: Report the extracted fields.
        input_schema:
          type: object
          properties:
            name: { type: string }
            severity: { type: string, enum: [low, medium, high, critical] }
          required: [name, severity]
    tool_choice: { type: tool, name: report_extraction }
  register: result
# result.tool_calls[0].input.name, result.tool_calls[0].input.severity
```

### `count_tokens`

```yaml
- aknochow.claude.count_tokens:
    model: claude-sonnet-5
    messages:
      - role: user
        content: "{{ large_prompt }}"
  register: estimate
- aknochow.claude.message:
    model: claude-sonnet-5
    max_tokens: 1024
    messages: [{role: user, content: "{{ large_prompt }}"}]
  when: estimate.input_tokens < 50000
```

### Cost accounting across many calls

Collect registered results into a list and use `map`/`sum` — no manual
accumulation needed:

```yaml
- ansible.builtin.debug:
    msg: "{{ my_calls | map(attribute='usage.input_tokens') | sum }} input / {{ my_calls | map(attribute='usage.output_tokens') | sum }} output tokens"
```

## Examples

See `examples/` for: structured extraction, deterministic tool-use
branching, batch analysis, multi-agent comparison (Haiku vs. Sonnet
cost/quality), and `sandboxed_execution.yml` (runs a `message` call
*inside* an OpenShell sandbox via `delegate_to` — see below).

## Combining with aknochow.openshell

This collection has zero knowledge of OpenShell — no "target sandbox"
parameter, nothing sandbox-specific. Running a `message` call inside a
sandbox is just normal Ansible `delegate_to`, the same as targeting any
other host:

```yaml
# (sandbox created and registered as 'sandbox_target' via
# aknochow.openshell — see that collection's README)

- name: Ensure the SDK is installed in the sandbox
  ansible.builtin.pip:
    name: anthropic
  delegate_to: sandbox_target

- name: Run a Claude call from inside the sandbox
  aknochow.claude.message:
    model: claude-haiku-4-5
    max_tokens: 128
    messages: [{role: user, content: "hello from inside the sandbox"}]
  delegate_to: sandbox_target
  register: result
```

The full worked pattern (including the SSH-delegation mechanics) is in
`examples/sandboxed_execution.yml`.

## Testing

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install ansible-core 'anthropic[vertex]>=0.84.0'
ansible-galaxy collection install . --force
python -m pytest tests/unit/
```

Live-verified against direct Anthropic API auth and Google Vertex AI
(including a real Haiku/Sonnet run and a full cost/correctness
comparison against `claude -p`) during development — see
`tests/test_models.yml` and `examples/cost_effectiveness_comparison.yml`.
