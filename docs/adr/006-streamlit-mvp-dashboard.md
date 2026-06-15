# ADR-006: Streamlit for the MVP Dashboard vs. a Full React App

## Status
Accepted

## Context
The platform's data is only valuable if stakeholders can *see* it. Phase 5 needs
a dashboard showing spend by team/project over time, cost by model, top use
cases, routing savings, and budget-vs-actual with alerts.

The audience is internal — Finance/FinOps, team leads, and a central AI-Ops
function — not external customers. The priority is **time-to-insight**: getting a
trustworthy, iterable view in front of stakeholders quickly so the data model and
the questions can be validated. The data volume is modest (one row per call) and
the interactions are read-mostly (filter, group, chart).

## Decision
Build the MVP dashboard in **Streamlit**, reading from the same call-log DB via a
testable reporting layer (`reporting.py`, pure pandas functions). Charts use
Plotly; budgets come from config (`budgets.yaml`). The UI file is thin — all
aggregation logic lives in `reporting.py`, decoupled from Streamlit.

## Alternatives Considered
- **Full React/Next.js app + charting lib + API endpoints:** rejected for the MVP.
  It's the right answer for a polished, multi-tenant, customer-facing product, but
  it's weeks of work (components, state, auth, build/deploy, a reporting API) to
  answer questions we can answer in an afternoon with Streamlit. Premature for a
  tool whose data model is still being validated.
- **A BI tool (Metabase / Superset / Looker):** strong for ad-hoc exploration and
  worth revisiting, but adds an external service to operate and makes bespoke
  views (budget-vs-actual with our alert semantics, the counterfactual savings
  framing) awkward compared to code we control.
- **Notebook (Jupyter) reports:** great for analysis, poor as a living dashboard
  for non-technical stakeholders.

## Consequences
- **Easier:** a working, shareable dashboard in hours; pure-Python so the team
  needs no frontend skills; the reporting layer is unit-tested and reusable by
  whatever UI comes next.
- **Harder / accepted:** Streamlit's polish, theming, and concurrency ceiling are
  lower than a bespoke React app; it re-runs the script per interaction (fine at
  this data scale, mitigated with `@st.cache_data`); and it's a separate process
  from the FastAPI gateway. These are acceptable for an internal MVP. Because the
  aggregation logic is isolated in `reporting.py`, swapping Streamlit for React
  later means rebuilding the *view*, not the analytics.

## Real-World Parallel
This is the classic "spreadsheet/Streamlit first, productionize once it earns it"
pattern. Internal data products almost always start as the fastest thing that
shows real numbers; teams invest in a hardened React/BI surface only after the
metrics, definitions, and audience are proven. Keeping the analytics behind a
clean interface is what makes that later investment cheap.
