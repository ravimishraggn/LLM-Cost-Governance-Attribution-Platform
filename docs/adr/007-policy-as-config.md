# ADR-007: Governance as Policy-as-Config vs. Hardcoded Rules

## Status
Accepted

## Context
Phase 6 adds enforcement: budgets per team, a recorded **policy-violation** event
when a team crosses its threshold, and an audit export for compliance. The
question is where the *policy* lives — the budget amounts, the alert thresholds,
and (later) any allow/deny rules.

Governance policy is owned by people who don't ship code: Finance sets budgets,
Compliance defines what must be audited. Policy also changes on a different clock
than the application — a quarterly budget reset, a new team onboarding, a
threshold tightened after an overspend. And in regulated settings you must be
able to answer "what was the policy on date X, and who changed it?"

## Decision
Treat governance as **policy-as-config**. Budgets and thresholds live in
`config/budgets.yaml` (loaded by `budgets.py`), not in code. The governance engine
(`governance.py`) contains only *mechanism* — compute month-to-date spend, compare
to the configured budget, record a de-duplicated `PolicyViolation` — and reads the
*policy* from config. Violations are written to a queryable table; the audit
export streams the full call log (and violations) as CSV. Config is hot-reloadable
(`POST /admin/reload-budgets`).

## Alternatives Considered
- **Hardcoded limits / `if team == "research": budget = 600`:** rejected — couples
  policy to deploys, makes Finance file an engineering ticket to change a number,
  and scatters policy across the codebase where it can't be reviewed as a whole.
- **Budgets in a database table edited via admin UI:** a reasonable future step
  (multi-user editing, server-side audit of changes). For the MVP, YAML-in-git
  already gives change history, code review, and rollback for free; a UI can come
  when non-technical owners need to self-serve edits.
- **Enforce by blocking calls over budget:** rejected for now in favour of
  *observe-and-record*. Hard-blocking LLM calls on a budget breach risks taking
  down production features over a cost threshold; the platform's stance is
  fail-open (record the violation, alert, let humans decide). Blocking can later
  be an opt-in policy — itself a config flag.

## Consequences
- **Easier:** Finance/Compliance change budgets and thresholds without a deploy;
  policy is one reviewable file with full git history; the same config drives both
  the dashboard's budget-vs-actual view and the violation engine, so they can't
  drift; violations are queryable and exportable for audit.
- **Harder / accepted:** YAML in git means changes go through whoever owns the
  repo (not yet self-service for Finance) and there's no server-side record of
  *who* changed a budget beyond git blame. De-duplication logic must be right so
  alerts neither spam nor go missing. These are acceptable for the MVP and have
  clear upgrade paths (DB-backed policy + admin UI).

## Real-World Parallel
This is the same separation cloud governance tools enforce: AWS Budgets, Azure
Policy, and Open Policy Agent all keep *policy* as declarative data, evaluated by
a generic engine — precisely so the people who own the policy aren't the people
who own the engine. It also mirrors the audit-trail requirement behind frameworks
like the EU AI Act: a complete, queryable, exportable record of usage and of the
policy decisions applied to it. Cost governance and compliance governance share
the same backbone — a trustworthy ledger plus externalized, versioned policy.
