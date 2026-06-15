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

---

## Phase 3 — Tracing must never slow down or break a call

**Challenge.** Adding Langfuse to the gateway introduced a tension: the tracing
call sits on the critical path of every LLM request. Two failure modes appeared
in the naive integration:
1. **Latency.** Calling `langfuse.flush()` after each request makes a synchronous
   network round-trip to Langfuse *per call* — adding tens to hundreds of
   milliseconds to a path whose entire job is to be a thin, fast pass-through.
2. **Blast radius.** If Langfuse is briefly unreachable (or the SDK raises on a
   payload shape it doesn't like), an unguarded trace call would turn an
   otherwise-successful LLM response into a `500`. Observability would be *causing*
   outages — the opposite of its purpose.

**Resolution.** Three guardrails, all in `observability.py` + the gateway:
1. **Don't flush per call.** Rely on the SDK's background batching and flush once
   at shutdown (FastAPI lifespan). Tracing comes off the latency hot path.
2. **Wrap everything, twice.** Each tracer self-guards its Langfuse calls, *and*
   the gateway wraps `trace_call()` in its own try/except as defense-in-depth — so
   even a misbehaving tracer implementation can't break a request. A unit test
   injects a deliberately-exploding tracer and asserts the call still succeeds.
3. **Off by default, opt-in.** A `NoOpTracer` is used unless tracing is explicitly
   enabled with credentials present, so tests, local dev, and mock runs carry zero
   tracing overhead or config burden.

This mirrors the platform's broader **fail-open** stance (see the gateway-down
discussion): cost accuracy lives in the database (the ledger), while Langfuse is
the *debugging lens* — a Langfuse problem degrades visibility, never correctness.

---

## Phase 4 — How do you measure savings you didn't spend?

**Challenge.** The router's whole pitch is "we saved you money by using a cheaper
model." But savings are a **counterfactual** — to know the true saving you'd have
to run *both* the expensive and the cheap model on the same request and compare,
which would double the cost and defeat the purpose. You only ever actually run
one model. So what number do you put in the `estimated_savings_usd` column, and
how do you avoid it being marketing fiction?

A subtler trap: the expensive model wouldn't have produced the *same* number of
output tokens as the cheap one, so even a "what would it have cost" estimate is
not exact.

**Resolution.** Two decisions, both about being honest rather than impressive:
1. **Compute the counterfactual against the served call's actual token usage** —
   take the input/output tokens the cheap model really used and price them at the
   *requested* (expensive) model's rate. `savings = expensive_rate_cost −
   actual_cost`. It's a defensible apples-ish-to-apples proxy that never requires
   a second API call.
2. **Name it `estimated_savings` everywhere** — column, response field, ADR, and
   dashboard — and document in ADR-005 that it's a counterfactual, not a measured
   A/B. Overclaiming here would poison finance's trust in every other number the
   platform produces.

This also pays a dividend: every routed call now logs (request features →
decision → outcome → estimated saving), which is exactly the labeled dataset a
future ML-based router (the road not taken in ADR-005) would need to train on.

---

## Phase 5 — Dashboard logic that survives the database (and the UI)

**Challenge.** Two coupling traps appear when you build a dashboard against a
live DB:
1. **SQL dialect lock-in.** The natural way to chart "cost per team per day" is a
   `GROUP BY date_trunc('day', created_at)` — but `date_trunc` is Postgres;
   SQLite uses `strftime`. Writing the aggregation in SQL would bind the dashboard
   to one database and silently break when we move from the SQLite MVP to Postgres
   in production.
2. **Logic trapped in the UI.** Aggregation written inline in Streamlit callbacks
   can't be unit-tested without spinning up a browser, and can't be reused by a
   future React app or a scheduled CSV export.

**Resolution.** Split the dashboard into two layers:
- A **pure-pandas reporting layer** (`reporting.py`): `load_calls()` pulls the raw
  rows once, and every metric (`cost_by_model`, `top_use_cases`,
  `budget_vs_actual`, ...) is a plain function `DataFrame -> DataFrame`. Grouping
  happens in pandas, so the logic is byte-for-byte identical on SQLite and
  Postgres. These functions are unit-tested with hand-built frames — no DB, no UI.
- A **thin Streamlit view** (`dashboard/app.py`) that only loads, filters, and
  draws. It holds no business logic.

Two subtler details fell out of this: `budget_vs_actual` must include teams that
have a budget but *zero* spend (union the configured teams with the spending
teams) and must count only the **current month** (a period mask), or the alerts
lie. And because Streamlit re-runs the whole script on every interaction,
`load_calls()` is wrapped in `@st.cache_data` so filtering doesn't hammer the DB.

The payoff is the ADR-006 thesis made real: when we outgrow Streamlit, we rebuild
the *view*, not the analytics.

---

## Phase 6 — Alerting that informs without spamming

**Challenge.** Governance evaluates budgets on *every call* (so a breach is caught
in real time, in the same transaction as the call that caused it). But a team
that's over budget is over budget on its next call too, and the one after that —
naively recording a violation each time would write thousands of duplicate
"research is over budget" rows in an afternoon, burying the one event that
mattered and making the audit export useless.

A second subtlety: "month-to-date spend" must mean *this calendar month*, and the
query has to give the same answer on SQLite (MVP) and Postgres (prod) — but the
two disagree on date functions (`strftime` vs `date_trunc`).

**Resolution.**
1. **De-duplicate on `(team, period, severity)`.** A `PolicyViolation` is recorded
   only if one of that severity doesn't already exist for that team in that
   `YYYY-MM` period. So a sustained overspend produces exactly one WARN event and
   one OVER event per month — a clean, auditable timeline, not noise.
2. **Compute the period with explicit datetime bounds**, not DB date functions:
   `created_at >= first-of-month AND < first-of-next-month`. Identical results on
   SQLite and Postgres, same lesson as the Phase 5 reporting layer.

A design decision fell out of this too (documented in ADR-007): we **observe and
record** rather than hard-block calls over budget. Blocking production LLM calls
on a cost threshold could take down a feature over money; the fail-open stance is
to record the violation, surface it, and let humans decide — blocking can become
an opt-in *config* flag later, never a hardcoded rule.
