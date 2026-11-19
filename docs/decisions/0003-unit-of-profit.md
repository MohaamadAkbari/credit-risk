# ADR 0003 — Weight profit by loan amount; test a term-scaled margin

**Date:** 2026-11-19 · **Status:** Accepted (engineer, Phase 2 review); target re-confirmation open · **Related:** D05, D06, D10, D12, D14, D54, E6

## Context

Until now profit was computed with every loan counted as size 1 (`scripts/preliminary_check.py`, "loan size = 1").
The Phase 2 review (`docs/04_manager_review_phase2.md`, finding 1) checked what the EDA had not: risk is not the
same across loan sizes or loan lengths.

| Loan amount (fifths) | Default | Loan term in months (fifths) | Default |
| --- | --- | --- | --- |
| up to 255k | 7.2% | 8–15 | 8.1% |
| 255k–432k | 9.2% | 15–20 | 9.9% |
| 432k–604k | 10.1% | 20–22 | 9.7% |
| 604k–900k | 7.9% | 22–30 | 6.2% |
| above 900k | 6.1% | 30–45 | 6.5% |

Weighted by money lent, the default rate is 7.52%, not 8.07%. The margin is flat at 12% per loan, but the term
(credit ÷ annuity) runs from 9.5 to 34.5 months between the 5th and 95th percentiles.

## Decision

1. **Primary measure: profit per 1,000 of principal applied for** (each loan weighted by `AMT_CREDIT`). It is still a
   share of principal, so D05 holds and no currency is needed. The unit-weighted figure is reported next to it.
2. **The margin stays flat at 12% per loan as the primary assumption** (D06). A **term-scaled margin** is a sensitivity
   variant, experiment **E6**: lifetime margin = 12% a year × term in years × the average outstanding share of an
   equal-instalment loan, (n + 1) / 2n. It gives 10.5% for the median loan, 5.3% to 17.8% between the 5th and 95th
   percentiles, and an amount-weighted mean of 13.0%. The flat 12% is therefore right on average but wrong for short and
   long loans.
3. `configs/economics.yaml` records both: `profit_weighting: amount` and `margin_model: flat` (with `term_scaled` for E6).

## What changes, and what does not

- **The approve / decline cutoff does not move** under a flat margin. When margin and loss are both shares of the amount,
  a loan is worth approving when PD < margin / (margin + LGD), whatever its size. Break-even stays 16.7% (D10).
  (The review said the cutoff "may be in the wrong place". That holds only for the term-scaled margin; the correction is noted there.)
- **The measured lift falls.** Preliminary check, same model and split as before (`reports/preliminary_check.md`):

  | Gradient boosting, break-even cutoff | Unit-weighted | Amount-weighted | Amount, term-scaled margin |
  | --- | --- | --- | --- |
  | Profit vs approving everyone | +11.2% | **+9.2%** | +8.5% (+9.7% with per-loan cutoffs) |
  | vs scorecard-like model | +1.9% | +1.8% | +2.0% |

  Large loans are safer, so declining risky applicants saves less money than the count-based measure suggested.
- **Capacity-limited choices do depend on the amount.** A reviewed file is worth more on a large loan, so the review band
  (E1) is filled by expected value in money, not by count, and the decline cap (D14) is reported both as a share of
  applications and as a share of principal.
- **A term-scaled margin moves the cutoff per loan**: break-even runs from about 8% for short loans to about 23% for
  long ones, and the preliminary model then declines about 16% of applicants, against 11% with the flat margin. This
  bears directly on the 10% decline cap (D14) and is tested in E6 before E4 settles the cap.

## Caveats

- **Label window.** `TARGET` counts payment difficulty in the first Y instalments. Long loans have more of their life after
  that window, so part of their lower default rate may come from the label, not from the borrower. This cannot be tested
  in this data. It makes the term-scaled margin look slightly better than it is, which is one more reason to keep it as a
  sensitivity rather than the primary assumption.
- **Revolving loans.** Their "principal" is a credit limit, not a drawn amount, and credit ÷ annuity is not a real term.
  Full-principal exposure (ADR 0002) is even more conservative for them. With 9.5% of rows they move the totals little.
- All numbers are from one untuned preliminary run.

## The target (D12)

D12 (+10% over approving everyone) was confirmed by the owner on unit-weighted numbers. Under the amount-weighted
measure the preliminary model reaches **+9.2%**, just under the target. The target is **kept unchanged** and is now
measured amount-weighted. The preliminary model uses 17 main-table inputs; stages B and C add the bureau and history
signal (18 of the 30 strongest single features carry bureau or history information), so the target is still plausible, but it is no longer shown to be
reachable. **The owner should re-confirm D12 under this measure**, or restate it, after the Phase 4 baselines.

## Alternatives considered

| Alternative | Why not |
| --- | --- |
| Keep unit weights | Profit is money; counting a 45k loan like a 4m loan misstates it |
| Make the term-scaled margin primary | Rests on the same weak annual-margin source, and the label window flatters long loans |
| Dollar amounts | Currency unknown (D05) |

## Revisit if

Real per-product margins become available, or E6 shows the conclusion changes between flat and term-scaled margins.
