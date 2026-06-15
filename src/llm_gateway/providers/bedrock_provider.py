"""AWS Bedrock adapter.

Bedrock is the strongest case for the adapter layer: it fronts many model
families (Anthropic, Meta, Amazon Titan...) and its response envelope differs
from the native provider SDKs. We use the **Converse API**, which normalizes
requests across model families and reports usage as `inputTokens` /
`outputTokens` (yet a third naming convention) nested under a `usage` key.
"""

from __future__ import annotations

from ..config import get_settings
from ..schemas import CompletionRequest, Role
from .base import LLMProvider, ProviderResult


class BedrockProvider(LLMProvider):
    name = "bedrock"

    def complete(self, request: CompletionRequest) -> ProviderResult:
        import boto3  # lazy import

        client = boto3.client("bedrock-runtime", region_name=get_settings().aws_region)

        system_parts = [{"text": m.content} for m in request.messages if m.role == Role.SYSTEM]
        messages = [
            {"role": m.role.value, "content": [{"text": m.content}]}
            for m in request.messages
            if m.role != Role.SYSTEM
        ]

        resp = client.converse(
            modelId=request.model,
            system=system_parts or None,
            messages=messages,
            inferenceConfig={
                "maxTokens": request.max_tokens or 512,
                "temperature": request.temperature or 0.7,
            },
        )

        # Bedrock nests content blocks differently from the native SDKs.
        blocks = resp["output"]["message"]["content"]
        text = "".join(b.get("text", "") for b in blocks)
        usage = resp["usage"]
        return ProviderResult(
            content=text,
            prompt_tokens=usage["inputTokens"],
            completion_tokens=usage["outputTokens"],
            model=request.model,
        )
