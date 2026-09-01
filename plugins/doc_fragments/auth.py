# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations


class ModuleDocFragment:

    DOCUMENTATION = r"""
options:
  provider:
    description:
      - Which Anthropic client backend to use.
      - If the value is not specified, the value of the E(ANSIBLE_CLAUDE_PROVIDER) environment variable will be used.
    type: str
    choices: [anthropic, vertex, bedrock]
    default: anthropic
  api_key:
    description:
      - API key for the direct Anthropic API.
      - Required when O(provider=anthropic) unless O(auth_token) is set.
      - If the value is not specified, the value of the E(ANTHROPIC_API_KEY) environment variable will be used.
    type: str
  auth_token:
    description:
      - Bearer auth token for the direct Anthropic API, used instead of O(api_key).
      - If the value is not specified, the value of the E(ANTHROPIC_AUTH_TOKEN) environment variable will be used.
    type: str
  base_url:
    description:
      - Override the API base URL.
      - If the value is not specified, the value of the E(ANTHROPIC_BASE_URL) environment variable will be used.
    type: str
  region:
    description:
      - Google Cloud region for Vertex AI.
      - Required when O(provider=vertex).
      - If the value is not specified, the value of the E(CLOUD_ML_REGION) environment variable will be used.
    type: str
  project_id:
    description:
      - Google Cloud project ID for Vertex AI.
      - Required when O(provider=vertex).
      - If the value is not specified, the value of the
        E(ANTHROPIC_VERTEX_PROJECT_ID) environment variable will be used.
    type: str
  access_token:
    description:
      - Explicit Vertex AI access token. If omitted, falls back to Application Default Credentials.
      - If the value is not specified, the value of the
        E(ANTHROPIC_VERTEX_ACCESS_TOKEN) environment variable will be used.
    type: str
  aws_access_key:
    description:
      - AWS access key ID for Bedrock.
      - If the value is not specified, the value of the E(AWS_ACCESS_KEY_ID) environment variable will be used.
    type: str
  aws_secret_key:
    description:
      - AWS secret access key for Bedrock.
      - If the value is not specified, the value of the E(AWS_SECRET_ACCESS_KEY) environment variable will be used.
    type: str
  aws_region:
    description:
      - AWS region for Bedrock.
      - If the value is not specified, the value of the E(AWS_REGION) environment variable will be used.
    type: str
  aws_profile:
    description:
      - AWS profile name for Bedrock.
      - If the value is not specified, the value of the E(AWS_PROFILE) environment variable will be used.
    type: str
  aws_session_token:
    description:
      - AWS session token for Bedrock.
      - If the value is not specified, the value of the E(AWS_SESSION_TOKEN) environment variable will be used.
    type: str
  timeout:
    description:
      - Per-request timeout in seconds.
    type: float
    default: 120.0
  max_retries:
    description:
      - Maximum number of automatic retries the SDK performs on transient errors.
    type: int
    default: 2
"""
