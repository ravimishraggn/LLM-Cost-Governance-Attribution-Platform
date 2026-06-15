# Engineering Challenges Log

A running log of one realistic technical challenge per phase and how it was
resolved. Written to capture the *why* behind non-obvious design choices.

---

## Phase 1 — Normalizing token usage across three providers

**Challenge.** The three target SDKs report token usage in three different
shapes, so there was no single field the gateway could read to populate the
`CallLog`:

| Provider  | Content location                       | Prompt tokens   | Completion tokens |
|-----------|----------------------------------------|-----------------|-------------------|
| OpenAI    | `choices[0].message.content`           | `prompt_tokens` | `completion_tokens` |
| Anthropic | `content[].text` (block list)          | `input_tokens`  | `output_tokens`   |
| Bedrock   | `output.message.content[].text`        | `inputTokens`   | `outputTokens`    |

On top of that, Anthropic takes the system prompt as a **top-level `system`
argument** rather than a message in the list, and Bedrock's Converse API nests
content in a different envelope again.

**Resolution.** Introduced an **adapter layer** (`providers/base.py` →
`ProviderResult`). Each provider gets its own adapter whose only job is to call
the SDK and map its idiosyncratic response onto one normalized dataclass
(`content`, `prompt_tokens`, `completion_tokens`, `model`). The gateway and the
cost engine never see provider-specific shapes — they only ever read
`ProviderResult`. Adding a fourth provider later is a new adapter, not a change
to the gateway.

A secondary benefit: because the adapter boundary is clean, a `MockProvider`
slots in behind the same interface, letting the whole pipeline (tagging → cost →
logging) run end-to-end with zero API keys and zero spend via
`GATEWAY_MOCK_MODE`.
