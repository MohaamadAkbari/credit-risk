# ADR 0001 — Choose models and policies by expected profit, not by AUC

**Date:** 2026-11-17 · **Status:** Accepted (provisional until the locked test run) · **Related:** D17, D10

## Context

The model estimates the probability that an applicant will have payment difficulties. 8.07% of applicants do (24,825 of 307,511, checked in the data). The business decision is approve, review or decline, and its value is money: a repaid loan earns a margin; a bad loan loses a share (LGD) of the principal.

## Decision

1. The **primary metric** is **expected profit per 1,000 applications** at the chosen policy, reported with a bootstrap confidence interval.
2. **ROC-AUC and PR-AUC** measure ranking quality and are used to compare models, but never alone.
3. **Brier score and calibration curves** are required, because the cutoff is a probability (about 17% with current assumptions).
4. **Thresholds** come from the profit curve, not from 0.5 or from a target approval rate.

## Reasons

- **Accuracy misleads.** A model that approves everyone is about 92% accurate when 8% default, and earns nothing from risk it ignores.
- **AUC measures ranking, not value.** Two models with the same AUC can have different profit, because profit depends on how accurate the probabilities are near the break-even point.
- **Costs are asymmetric.** With 12% margin and 60% LGD, one default wipes out the margin of about five good loans, so errors must be weighed by money.
- **The decision is a threshold on a probability**, so wrong probabilities lead directly to wrong decisions.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Choose by ROC-AUC | Ignores costs and calibration |
| Choose by F1 or accuracy | Poor fit for 8% positives and unequal costs |
| Choose by KS statistic (common in credit) | Useful as a secondary check; still blind to costs |
| Hit a fixed approval rate | Hides the economics; arbitrary |

## Consequences

- Every experiment reports profit; ML metrics are supporting evidence.
- The profit result depends on the money assumptions (D06–D09), which are placeholders. We therefore run sensitivity experiments E2 and E3 and report profit as a range.
- The label is payment difficulty, not write-off, so profit is an estimate of the real P&L.

## Revisit if

Real figures for margin, loss, review cost or reviewer accuracy become available; or the label definition changes.
