# Explain It Simply

*A plain-English tour of the LLM Cost Governance & Attribution Platform. No technical background needed. Readable in about five minutes.*

---

## 1. The Problem

Companies now use AI assistants everywhere, and every time someone uses one, it costs the company a little money. But nobody is writing down *who* used it, *what for*, or *how much it cost* — so the bill at the end of the month is one big number with no explanation.

Imagine every employee has a company credit card, but none of them keep receipts. At month-end you get a huge statement and no idea who bought what. This platform is the receipts — for AI usage.

It's sneakier than it sounds, too: a single question from one employee can quietly set off ten or more separate AI requests behind the scenes (modern AI assistants often work in teams of smaller helpers). So the costs pile up invisibly, and the ordinary tools companies use to track cloud bills can't help — they can see "we paid the AI company $50,000," but not *which* team or *which* task caused it.

---

## 2. The One-Sentence Summary

This platform sits in the middle of every AI request a company makes, quietly tags it, prices it, and records it — so the company always knows who is spending what on AI, and can cut waste without anyone changing how they work.

---

## 3. Follow ONE Request, Start to Finish

Let's follow a real example.

**Priya works on the Recruiting team.** She asks her AI assistant: *"Summarize these 50 resumes for me."* Here is exactly what happens.

**Step 1 — Priya makes her request (the trigger).**
She types her request and hits enter. From her point of view, that's it — she's just asking the AI for help, the same as always.

**Step 2 — The request goes through the "gateway" first, and gets a name tag.**
Instead of going straight to the AI, her request first passes through a checkpoint we call the *gateway* (think of it as a single front door that every AI request must walk through). At the door, the request gets a **name tag** — exactly like the badge you're given at a conference. The tag says: *Recruiting team, resume-screening project, "resume summarizer" assistant, purpose: summarizing.* No tag, no entry — a request with no name tag is turned away.

*Why force everything through one door?* Because the alternative — asking every team to remember to label their own AI usage — never holds up: some forget, some label things differently, and the records end up full of holes. One door, one rulebook, no gaps. That's what makes the final numbers trustworthy.

**Step 3 — The system decides which AI to use (routing).**
The gateway looks at the request and asks: *"Is this simple, or is it hard?"* Summarizing a resume is fairly routine, so it picks a **cheaper, lighter AI model** instead of the most expensive one. (More on this in section 6.) Hard, complex requests get sent to the powerful expensive model — but easy ones don't waste money on it.

**Step 4 — A receipt is written.**
The system records the details of this request like a shop saving a receipt: who asked, what for, which AI was used, how many words went in and out, how much it cost, and how long it took.

**Step 5 — The actual AI does the work.**
Only now does the request go out to the real AI provider (the outside company that runs the AI — like OpenAI, Anthropic, or Amazon). It reads the resumes and writes the summaries.

The company actually uses several of these providers, and each one "speaks" in its own format — like appliances from different countries using different plugs and voltages. The gateway acts as a **universal travel adapter**: whichever provider does the work, the request goes out smoothly and the receipt always comes back in one consistent shape.

**Step 6 — Priya gets her answer.**
The summary comes straight back to Priya. Her experience is completely unchanged — she just got her summaries, a second or two later. She never sees the tag, the cost, or the receipt.

**Step 7 — What happened behind the scenes.**
Without Priya ever noticing, the company now has a permanent, labeled record: *the Recruiting team spent this much, on this task, at this moment.* That record is the whole point.

```
  [ Priya: "Summarize these 50 resumes" ]
            |
            v
  [ GATEWAY adds a name tag:
    "Recruiting team / resume summarizer / purpose: summarizing" ]
            |
            v
  [ ROUTER asks: "Is this simple?"  -> YES -> picks the cheaper AI ]
            |
            v
  [ RECEIPT saved: who, what, which AI, cost, how long ]
            |
            v
  [ Sends to the AI provider, gets the summaries back ]
            |
            v
  [ Priya gets her summaries — she never knew any of this happened ]
```

---

## 4. What the Data Actually Looks Like

Here is the single receipt saved for Priya's request, in plain terms:

| What | Example Value |
|------|---------------|
| Who used it | Recruiting team |
| What for | Summarizing resumes |
| Which AI model | The cheaper model (the task was simple) |
| How much it cost | $0.002 |
| How long it took | 1.2 seconds |
| Money saved by using the cheaper AI | About $0.03 (vs. the expensive model) |
| Date and time | 15 June 2026, 2:14 pm |

One request, one tidy row. Nothing fancy — but multiply it by thousands and it becomes powerful.

---

## 5. What This Adds Up To (The Dashboard)

Now imagine collecting thousands of these receipts every day, from every team. The platform adds them all up onto a single screen called the *dashboard* (a one-page summary, like the front page of a report).

It's like a monthly credit card statement — but instead of one person's purchases, it shows **every team's AI usage**. Leadership can see, at a glance: which teams spend the most, which tasks cost the most, how spending is trending over the month, and how much money the "use the cheaper AI" feature has saved. Questions that used to be impossible to answer ("why is our AI bill so high, and who caused it?") become a quick look at a chart.

---

## 6. The "Smart" Parts, Explained Simply

- **Choosing the right AI for the job (routing).** The system automatically sends easy tasks to a cheap AI and hard tasks to a powerful one. *Like grabbing a pocket calculator for simple sums, but hiring an accountant for your complicated taxes — you don't pay accountant rates to add two numbers.*

- **Budget alerts.** Each team gets a monthly spending limit, and the system warns when they're getting close or have gone over. *Like your phone provider texting "you've used 90% of your data plan" before you get a shock on the bill.*

- **Behind-the-scenes tracking (observability).** Every request can be traced step by step — what was asked, what came back, and how long each part took. *Like a flight tracker: you can follow exactly where a request went and where any delay happened.* We didn't build this from scratch — we use a proven, ready-made tool that the company can run on its own computers, so sensitive data never has to leave the building (which matters a lot to banks and other regulated firms).

- **Always-on, never in the way (reliability).** All this tagging, pricing, and recording is built to be invisible and safe: if any of it ever hiccups, the request still goes through and the person still gets their answer. *Like a shop whose card reader keeps working even when the receipt printer jams — you still walk out with your shopping.*

- **Change the rules without rebuilding (settings, not code).** The prices, the "easy vs. hard" rules, and each team's budget all live in simple settings files. Finance or operations can change them in seconds. *Like editing a spreadsheet yourself instead of filing a ticket and waiting on the IT department.*

---

## 7. Why This Matters

- **Saves money.** By sending easy tasks to cheaper AIs, a company can cut its AI bill substantially — on routine work the savings can be very large (the difference between a premium and a budget model is often 10x or more per request).
- **Stops surprises.** No more "why is our AI bill so high?" at month-end. Spending is visible every day, with alerts before limits are crossed.
- **Builds trust.** Every team can see its own usage. Nothing is hidden, and the numbers are explainable, so finance and engineering stop arguing about a mystery total.
- **Keeps things compliant.** Regulated companies (like banks and financial firms) are required to keep complete records of how they use technology. This platform produces exactly that: a full, exportable history of every AI request, ready for an audit.

---

## 8. What's Still Manual / What's Next

A few honest limits today:

- **It only sees AI that goes through the front door.** If someone uses an AI tool directly, bypassing the platform, we wouldn't see that usage yet. Encouraging (or requiring) everyone to go through the gateway is the next step.
- **The cheap-vs-expensive decision uses simple rules, not learning.** It decides "easy or hard" using straightforward checks (like how long the request is). It works well, but a future version could learn from past requests to make smarter choices.
- **Prices are kept up to date by hand.** AI providers change their prices often. Today someone makes a quick edit to a settings file (deliberately easy — no software rebuild), but a future version could pull the latest prices automatically.
- **The savings figure is a careful estimate, not a guarantee.** We record how much *would* have been spent on the expensive AI versus what we actually spent — an honest "what-if," since we only ever run one AI per request.
- **It alerts, it doesn't block.** If a team goes over budget, the system raises a flag rather than cutting off their AI — because suddenly blocking a live tool could break someone's work. Blocking could be switched on later if a company wants it.
