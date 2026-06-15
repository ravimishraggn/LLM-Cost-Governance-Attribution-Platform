# What we've built so far — a plain-English walkthrough

*Covers Phase 1 (the gateway), Phase 2 (the cost engine), Phase 3
(observability), and Phase 4 (the model router). No code knowledge needed.*

---

## The problem, in one picture

Today your company's AI bill looks like this:

> **OpenAI invoice: $48,000.** Anthropic invoice: $31,000. AWS Bedrock: $12,000.

That's it. Nobody can tell you *which team*, *which project*, or *which feature*
caused that spend. Finance is staring at a single number it can't explain, and
engineering can't answer "who's spending what, and why."

We're building the missing layer that turns that one number into an **itemized,
explainable bill** — like turning "$48,000 in phone charges" into a list of every
call: who made it, how long it was, and what it cost.

---

## What it is (the toll-booth analogy)

Think of a **toll booth** that every AI request must drive through.

- Before the booth: cars (AI calls) zoom straight to the providers. Nobody counts
  them.
- After we add the booth: every car stops for a split second. We write down **who
  it is** (team, project, agent), **what it carried** (how many tokens in and out),
  **how long it took**, and now — **what it cost** — then wave it through.

That booth is the **gateway**. Nothing else changes for the app; it just sends its
request to us instead of straight to OpenAI.

---

## Phase 1 — the booth that writes everything down

We built one entry point that every AI call passes through. Two things make it
useful:

1. **It demands a name tag.** Every call must say which `team`, `project`,
   `agent`, and `use_case` it belongs to. No tag, no service — the call is
   rejected. This is what guarantees we can *always* attribute spend later. (No
   more anonymous cars sneaking through.)
2. **It speaks to all three providers in one language.** OpenAI, Anthropic, and
   Bedrock each format requests and report token counts differently. We built
   small "translators" (adapters) so the booth records every call the same way,
   no matter who served it.

Every call becomes **one tidy row** in a database table.

## Phase 2 — putting a price on each row

Phase 1 captured *how many tokens* each call used. Phase 2 answers *how many
dollars that is*.

- Prices live in a plain, editable file (`config/pricing.yaml`) — not buried in
  code. When OpenAI changes its prices next month (they do, often), someone edits
  one line and clicks "reload." No software release needed.
- Each model has two prices: one for the text you send in, one for the text it
  writes back. We multiply tokens × price and store the result on the row.

---

## Phase 3 — a flight recorder for every call

The cost database answers *"what did it spend?"* Engineers also need *"what
actually happened?"* — the exact prompt, the answer, how long it took, and how
one user request quietly fanned out into a dozen model calls.

So the booth now also files a **flight recording** of each call to **Langfuse**
(an open-source tool built for exactly this). Same name tags as the cost row, so
the money view and the debugging view line up. Now an engineer can click into a
slow or weird call and see everything, while finance keeps using the cost table.

Three promises we built in, because this recording happens on every single call:

- **It never slows a call down** — recordings are batched in the background, not
  sent one-by-one.
- **It can never break a call** — if Langfuse hiccups, the AI request still
  succeeds; we just lose that one recording.
- **It's optional** — off by default; flip it on with a couple of settings.

Think of it like a black box recorder on a plane: always running quietly, never
interfering with the flight, invaluable when you need to investigate.

## Phase 4 — a smart switchboard that picks the cheapest capable model

Up to now the booth only *watched* spending. Phase 4 lets it *reduce* spending.

Using a top-tier model for a trivial task is like taking a taxi to your mailbox.
The **router** is a switchboard at the front of the booth: it takes a quick look
at each request and asks "is this hard or easy?" using simple, transparent rules
(How long is it? Does it contain words like *analyze*, *design*, *reason*? Is it
asking for a long answer?).

- **Easy task** (e.g. "write a 5-word greeting") sent to an expensive model →
  the router quietly swaps it for a cheaper one that does the job fine.
- **Hard task** (e.g. "analyze the competitive landscape") → left on the powerful
  model, untouched.

Every time it downgrades, it records the **estimated savings** — what the pricey
model *would* have cost for the same work. We're careful to call this an
*estimate*: we only ever ran one model, so it's an honest "what-if," not a number
we're pretending is exact.

Two deliberate choices worth knowing:
- **Rules, not AI (for now).** The switchboard uses plain rules, not a machine-
  learning model. Rules are instant, predictable, and easy to explain ("your call
  was downgraded because the prompt was short and had no complex keywords"). Every
  decision we log also becomes training data *if* we later want a smarter,
  ML-based router.
- **It only ever makes things cheaper or leaves them alone** — it never blocks a
  call or upgrades you into a more expensive model by surprise.

---

## Let's simulate a real day

Here are five calls flowing through the booth. (Token counts are realistic; the
per-token prices are the illustrative example rates from `config/pricing.yaml`.)
Watch the last two — the router steps in.

| Who (team / use case)          | Asked for → served      | Tokens in → out | Cost     | Router |
|--------------------------------|-------------------------|-----------------|----------|--------|
| recruiting / resume-screening  | gpt-4o-mini             | 1,200 → 300     | $0.00036 | kept (already cheap) |
| support / ticket-triage        | claude-haiku-4-5        | 800 → 150       | $0.00155 | kept (already cheap) |
| research / market-analysis     | claude-opus-4-8         | 5,000 → 2,000   | $0.22500 | **kept** (complex: "analyze") |
| marketing / tagline            | opus → **haiku**        | 30 → 20         | $0.00013 | **downgraded**, saved ~$0.0018 |
| analytics / yes-no check       | gpt-4o → **gpt-4o-mini** | 40 → 5          | $0.00001 | **downgraded**, saved ~$0.0001 |

How the research call's cost is worked out:

```
input:   5,000 tokens ÷ 1,000,000 × $15.00  = $0.075
output:  2,000 tokens ÷ 1,000,000 × $75.00  = $0.150
total                                        = $0.225
```

Now that every row has an owner *and* a cost, questions that were impossible
yesterday become one-line lookups:

- **"What did the support team spend?"** → add up their rows → `$0.00310`
- **"What's our priciest use case?"** → `market-analysis` ($0.225 — one Opus call
  costs more than 140 of the recruiting calls)
- **"Is anyone using an expensive model for cheap work?"** → group by model and
  look

Scale this up — an agent running 1,000 *simple* calls a day on Opus is
**~$225/day**. The router moving those to Haiku makes it **~$15/day**. That ~$210/
day gap, captured automatically and logged as estimated savings, is the router
earning its keep. (Genuinely complex calls stay on Opus — we don't trade quality
for pennies.)

---

## Why this matters (the "so what")

| Question | Before | Now |
|----------|--------|-----|
| Who spent the money? | Unknown | Every call is tagged by team/project/agent |
| What did *this feature* cost? | Unanswerable | Filter the table by `use_case` |
| Prices changed — now what? | Wait for a code release | Edit one file, reload |
| Paying flagship rates for trivial tasks? | Nobody notices | Auto-routed to a cheaper model |
| Show me everything for an audit | Scattered across 3 vendor dashboards | One queryable table |

Cloud cost tools (like AWS Cost Explorer) can't do this — they see "money spent
at OpenAI," not "tokens spent by the recruiting team's resume parser." We've added
the **meaning** on top of the raw spend.

---

## Where this is going

- **Phase 5 — Dashboard:** a screen for finance and team leads — spend by team
  over time, top use cases, and the routing savings achieved.
- **Phase 6 — Governance:** budgets, alerts when a team overspends, and an audit
  export for compliance.

---

## See it yourself

Once Python 3.11+ is installed:

```bash
pip install -r requirements.txt
python scripts/demo_phase1.py     # fires sample calls, prints the logged rows + cost
```

Every line it prints is one row in the table described above.
