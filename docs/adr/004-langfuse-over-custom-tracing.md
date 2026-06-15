# ADR-004: Langfuse for Tracing vs. Building Custom Observability

## Status
Accepted

## Context
The gateway already records a structured cost row per call (Phase 1/2). But cost
data answers *"what did it spend?"* — engineers debugging an agent also need
*"what actually happened?"*: the full prompt, the response, latency, token usage,
and how a single user request fanned out into many model calls (multi-agent
systems routinely trigger 10+ calls per request).

We need LLM-aware tracing: nested traces/spans, prompt/response capture, token
and cost attribution per generation, and a UI to explore it. The question is
build vs. buy.

Constraints:
- We are a small platform team; observability is necessary infrastructure, not
  our differentiator (the cost-governance layer is).
- Data residency matters in regulated environments — we may need to self-host.
- We want the *same* attribution tags (team / project / agent / use_case) to
  appear on traces as on cost rows, so the two views reconcile.

## Decision
Integrate **Langfuse** as the tracing backend rather than building custom
tracing. Every gateway call creates a Langfuse trace tagged with the same
attribution metadata and a generation carrying model, input, output, token
usage, latency, and our computed cost.

Three engineering guardrails make it safe:
1. **Tracing never breaks a call** — all Langfuse calls are wrapped; failures log
   a warning and the request still succeeds.
2. **Off by default, opt-in** — a no-op tracer is used unless tracing is enabled
   and credentials are present, so local/mock/test runs need nothing.
3. **No per-call flush** — we rely on the SDK's background batching and flush once
   at shutdown, keeping tracing off the latency hot path.

## Alternatives Considered
- **Build custom tracing** (our own spans table + a UI): rejected — it rebuilds a
  solved problem, and the UI/exploration tooling is a large ongoing cost that
  isn't our value-add. Our DB already holds the cost-of-record; duplicating
  full-trace storage and visualization is wasteful.
- **General-purpose APM (Datadog / OpenTelemetry only):** great for infra metrics
  but not LLM-native — no first-class notion of a "generation," prompt/response
  capture, or per-token cost. A fine *complement* (the gateway can emit OTel spans
  too) but not a replacement for LLM tracing.
- **Provider-native tracing (OpenAI/Anthropic dashboards):** rejected — siloed
  per provider, no cross-provider view, no custom tags. Same gap as ADR-002.

## Consequences
- **Easier:** rich tracing + cost view out of the box; open-source and
  self-hostable (keeps data ownership in regulated settings); native LangChain/
  LangGraph integration for teams already on those; tags reconcile cost ↔ traces.
- **Harder / accepted:** a new dependency and (if self-hosted) another service to
  operate. Our cost DB stays the authoritative source of record; Langfuse is the
  *debugging/observability* lens, not the billing ledger — so a Langfuse outage
  degrades visibility, not cost accuracy.

## Real-World Parallel
This is the classic "buy the undifferentiated heavy lifting" call. Few teams
build their own metrics/tracing stack from scratch anymore — they adopt
Prometheus/Grafana/Datadog and spend their energy on the domain logic. Langfuse
is that choice for the LLM layer: adopt the standard observability tool, keep the
team focused on the cost-governance differentiator, and retain the self-host
option compliance may require.
