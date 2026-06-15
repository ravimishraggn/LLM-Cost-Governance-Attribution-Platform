# ADR-001: FastAPI + Proxy/Gateway Pattern over SDK Wrappers

## Status
Accepted

## Context
Every LLM call in the org needs to be tagged, measured, costed, and governed.
The first architectural fork is *where* that interception lives. Two broad shapes:

1. A **library/SDK wrapper** that each application imports and calls instead of
   the raw provider SDK.
2. A **standalone proxy/gateway service** that applications call over HTTP, which
   then forwards to the provider.

Constraints that shape the decision:
- Calls originate from a polyglot fleet (Python services, notebooks, LangGraph
  agents, possibly non-Python tools) — not everything can import one Python lib.
- The tagging taxonomy and pricing logic must evolve **without redeploying every
  consumer**.
- Finance and compliance need a *guaranteed* choke point, not best-effort adoption.
- We want a Python-native stack with first-class async (LLM calls are I/O bound),
  automatic request validation, and OpenAPI docs for self-service onboarding.

## Decision
Build the platform as a **centralized HTTP gateway service** using **FastAPI**.
Applications send a normalized completion request (provider, model, messages,
and a required `metadata` block) to the gateway; the gateway tags, times, logs,
costs, optionally re-routes, and forwards to the underlying provider SDK.

FastAPI specifically because:
- Native `async`/`await` — the gateway is almost pure I/O (network to providers,
  network to DB/observability), so async concurrency is the right model.
- Pydantic v2 request/response validation makes the `metadata` contract
  (`team`, `project`, `agent_name`, `use_case`) enforceable at the edge — a call
  with no attribution can be rejected, which is the whole point of the platform.
- Auto-generated OpenAPI/Swagger lowers onboarding friction for consuming teams.

## Alternatives Considered
- **SDK wrapper library (per-language):** rejected as the *primary* interface.
  It couples cost-governance logic to consumer deploy cycles, can't be enforced
  (a team can always `import openai` directly), and multiplies maintenance across
  languages. It remains valuable as an *optional* thin client for latency-sensitive
  callers (documented as a future packaging option, not the core).
- **Flask / Django:** rejected — weaker async story and no built-in schema
  validation; we'd rebuild what FastAPI gives for free.
- **A generic API gateway (Kong/Apigee) with plugins:** rejected for the MVP —
  great at auth/rate-limiting but has no semantic understanding of tokens, model
  pricing tiers, or per-agent attribution. We'd be writing custom plugins anyway,
  in a less testable environment than a first-class Python service.

## Consequences
- **Easier:** one enforced choke point; consistent tagging; pricing/routing logic
  updatable centrally; language-agnostic consumers; self-service via OpenAPI.
- **Harder:** the gateway becomes a critical-path dependency and a potential
  latency/availability bottleneck. This is accepted now and addressed later via
  fail-open behaviour and an async logging path (future ADRs on HA and scale).
- We take on operating a service (deploy, monitor, scale) rather than shipping a
  library — a deliberate trade of operational cost for governance guarantees.

## Real-World Parallel
This is the same evolution REST traffic went through: teams first hand-rolled
HTTP clients, then organizations standardized on API gateways (Kong, Apigee, AWS
API Gateway) to centralize auth, rate-limiting, and observability. As LLM calls
become as routine as REST calls, an **"LLM gateway"** is the natural place to
centralize cost governance — the same pattern, applied one layer up the stack.
