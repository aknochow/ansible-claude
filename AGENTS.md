# ansible-claude: Project Context

## Read first

- [CONTRIBUTING.md](CONTRIBUTING.md): branch names, commits, test and lint commands
- [README.md](README.md): project overview

## What this repo is

Ansible collection for calling Claude directly via the official Anthropic Python SDK, not the `claude` CLI. Built for deterministic, structured invocation from Ansible tasks, across the Anthropic API, Google Vertex AI, and AWS Bedrock.

## Commands

Test and sanity commands, copied from [CONTRIBUTING.md](CONTRIBUTING.md):

### Quick test run:
```bash
uv run pytest
```

### Syncing dependencies:
```bash
uv sync --extra dev
uv run pytest -v
```

### Running sanity tests:
Ansible sanity tests require the repository to be within an `ansible_collections/aknochow/claude` directory hierarchy:
```bash
uv run ansible-test sanity --local --python 3.13 -v
```
