# Problem brief (Phase 0)

*17 November 2026. One page. Details and reasons: `decision_log.md`; formulation: `02_ml_formulation.md`.*

## The problem in one paragraph

A consumer lender serves many applicants with little or no credit history. Bureau scores say little about them, so the lender either declines good applicants (lost margin) or approves bad ones (lost principal). We build a system that scores every application and chooses **approve, manual review or decline**, to maximise expected profit while explaining every decline.

## User and decision

| Who | What they do with the output |
| --- | --- |
| Loan origination system | Acts automatically on approve and decline |
| Underwriters | Review the files sent to manual review |
| Applicants | Receive the top reasons for a decline |
| Risk and compliance | Audit decisions, fairness and model documentation |

**Today:** a logistic-regression scorecard plus underwriter judgement. In the dataset, "approve everyone" is the observed status quo.

## Value

Profit per approved loan = (1 − PD) × margin − PD × LGD, with all amounts as a share of principal. Placeholder values, flagged as assumptions: margin 12%, LGD 60%, review cost 0.3% per file, reviewers catch 30% of defaults. Break-even PD is about 16.7%. See `decisions/0002-economic-assumptions.md`.

## Success criteria

- Expected profit at least 10% above approving everyone (D12). The scorecard comparison is reported with a confidence interval but is not a gate. (A preliminary run: about +9 to +11% over approving everyone, only +1.9% between a basic and a better model.)
- Default rate among auto-approved loans at most 6.5% (portfolio: 8.07%).
- Decline cap of 10%: decided after experiment E4 (D14); the profit-optimal cutoff declines about 10 to 11% in a preliminary run.
- Fair treatment across gender and age band: approval-rate ratio and approval among people who repay both at least 0.8.
- Review band within capacity (start at 5%, size chosen by experiment); scoring in under 1 second; four reason codes per decline.

## Constraints

Explainable and auditable (model-risk documentation in the style of OSFI E-23). Gender and age excluded from inputs, monitored for fairness. True default labels take months, so monitoring uses early signals. Data amounts have no stated currency.

## Non-goals

Pricing and credit limits, collections strategy, a full solution to reject inference (outcomes exist only for granted loans).

## Known limits

The label `TARGET` means payment difficulty, not write-off, so profit is an estimate. No application dates exist, so a time-based split is impossible. Money assumptions are placeholders and are stress-tested by experiments E1–E7. Profit is weighted by loan amount (ADR 0003).
