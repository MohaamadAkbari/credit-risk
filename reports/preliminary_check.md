# Preliminary check (not the official baseline)

*18 November 2026, updated 19 November. Script: `scripts/preliminary_check.py` (`make preliminary`). Purpose: replace guesses with a first real number before fixing the profit target.*

## What was run

A quick comparison on `application_train` only: a random 70/30 split (stratified, seed 42), 17 inputs from the main table (three external scores, income, loan amounts, employment and registration dates, family size, region, contract type). **Gender and age were not used.** Two models, one run each, untuned: a logistic regression (a stand-in for the old scorecard) and gradient boosting. Profit uses the placeholder economics (margin 12%, LGD 60%), approves anyone whose predicted risk is below the break-even 16.7%, and counts the real outcomes of the 30% hold-out (92,254 applicants).

## Results

| Policy | ROC-AUC | Declined | Default rate among approved | Profit per 1,000 | vs approve everyone | vs scorecard-like |
| --- | --- | --- | --- | --- | --- | --- |
| Approve everyone | — | 0% | 8.07% | 61.9 | — | — |
| Logistic regression, break-even cutoff | 0.731 | 10.0% | 6.24% | 67.5 | +9.1% | — |
| Gradient boosting, break-even cutoff | 0.747 | 11.0% | 5.93% | 68.8 | +11.2% | +1.9% |

Declining a fixed share instead of using the break-even cutoff (gradient boosting): riskiest 5% gives +9.2%, 10% gives +11.0%, 15% gives +10.8%. The riskiest 10% contains 32.4% of the defaults.

Gender check (gradient boosting, break-even cutoff): approval 90.4% for women and 86.1% for men, a ratio of 0.95; among people who repay, 92.1% and 88.9%, a ratio of 0.97.

## What it tells us

1. **A +10% target over approving everyone is reachable**, even with a basic model on the main table (+11.2%).
2. **A +10% target over the scorecard is not.** The gradient-boosting model gains only 1.9% over the logistic regression. Most of the value comes from using any decent risk score at all, not from the fancy model.
3. **The break-even cutoff declines 10 to 11% of applicants**, almost exactly the proposed cap, so the cap and the cutoff barely conflict.
4. **The fairness ratio is not at risk** for gender in this run (0.95 and 0.97 against a threshold of 0.8), even though men default more often.
5. The default rate among approved loans is 5.9 to 6.2%, under the 6.5% target.

## Update, 19 November: profit weighted by loan amount (ADR 0003)

The table above counts every loan as size 1. The Phase 2 review found that risk varies with loan size (large loans are
safer) and that the flat 12% margin misprices short and long loans. The same models and split, re-run with profit
**per 1,000 of principal applied for** (the primary measure since D54) and with a term-scaled margin (experiment E6):

| Policy | Declined (applications / principal) | Default among approved (count / amount) | Unit-weighted | **Amount-weighted** | Amount, term-scaled margin |
| --- | --- | --- | --- | --- | --- |
| Approve everyone | 0% | 8.07% / 7.55% | 61.9 | 65.6 | 75.7 |
| Logistic regression, break-even cutoff | 10.0% / 8.8% | 6.24% / 5.94% | +9.1% | **+7.4%** | +6.4% |
| Gradient boosting, break-even cutoff | 11.0% / 9.5% | 5.93% / 5.67% | +11.2% | **+9.2%** | +8.5% |
| Gradient boosting, per-loan break-even under the term-scaled margin | 15.9% | — | — | — | +9.7% |

Gradient boosting over logistic regression: +1.9% unit-weighted, +1.8% amount-weighted, +2.0% term-scaled.

What changes:

1. **The lift over approving everyone is about 2 points lower when money is counted.** Declining risky applicants saves
   less than the count suggested, because the declined loans are smaller than average. The preliminary model reaches
   +9.2%, **just under the +10% target (D12)**. The target is kept and now measured amount-weighted, and the owner
   re-confirmed it on 19 November. The Phase 4 baselines, which use the bureau and history features this check does not, are judged against it.
2. **The cutoff itself does not move** with a flat margin: margin and loss both scale with the amount, so break-even
   stays 16.7% for every loan.
3. **A term-scaled margin changes the policy.** Each loan gets its own break-even (about 8% for short loans to 23% for
   long ones), and the model declines about 16% of applicants instead of 11%. That would conflict with a 10% decline
   cap (D14), so E6 runs before the cap is decided.
4. The scorecard comparison hardly changes (+1.8% to +2.0%).

## Limits

One run, one split, one seed, no tuning, no confidence intervals, main table only, placeholder economics, and profit counted on a label that means payment difficulty. Treat every number as a rough guide. The official baselines come in Phase 4 with the tested pipeline.
