# ADR-002: Gateway-Level Logging vs. Per-Application Instrumentation

## Status
Accepted

## Context
LLM usage needs to be tracked across multiple applications and teams.
We could either ask each application team to add logging/tagging code
themselves, or intercept all calls centrally.

## Decision
Implement logging at the gateway layer. All LLM calls route through a
single proxy service that captures metadata, tokens, cost, and latency
before forwarding to the provider. The call record is written from one
place (`gateway.complete()`), using one schema, regardless of which
provider ultimately served the request.

## Alternatives Considered
- **Per-app SDK instrumentation:** rejected — relies on every team adopting
  it consistently, creates drift, and is hard to enforce in regulated
  environments. A single team forgetting to tag calls produces an
  unattributed gap in the very report Finance depends on.
- **Provider-side logging only (e.g., OpenAI usage dashboard):** rejected —
  no cross-provider view, no custom tagging for chargeback, and the billing
  granularity stops at the API-key/account level, not team/agent/use-case.

## Consequences
- Single point of integration reduces onboarding friction for new teams.
- One canonical record schema — attribution, tokens, cost, and latency live
  together, so chargeback and observability read from the same source of truth.
- Becomes a critical-path dependency — needs HA design and, at scale, an async
  write path so DB latency never blocks a model call (future ADR).
- Enables a consistent tagging taxonomy enforced at the edge across the org.

## Real-World Parallel
This mirrors how enterprise API gateways (Kong, Apigee) centralize auth
and rate-limiting — applying the same pattern to LLM cost governance is
the natural evolution as LLM calls become as ubiquitous as REST calls.
It also matches the FinOps principle that cost data must be *complete* to be
trusted: a chargeback model with optional, opt-in instrumentation is one
unattributed team away from losing finance's confidence.
