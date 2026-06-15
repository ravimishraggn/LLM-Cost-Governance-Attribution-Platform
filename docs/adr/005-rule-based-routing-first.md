# ADR-005: Rule-Based Routing First vs. ML-Based Routing

## Status
Accepted

## Context
A large share of LLM spend is waste: using a frontier model for tasks a small
model handles perfectly (classification, extraction, short replies). A router
that sends simple tasks to cheaper models is one of the highest-leverage cost
levers — the same workload can swing from ~$225/day on a flagship model to ~$15/
day on a small one.

The question is *how* to decide "simple vs. complex." Options range from a few
heuristics to a trained classifier (or a cheap LLM acting as judge). The router
runs **synchronously on every request**, so latency, predictability, and
debuggability matter as much as accuracy.

## Decision
Ship a **rule-based router** for the MVP. Classify each request with cheap,
transparent heuristics — prompt length, presence of complexity keywords (in the
prompt or `use_case`), and requested output size — and, if the task is simple,
swap the requested model for a configured cheaper sibling (`config/routing.yaml`,
hot-reloadable). Complex tasks are never downgraded. We record the actual cost on
the served model and the **estimated savings** (what the requested model would
have cost for the same token usage), so the value of routing is measured, not
assumed.

## Alternatives Considered
- **ML/learned classifier (or LLM-as-judge):** rejected *for now*. A trained
  classifier needs labeled data we don't yet have, and an LLM-judge adds a second
  model call (latency + cost + a new failure mode) to *every* request — ironic for
  a cost-saving feature. Both are hard to explain to a team asking "why did my
  Opus call get downgraded?"
- **No routing, just dashboards:** rejected — surfacing waste is useful (Phase 5)
  but acting on it automatically is where the savings actually land.
- **Per-request manual model choice only:** that's the status quo; it relies on
  every developer always picking optimally, which is exactly the drift the
  platform exists to remove.

## Consequences
- **Easier:** near-zero added latency; fully deterministic and explainable (every
  decision carries a human-readable reason); tunable by ops via config without a
  deploy; safe (only ever downgrades simple tasks, never upgrades or blocks).
- **Harder / accepted:** heuristics are blunt — they will misclassify some edge
  cases (a short prompt that's actually hard, a long prompt that's trivial). We
  accept that because the failure is *graceful* (a simple task occasionally runs
  on the expensive model, or vice-versa) and because the logged savings + Langfuse
  traces give us exactly the labeled data a future ML router would need.
- The estimated-savings figure is a **counterfactual** (what the other model
  *would* have cost at the same token usage), not a measured A/B — honest framing
  matters for the chargeback narrative.

## Real-World Parallel
This is the standard "heuristics before ML" maturation path. Spam filters, fraud
detection, and autoscalers all began as rules and graduated to models *once the
rules generated enough labeled outcomes to train on*. Starting rule-based isn't a
compromise — it's how you earn the dataset (and the stakeholder trust) that makes
a later ML router justifiable. The config-driven design means that upgrade is a
swap behind the same `Router` interface, not a rewrite.
