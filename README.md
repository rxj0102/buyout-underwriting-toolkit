# Buyout Underwriting Toolkit

A Python toolkit that models the core underwriting workflow of a private
equity **Investment Analyst** at a **buy-and-build ("roll-up") platform**
focused on durable, essential-services industries — think residential
HVAC, plumbing, pest control, or commercial landscaping. It walks the
same path a real deal would: source and prioritize targets, value one,
structure an LBO around it, model it as a bolt-on to an existing
platform, track diligence, and write it up for the Investment Committee
(IC).

> **Synthetic-data disclaimer:** Every company, financial figure, name,
> and diligence finding in this repository is **synthetically
> generated** with seeded random number generators. Nothing here
> represents a real company, a real transaction, or real financial data.
> The methodology mirrors standard lower-middle-market PE practice, but
> assumptions (multiples, leverage, growth rates, synergy %) are
> illustrative and simplified for a demonstration project. **This is not
> investment advice and should not be used to underwrite a real deal.**

## The scenario

A sponsor runs a buy-and-build strategy in fragmented, essential-services
trades — businesses that are recession-resistant, non-discretionary, and
ripe for consolidation. The firm already owns one regional platform
company and is sourcing bolt-on acquisitions across four sub-sectors:

- Residential HVAC Services
- Plumbing & Drain Services
- Pest & Termite Control
- Commercial Landscaping & Grounds Maintenance

An Investment Analyst's job is to build and prioritize the pipeline,
underwrite valuation and returns on promising targets, structure the
acquisition financing, quantify the synergy case for folding a target
into the existing platform, track due diligence to closure, and package
it all into an IC memo.

## Project structure

```
buyout_toolkit/
    deal_pipeline.py        # 1. Synthetic pipeline + scoring/prioritization
    valuation_model.py      # 2. EBITDA-multiple + DCF cross-check valuation
    lbo_model.py             # 3. Sources & uses + 5-yr LBO + IRR/MOIC by case
    addon_synergy_model.py  # 4. Revenue/cost synergies as a platform bolt-on
    diligence_tracker.py    # 5. DD checklist + readiness rollup
    investment_memo.py      # 6. IC memo assembled from the modules above
tests/
    test_*.py                # pytest suite (35 tests)
requirements.txt
README.md
```

Every module is runnable directly (`python3 -m buyout_toolkit.<module>`)
and prints a worked example using the top-ranked synthetic target.

## Methodology by module

### 1. `deal_pipeline.py` — sourcing & prioritization

Generates 40-60 synthetic acquisition targets spread across the four
sub-sectors, each with revenue, EBITDA margin, growth rate, recurring
revenue mix, customer concentration, owner age, succession situation, and
outreach status. Three scoring pillars, each 0-100, roll up into a single
priority score:

- **Strategic fit** — how central the sub-sector is to the roll-up
  thesis, recurring-revenue/cross-sell potential, footprint density in
  the platform's existing states, and multi-location scalability.
- **Financial quality** — EBITDA margin, growth, customer concentration
  risk, and a "sweet spot" revenue size ($8M-$25M) typical of a fundable
  bolt-on.
- **Sourcing feasibility** — owner succession urgency (used as a proxy
  for near-term willingness to transact) and how far outreach has
  already progressed.

`rank_pipeline()` scores and sorts the full pipeline; the weighting
(35% strategic fit / 40% financial quality / 25% sourcing feasibility) is
configurable.

### 2. `valuation_model.py` — valuation cross-check

For a single target, produces:

- An **EBITDA-multiple** valuation using low/base/high multiples
  calibrated by sub-sector.
- A **DCF** with a 5-year explicit forecast (growth and margin fading to
  long-run rates), unlevered free cash flow, and a Gordon-growth terminal
  value discounted at the platform's required return.
- A **blended enterprise value range** that cross-checks the two methods,
  and a corresponding **equity value range** (EV less the target's net
  debt, consistent with a cash-free, debt-free deal).

### 3. `lbo_model.py` — acquisition financing & returns

Builds a **sources & uses table** (purchase EV + fees = senior debt +
seller note + sponsor equity, which balance by construction) and projects
a **5-year operating and debt-paydown schedule**: EBITDA growth, cash
interest, mandatory amortization, and a 100% free-cash-flow sweep that
pays down senior debt first, then the PIK-accruing seller note. Exit is
modeled at a terminal EBITDA multiple in **base, upside, and downside**
cases (varying growth, margin trajectory, and exit multiple), producing
platform-level **IRR and MOIC** for each case.

### 4. `addon_synergy_model.py` — the bolt-on case

Models the target as an add-on to the firm's existing (also synthetic)
platform company. Quantifies three synergy levers, each ramped linearly
to full run-rate over 3 years:

- **Cross-sell revenue synergy** — incremental revenue from selling the
  platform's other service lines into the target's customer base, with
  an incremental EBITDA flow-through margin.
- **Overhead consolidation** — corporate/SG&A cost take-out.
- **Purchasing scale** — procurement savings from combined buying power.

It then compares **combined platform-level IRR/MOIC with vs. without**
those synergies being realized, isolating the synergy delta.

### 5. `diligence_tracker.py` — due diligence

A 20-30 item checklist spanning **Financial, Legal, Operational, and
Commercial** workstreams, each item with an owner, a status (Not
Started / In Progress / Complete / Flagged), and a risk flag (None / Low
/ Medium / High). `compute_readiness()` rolls this up into overall
completion %, per-workstream completion, outstanding red/medium flags,
and a **deal readiness verdict** (blocked on any open HIGH flag,
otherwise gated by completion % and open MEDIUM flags).

### 6. `investment_memo.py` — the IC memo

Assembles a structured memo — thesis, financial profile, valuation
summary, proposed offer terms & structure, standalone and synergy-case
returns, key risks, diligence status, and a recommendation — by calling
into every module above rather than re-deriving any figure. The
recommendation logic checks base-case returns against IRR/MOIC hurdles,
confirms the downside case is capital-protective, and blocks outright on
any unresolved HIGH-risk diligence flag.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
# Rank the synthetic pipeline
python3 -m buyout_toolkit.deal_pipeline

# Value the top-ranked target
python3 -m buyout_toolkit.valuation_model

# Run the LBO (base/upside/downside)
python3 -m buyout_toolkit.lbo_model

# Compare returns with vs. without add-on synergies
python3 -m buyout_toolkit.addon_synergy_model

# Generate a diligence tracker + readiness verdict
python3 -m buyout_toolkit.diligence_tracker

# Print the full IC memo (pulls from every module above)
python3 -m buyout_toolkit.investment_memo
```

## Running the tests

```bash
python3 -m pytest -q
```

The suite (35 tests) covers pipeline scoring logic, sources & uses
balancing, debt paydown math, synergy delta calculations, and diligence
rollup logic, in addition to valuation cross-checks and end-to-end memo
assembly.
