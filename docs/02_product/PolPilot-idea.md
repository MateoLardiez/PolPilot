# PolPilot — Hackathon Scope

> **Reduced scope for hackathon** · April 2026
> Authors: Lucas Calatayud & Wenceslao Hernandez

---

## The problem we solve

82% of Latin American SMBs fail — not for lack of effort, but for lack of access to quality information at the moment of decision. While a corporation has a CFO, an economist, and a legal team working 24/7, the owner of the local hardware store has WhatsApp and their gut feeling.

One of the most critical moments is seeking financing: the owner **doesn't know which loans they qualify for**, doesn't have their financial data organized to present to a bank, and even if they get the loan, **they have no clear plan on how to invest it to generate real value**.

PolPilot closes that gap.

---

## What we're building in this hackathon

An application that does **two things exceptionally well**:

1. **Automatically detects the bank loans an SMB can apply for**, based on their actual financial data.
2. **Generates a strategic capital deployment plan**, explaining in plain language what to do with that money to maximize return.

The interaction channel is **WhatsApp** — the only tool the SMB owner already uses every day, with zero learning curve.

---

## The two active modules

### Module 1 · The CFO (Financial & Cash Flow)

The system's analytical engine. It takes the company's financial data — whether invoices, photos of spreadsheets, voice memos from the owner, or connections to billing systems — and builds a real-time financial picture.

**What it produces:**

- Real and projected cash flow for 30, 60, and 90 days
- Identification of income, expenses, and recurring costs
- Profitability by product or business line
- Detection of overdue clients and accounts receivable
- Business financial health score (0–100)
- Solvency ratios and repayment capacity

**Why it matters for the hackathon:**
This is the data source that powers loan detection. Without a reliable financial snapshot, it's impossible to evaluate whether the company qualifies for a loan or under what conditions.

---

### Module 2 · The Economist (Macroeconomic Context)

Crosses the company's internal data with real-time external economic context. Monitors exchange rates, inflation, interest rates, and sector cycles to provide context for financial decisions.

**What it produces:**

- Alerts on interest rate changes that affect whether taking on debt makes sense
- Analysis of whether current market conditions favor borrowing now vs. waiting
- Real-value adjustment of the company's numbers based on inflation
- Sector context: how similar companies in the same industry are performing

**Why it matters for the hackathon:**
A fixed-rate loan at 29% APR can be an excellent opportunity if projected inflation is 40%, or a trap if inflation drops to 15%. This module gives the owner the context to decide wisely.

---

## The core feature: Loan detection + Credit package

This is the centerpiece of the hackathon. The complete flow:

```
Owner sends their financial data via WhatsApp
        ↓
PolPilot builds their financial profile (CFO Module)
        ↓
Crosses the profile against available credit lines (central bank, banks)
        ↓
Filters the loans the company can actually apply for
        ↓
Generates the Credit Package ready to present to the bank
        ↓
Produces the Strategic Capital Deployment Plan
```

### Credit Package (automatic output)

Automatically generated PDF document that includes:

- Projected cash flow for 90 days
- Calculated solvency ratios
- Demonstrated repayment capacity with real data
- Billing history
- List of available loans with a comparison of terms (rate, term, requirements)

### Strategic Capital Deployment Plan (automatic output)

Once the most suitable loan is identified, PolPilot generates a concrete plan:

- **How much to borrow** and why (based on the real business need, not the maximum available)
- **What to invest it in** with priorities ordered by expected impact
- **Return projection**: how cash flow and profitability change if the investment is made
- **Payment simulation**: monthly cost and whether the business can afford it without compromising liquidity
- **Warning signals**: which indicators to watch to know if the decision is working

---

## Real interaction example

**Owner:** *(sends 20-second voice message)* "Hey, I need cash to buy more stock before winter. I have about $800k in hand but I think I need double. Is there anything I can apply for?"

**PolPilot (Ángela):**
> Gonzalo, I reviewed your numbers. Here's the analysis:
>
> 📊 **Your financial situation:**
> Your average cash flow over the last 3 months is $1.2M/month. Your solvency ratio is 1.8 — that's healthy.
>
> 🏦 **You pre-qualify for 2 credit lines:**
>
> **Option A — Central Bank SMB Line · 29% APR**
> You can access up to $2.4M. With projected inflation at 38%, the real rate is negative — this is favorable.
>
> **Option B — National Bank · Working Capital · 34% APR**
> Up to $1.8M, with an 18-month term. Estimated monthly payment: $128k. Your cash flow can handle it without issues.
>
> 📋 **I generated your Credit Package, ready for the bank.** It includes your 90-day cash flow and solvency ratios.
>
> 💡 **Suggested investment plan for the $1.6M:**
> — $900k in heating stock (high winter turnover, 28% margin)
> — $400k to cancel debt with Supplier A (gives you 60 more days of terms)
> — $300k as an operational liquidity buffer
>
> Projection: if you execute this plan, your EBITDA increases 18% in the quarter.

---

## Tech stack (simplified for hackathon)

| Layer | Technology |
|-------|-----------|
| Input channel | WhatsApp Business API (via Twilio or 360dialog) |
| Backend / API | Node.js + FastAPI (Python) |
| Main LLM | Claude Opus (via Anthropic API) |
| Audio processing | Whisper (OpenAI) |
| Document OCR | Google Vision API |
| Database | PostgreSQL + pgvector |
| PDF generation | ReportLab / WeasyPrint |
| External data sources | Central Bank API, National Statistics, Tax Authority |

---

## Hackathon success metrics

- Onboarding time until first deliverable: **under 5 minutes**
- Accuracy in detecting applicable loans: **at least 3 real and current options**
- Quality of the strategic plan: evaluated by jury with real-world applicability criteria
- Functional end-to-end demo via WhatsApp

---

## What is NOT in scope (for this version)

- Legal / Regulatory module
- Competitive / Sector intelligence module
- Purchasing & Inventory module
- Real Value module (ROIC, WACC, EVA)
- Collective intelligence / anonymous cross-user data
- Integration with accounting systems (Colppy, Contabilium)
- Dual accounting (operational vs. tax layer)
- Alternative credit scoring and fintech partnerships (Phase 2)

---

*PolPilot · Hackathon Build · April 2026*
