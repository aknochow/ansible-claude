# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from ansible.module_utils.basic import AnsibleModule, env_fallback

PROVIDER_ARGSPEC = dict(
    provider=dict(
        type="str",
        choices=["anthropic", "vertex", "bedrock"],
        default="anthropic",
        fallback=(env_fallback, ["ANSIBLE_CLAUDE_PROVIDER"]),
    ),
    # Direct Anthropic API
    api_key=dict(
        type="str",
        no_log=True,
        fallback=(env_fallback, ["ANTHROPIC_API_KEY"]),
    ),
    auth_token=dict(
        type="str",
        no_log=True,
        fallback=(env_fallback, ["ANTHROPIC_AUTH_TOKEN"]),
    ),
    base_url=dict(
        type="str",
        fallback=(env_fallback, ["ANTHROPIC_BASE_URL"]),
    ),
    # Vertex AI
    region=dict(
        type="str",
        fallback=(env_fallback, ["CLOUD_ML_REGION"]),
    ),
    project_id=dict(
        type="str",
        fallback=(env_fallback, ["ANTHROPIC_VERTEX_PROJECT_ID"]),
    ),
    access_token=dict(
        type="str",
        no_log=True,
        fallback=(env_fallback, ["ANTHROPIC_VERTEX_ACCESS_TOKEN"]),
    ),
    # Bedrock
    aws_access_key=dict(
        type="str",
        no_log=True,
        fallback=(env_fallback, ["AWS_ACCESS_KEY_ID"]),
    ),
    aws_secret_key=dict(
        type="str",
        no_log=True,
        fallback=(env_fallback, ["AWS_SECRET_ACCESS_KEY"]),
    ),
    aws_region=dict(
        type="str",
        fallback=(env_fallback, ["AWS_REGION"]),
    ),
    aws_profile=dict(
        type="str",
        fallback=(env_fallback, ["AWS_PROFILE"]),
    ),
    aws_session_token=dict(
        type="str",
        no_log=True,
        fallback=(env_fallback, ["AWS_SESSION_TOKEN"]),
    ),
    # Common
    timeout=dict(type="float", default=120.0),
    max_retries=dict(type="int", default=2),
)


def get_client(module: AnsibleModule):
    """Construct the right Anthropic SDK client for module.params['provider']."""
    provider = module.params["provider"]
    timeout = module.params.get("timeout") or 120.0
    max_retries = module.params.get("max_retries")
    if max_retries is None:
        max_retries = 2

    if provider == "anthropic":
        try:
            from anthropic import Anthropic
        except ImportError:
            module.fail_json(
                msg="The anthropic Python SDK is required. Install it with: pip install anthropic"
            )
            return
        api_key = module.params.get("api_key")
        auth_token = module.params.get("auth_token")
        if not api_key and not auth_token:
            module.fail_json(
                msg="'api_key' or 'auth_token' is required when provider=anthropic"
            )
            return
        return Anthropic(
            api_key=api_key,
            auth_token=auth_token,
            base_url=module.params.get("base_url"),
            timeout=timeout,
            max_retries=max_retries,
        )

    if provider == "vertex":
        try:
            from anthropic import AnthropicVertex
        except ImportError:
            module.fail_json(
                msg="The anthropic Vertex extra is required. Install it with: pip install 'anthropic[vertex]'"
            )
            return
        region = module.params.get("region")
        project_id = module.params.get("project_id")
        if not region or not project_id:
            module.fail_json(
                msg="'region' and 'project_id' are required when provider=vertex"
            )
            return
        return AnthropicVertex(
            region=region,
            project_id=project_id,
            access_token=module.params.get("access_token"),
            base_url=module.params.get("base_url"),
            timeout=timeout,
            max_retries=max_retries,
        )

    if provider == "bedrock":
        try:
            from anthropic import AnthropicBedrock
        except ImportError:
            module.fail_json(
                msg="The anthropic Bedrock extra is required. Install it with: pip install 'anthropic[bedrock]'"
            )
            return
        return AnthropicBedrock(
            aws_access_key=module.params.get("aws_access_key"),
            aws_secret_key=module.params.get("aws_secret_key"),
            aws_region=module.params.get("aws_region"),
            aws_profile=module.params.get("aws_profile"),
            aws_session_token=module.params.get("aws_session_token"),
            base_url=module.params.get("base_url"),
            timeout=timeout,
            max_retries=max_retries,
        )

    module.fail_json(msg=f"Unknown provider: {provider}")
    return
