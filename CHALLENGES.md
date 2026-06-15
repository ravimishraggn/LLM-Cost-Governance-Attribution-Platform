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

---

## Phase 2 — Model names don't match the pricing table

**Challenge.** The cost engine looks up a price by model name, but the name a
provider *reports* is often not the name you can price against. Ask OpenAI for
`gpt-4o-mini` and the response's `model` field comes back as a dated snapshot
like `gpt-4o-mini-2024-07-18`. A naive exact-match lookup against a pricing table
keyed on `gpt-4o-mini` misses, silently producing `$0.00` — the worst kind of
bug in a cost system, because the number still *looks* plausible.

A second wrinkle: the same Claude model is priced differently on Anthropic direct
versus Bedrock, so a table keyed by model name alone can't represent both.

**Resolution.** Two decisions in `pricing.py`:
1. **Key prices by `(provider, model)`**, never model alone — so Anthropic-direct
   and Bedrock rates for the same family coexist.
2. **Resolve names with an exact match first, then a longest-prefix fallback**, so
   `gpt-4o-mini-2024-07-18` still resolves to the `gpt-4o-mini` entry while
   `gpt-4` never accidentally swallows `gpt-4o`. When nothing matches at all, we
   record `$0.00` *and log a warning* — an unpriced model becomes a visible gap,
   not a silent zero.

This is also why the gateway prices on the **requested** model (what the caller
asked for and what the rate card is written against) rather than the provider's
returned snapshot id.
