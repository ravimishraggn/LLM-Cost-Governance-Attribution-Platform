# ADR-003: External, Updatable Pricing Config vs. Hardcoded Prices

## Status
Accepted

## Context
The cost of every call is `tokens × per-token price`. The token counts come
from the provider response; the prices come from us. The open question is where
those prices live.

LLM pricing is unusually volatile for a "constant":
- Providers cut prices several times a year and add new models monthly.
- The *same* model is priced differently per provider (Anthropic direct vs. the
  same Claude model served through Bedrock) and per tier (standard, batch,
  provisioned throughput, committed-use discounts).
- Input and output tokens are priced separately, often at very different rates.

If prices were constants in code, every provider price change would require a
code edit, a review, a build, and a deploy — and until that ships, every
chargeback number is silently wrong. Finance cannot trust a cost system whose
accuracy depends on the engineering release cadence.

## Decision
Externalize pricing into a **version-controlled YAML file** (`config/pricing.yaml`)
loaded at runtime, keyed by `(provider, model)` with separate `input` / `output`
rates per 1M tokens. A `PricingBook` resolves a model to a price (with a prefix
fallback so dated model snapshots still match), and `cost.py` calls it for every
completion. A `POST /admin/reload-pricing` endpoint reloads the file without a
restart, so a price change is a **one-line edit + reload**, not a deploy.

Keying by `(provider, model)` — not by model alone — is deliberate: it's the only
way to represent the same model costing different amounts on different providers.

## Alternatives Considered
- **Hardcoded constants / a Python dict in code:** rejected — couples price
  accuracy to the deploy pipeline; a price change can't ship faster than code.
- **Prices in the database, edited via admin UI:** a reasonable *future* step
  (auditable, multi-user), but heavier than the MVP needs and harder to review.
  YAML in git gives us change history, code review, and rollback for free today.
- **Live-fetch from provider pricing APIs:** attractive but the providers don't
  offer uniform, reliable pricing APIs; this becomes a sync job feeding the same
  YAML/table later, not a reason to skip the config now.

## Consequences
- **Easier:** update prices without a deploy; full audit trail via git history;
  represent per-provider and per-model rate differences cleanly; expose current
  rates via `GET /pricing`.
- **Harder / accepted trade-offs:** the file is a source of truth someone must
  keep current — a stale file means wrong (but consistently wrong, and fixable)
  numbers. Unpriced models record `$0.00` and log a warning rather than guessing,
  so gaps are visible. A future ADR can add validation/alerting on staleness.

## Real-World Parallel
This is the FinOps equivalent of a **rate card** kept outside the billing engine.
Cloud cost tools don't hardcode EC2 prices into their binaries — they ingest a
published, dated price list. Treating LLM prices the same way (config as data,
versioned, hot-reloadable) is what lets a cost platform stay accurate in a market
where the vendors re-price every few months.
