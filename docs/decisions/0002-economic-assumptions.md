# ADR 0002 — Use labelled placeholder economics, and test their effect

**Date:** 2026-11-17 · **Status:** Accepted · **Related:** D06–D10

## Context

Profit needs four money values: margin on a repaid loan, loss given default (LGD), the cost of a manual review, and how many defaults a reviewer catches. No internal figures are available, so public sources were searched on 17 November 2026.

## What was found

| Parameter | Value used | Evidence | Range tested | Confidence |
|---|---|---|---|---|
| LGD | 60% of principal | Two glossaries: 50–70% and 60–90% for unsecured consumer loans | 50–90% | Medium |
| Margin | 12% of principal | One article: net interest margin 12–18% (annual portfolio figure, not per loan) | 8–18% | Low |
| Review cost | 0.3% of principal per file | Only mortgage origination data (about $11,600 per loan, Q3 2023); different product | 0.1–1.0% | Low |
| Reviewer catch rate | 30% | Nothing public; vendor claims concern review time, not accuracy | 0–60% | Very low |

Search excerpts only; the pages were not opened in full. Treat as ballpark.

## Decision

Keep the four placeholder values above, express every amount as a share of principal (the currency is unknown), store them in `configs/economics.yaml`, and **run sensitivity experiments** (E2, E3) so the conclusion never rests on one guess.

## Reasons

- Inventing precise dollar figures would give false confidence.
- A single config file means every profit number can be regenerated when real values arrive.
- The break-even PD, Margin / (Margin + LGD), ranges from about 8% to 27% across the tested values, so the cutoff cannot be hard-coded.

## Simplifications to remember

- Exposure at default equals the full principal. The balance really falls as instalments are paid, so losses are somewhat overstated.
- A reviewer is assumed to decline only defaulters, never good applicants. Real reviewers also make that mistake, so review is worth somewhat less than shown.
- Review beats declining only below a PD of about 22%; above that, declining is better.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Wait for real figures | Blocks all work; none are available |
| Use dollar amounts | Currency unknown; would be fabricated |
| Skip review costs and treat review as free | Makes the review band look better than it is |

## Consequences

- The size of the review band, and whether review is worth having, depends mostly on the reviewer catch rate. If experiment E3 shows review only pays at high accuracy, the report must say the band is a bet.
- With the placeholders, review adds the most value near the break-even risk of about 17%, roughly 2.7% of principal per file, and beats plain approval above about 1.7% PD. Capacity, not economics, then limits the band size.

## Revisit if

Finance, collections or underwriting provide real values, or experiment results show the answer changes with the assumptions.
