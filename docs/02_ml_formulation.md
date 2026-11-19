# ML formulation (Phase 1)

Mohammad Akbari · 17 November 2026, revised 18 November 2026

*Business context: `01_problem_brief.md`. Decisions and their reasons: `decision_log.md` and `decisions/`.*

## Summary

Phase 1 turns the business question "whom should we lend to?" into a precise prediction task, and fixes how we will judge the result in money, not in accuracy points.

In plain words: for every loan application, the model estimates the chance that the applicant will have trouble repaying. That chance is not the final answer. A separate decision rule turns it into one of three actions, **approve**, **send to a human underwriter**, or **decline**, by comparing the profit and the loss each action is expected to bring.

This report settles five things:

- **What the model predicts:** the probability that an applicant will have payment difficulties (the dataset column `TARGET`).
- **When it predicts:** at the moment of application, using only what is known by then.
- **How it is judged:** by expected profit per 1,000 applications, with ranking and probability-quality metrics as supporting evidence.
- **What money numbers we assume:** margin, loss on a bad loan and review cost. They are placeholders backed by public benchmarks, and we will test how much the answer depends on them.
- **What is in scope:** one model for all products, the main table first and the other tables as an ablation, and the two stretch goals (survival model, counterfactual explanations) after the core is done.

## Scope decisions

Seven scope questions were settled before the formulation was written (D11, D06–D09, D23–D26).

| # | Question | Decision | What it changes |
| --- | --- | --- | --- |
| 1 | Review capacity (share of applications a human can check) | Not fixed. Start at 5%, then measure the cost and benefit of 0–15% with the real model and data | Size of the "send to underwriter" band |
| 2 | Real figures for margin, loss and review cost | None available. Keep the placeholders unless public sources give better ones (see next section) | Every profit number in the project |
| 3 | Share of defaults a reviewer catches | Keep as a key assumption, test its effect, replace with a real value if one is found | Whether manual review is worth its cost at all |
| 4 | Protected attributes | Gender and age band are monitored for fairness and excluded from the model's inputs | Fairness checks; feature list |
| 5 | One model or several | One model for all products, with contract type as an input | Model count; per-product evaluation |
| 6 | Use the six related tables from the start | No. Build on the main table first, then add the related tables as a measured ablation | Order of work in Phases 3–5 |
| 7 | Stretch goals | In scope: survival model and counterfactual explanations, after the core system works | Final phase of the project |

## Economic assumptions

We found public ranges that support the loss figure, but nothing solid for margin, review cost or reviewer accuracy, so those stay as labelled placeholders that the experiments will stress-test.

All amounts are shown as a share of the loan principal. The dataset does not state its currency, so dollar figures would be invented.

### How the money works

Each approved loan either pays back and earns a margin, or defaults and loses a share of what was lent:

```latex
Profit = (1 - PD) * Margin - PD * LGD
```

- **PD** (probability of default): the model's estimate that this applicant will have trouble repaying.
- **Margin:** what a repaid loan earns, as a share of principal.
- **LGD** (loss given default): the share of principal we do not recover when a loan goes bad.

Setting profit to zero gives the **break-even PD**, the highest risk at which approving still pays: Margin / (Margin + LGD). With 12% margin and 60% LGD that is about 16.7%. A normal classifier cutoff of 50% would approve far too many bad loans.

Simplification: we set the exposure at default (EAD) equal to the full principal. In reality the balance shrinks as instalments are paid, so true losses are somewhat lower and this choice is conservative.

### Values used and the evidence behind them

| Parameter | Value used | What public sources say | Range we will test | Confidence |
| --- | --- | --- | --- | --- |
| Loss given default (LGD) | 60% | Unsecured consumer loans are usually quoted at 50–70% ([LoanPro](https://www.loanpro.io/glossary/loss-given-default)) and 60–90% ([Vergent](https://www.vergentlms.com/?p=8609)) | 50–90% | Medium. Supported by two industry glossaries; our value sits at the low end. |
| Margin on a repaid loan | 12% of principal | One lender-economics article puts net interest margin at 12–18% of the portfolio, after funding costs ([product economics](https://mazino2d.github.io/2026-04-14-1-product-economics/)). It is an annual portfolio figure, not a per-loan one | 8–18% | Low. Single non-authoritative source; kept at the bottom of its range to be cautious. |
| Manual review cost | 0.3% of principal per file | No consumer-loan figure found. Mortgage data shows underwriting is expensive: average origination cost was about $11,600 per loan in Q3 2023 ([HousingWire on Freddie Mac](https://www.housingwire.com/articles/top-cost-effective-retail-lenders-produce-loans-at-half-the-industry-average-freddie-mac/)). Mortgages are a different product | 0.1–1.0% | Low. Pure placeholder. |
| Share of defaults a reviewer catches | 30% | Nothing public found. Vendor material talks about 30–50% less review *time*, which is a different thing ([Stealth Agents summary](https://stealthagents.com/research/ai-credit-scoring-automation)) | 0–60% | Very low. The most important unknown, so it gets its own experiment. |

### What a human review is worth

If a reviewer catches a share *e* of the defaulters in the band and declines them, a reviewed file earns the same profit as an approval, minus the review cost, plus the losses avoided:

```latex
Gain from review = PD * e * LGD - ReviewCost
```

Three consequences follow, and they drive the experiments later:

- If reviewers catch nothing (e = 0), review only costs money. Whether it helps depends entirely on *e*.
- With the placeholders, review beats approving as soon as PD exceeds about 1.7% (0.3% / (30% x 60%)), so many applicants would qualify and the **capacity limit, not the economics, decides the band size**.
- Review adds the most value near the break-even PD of 17%, about 2.7% of principal per file, because that is where approve and decline are closest and a wrong call is cheapest to fix. Above a PD of about 22% declining is better than reviewing. So the review band should sit between roughly 2% and 22% PD, centred on 17%, and its width is set by capacity.
- These figures assume a reviewer only ever declines defaulters and never wrongly declines a good applicant. If reviewers also reject some good applicants, review is worth less.

### Break-even PD under other assumptions

| Margin | LGD 50% | LGD 60% | LGD 90% |
| --- | --- | --- | --- |
| 8% | 13.8% | 11.8% | 8.2% |
| 12% | 19.4% | 16.7% | 11.8% |
| 18% | 26.5% | 23.1% | 16.7% |

The wide spread (8% to 27%) is why the cutoff must never be hard-coded. It lives in `configs/economics.yaml` and changes with the assumptions.

## The ML problem

We predict, for each loan application, the probability of payment difficulties, using only information available on the day of application, and we then turn that probability into a decision with a separate profit-based rule.

| Element | Our choice | Why |
| --- | --- | --- |
| Unit of prediction | One loan application (`SK_ID_CURR`) | The lender decides per application |
| Prediction time | Application date | Anything learned later (for example how the loan was repaid) would not exist when the decision is made, so using it would be cheating |
| Target | `TARGET = 1`: the client had a late payment of more than a set number of days on at least one of the first few instalments ([Home Credit definition, as restated here](https://gegznav.github.io/ds-projects/home-credit)) | This is what the dataset provides |
| Task type | Binary classification that outputs a *calibrated probability*, followed by a decision rule | The decision needs a trustworthy percentage, not just a yes or no |
| Products | Cash loans and revolving loans in one model, contract type as an input | D24. Results are still reported per product |
| Inputs | Application form fields first, then bureau and previous-loan history as an ablation | D25 |
| Output of the service | Probability, decision, top reasons, model version | Needed for audits and for telling declined applicants why |

### Two things the label does not tell us

- **`TARGET` means payment difficulty, not a final write-off.** Some people with a late payment catch up later. Our profit figures are therefore estimates of the real thing, and the report says so wherever profit appears.
- **We only see outcomes for people who were approved.** Anyone the lender once turned away has no label. The model learns from a population that earlier decisions already filtered. This is called *reject inference* and we document it as a limit, not a solved problem.

## Metrics

Expected profit decides which policy ships; the machine-learning scores only tell us whether the model is a good ingredient for that policy.

In this dataset 24,825 of 307,511 applicants (8.07%) have `TARGET = 1`; this was checked against the data on 17 November 2026. A model that says "nobody will have trouble" would therefore be right about 92% of the time and earn nothing from the risk it ignores. That is why plain accuracy is not used anywhere in this project.

| Level | Metric | What it answers | Role |
| --- | --- | --- | --- |
| Business | Expected profit per 1,000 applications, with a bootstrap confidence interval | Does the policy make more money than today's? | Decides go or no-go |
| Business | Default rate among approved loans; approval rate; review volume | Did we get profit by taking hidden risk or by shrinking the business? | Guardrails |
| ML: ranking | ROC-AUC and PR-AUC | Does the model put risky people above safe ones? | Compare models |
| ML: probabilities | Brier score and calibration curve | When the model says 10%, do about 10% of those people actually struggle? | Required, because the cutoff is a probability |
| Fairness | Approval-rate ratio and equal-opportunity gap across gender and age bands | Are groups treated comparably? | Guardrail |
| Operational | p99 response time, review band size vs capacity | Can it run in production? | Guardrail |

### Targets

**What the profit target compares.** Three policies are scored by expected profit per 1,000 applications: (1) approve everyone, which is what the data shows; (2) the old scorecard; (3) our model. The first draft said "our model must earn 10% more than the scorecard". A preliminary run (`reports/preliminary_check.md`, rough, one run, placeholder economics) shows why that cannot work:

| Policy (preliminary, main table only) | Profit per 1,000 | vs approve everyone | vs scorecard-like |
| --- | --- | --- | --- |
| Approve everyone | 61.9 | — | — |
| Logistic regression (scorecard-like), break-even cutoff | 67.5 | +9.1% | — |
| Gradient boosting, break-even cutoff | 68.8 | +11.2% | +1.9% |

Most of the money comes from using *any* decent risk score instead of approving everyone. A better model adds only a little on top (+1.9%). So "+10% over the scorecard" would almost never be met, however good the model is, while "+10% over approving everyone" is reachable. The target is therefore set against approving everyone, and the scorecard is a reported comparison.

The profit target is therefore **+10% over approving everyone** (D12). The scorecard comparison is still reported, with a confidence interval, but is not a pass/fail gate. The remaining guardrails:

- Expected profit at least **10% higher than approving everyone** (D12).
- Default rate among auto-approved loans at most **6.5%** (preliminary: 5.9 to 6.2%).
- Decline cap of **10%**: decided after experiment E4 (D14) whether it overrides the profit-optimal cutoff. Preliminary: the break-even cutoff declines 10 to 11%, so the two nearly coincide.
- Fairness, measured on gender and age band: approval-rate ratio and the ratio of approval among people who repay, both at least **0.8**. Preliminary for gender: 0.95 and 0.97.
- Review band within the chosen capacity; scoring in under one second.

If the model misses them, that is a valid finding and we report it as one.

### The thin-file slice

The business goal is about applicants with thin credit history, but the data has no thin-file flag. The project defines it as **no record in the bureau table** (D30) (14.3% of applications). We report approval rate, default rate and profit for this slice separately.

### Why AUC does not pick the winner

Two models with the same AUC can lead to different profit, because profit depends on how well the probabilities are calibrated near the break-even point (around 17%), not on the overall ranking. Model choice therefore uses profit, with AUC as a sanity check. The reasoning is recorded in `docs/decisions/0001-primary-metric.md`.

## Data, split and leakage rules

The data has no true application dates, so we split at random by applicant, lock a test set away, and enforce strict rules so that no information from after the application reaches the model.

### The data

The dataset is Home Credit Default Risk on Kaggle: one main table of applications (about 307,000 rows, with the target) and six related tables of credit-bureau and past-loan history. It is stored in `data/home-credit-default-risk/`, next to the original 721 MB zip. The raw files stay untouched and out of git (see `.gitignore`).

| Table | Content | Used in |
| --- | --- | --- |
| `application_train` | One row per application, with the target | Baseline model |
| `bureau`, `bureau_balance` | Loans at other lenders and their monthly status | Ablation B |
| `previous_application`, `POS_CASH_balance`, `installments_payments`, `credit_card_balance` | Earlier loans with this lender | Ablation C |

### Split

- **Train / validation / test** split by applicant, stratified on the target so each part keeps the same default rate. Suggested shares: 70 / 15 / 15.
- The **test set is locked** and scored once, at the end.
- Tuning and threshold choice use the validation set only.
- **Known limit:** because there are no calendar dates, we cannot test how the model ages over time. Drift will be examined with simulated shifts in Phase 9, and we say so plainly in the model card.

### Leakage rules

Leakage means the model sees something it would not know at decision time, which makes test results look better than real life.

1. Every feature is checked against one question: **was it known on the application date?** The answers are written in a feature table.
2. Dates in the related tables are stored as days relative to the application. Checked on the data: all past-event dates are on or before the application (previous-loan decisions at most -1, instalments at most -1, bureau credit start at most 0, monthly balances at most 0). Three exceptions need care: (a) planned end dates can be positive and are legitimately known at application time; (b) the value 365243 is a "no date" marker, not a real date, and must be recoded; (c) 17 bureau rows have an update date after the application and are dropped or tested.
3. Imputation, scaling and encoding are fitted on the training part only, inside a pipeline.
4. Aggregations of related tables are tested functions with unit tests.
5. No feature is built from `TARGET`.

### Protected attributes

Gender (`CODE_GENDER`) and age (`DAYS_BIRTH`) are kept out of the model's inputs and used only to measure fairness. We also test for *proxies*, other columns that predict gender or age well enough to bring them back in by the side door.

### Known data quirks to handle in Phase 2

- `DAYS_EMPLOYED` contains the placeholder 365243 in 55,374 rows (18.0%). Those people default less often (5.4%) than average, so the placeholder carries information and is recoded to a missing flag, not dropped.
- Many columns have large shares of missing values; missingness itself can carry meaning and is checked, not blindly filled.

### Facts checked against the data (17 November 2026)

| Fact | Value |
| --- | --- |
| Applications / columns in `application_train` | 307,511 / 122, no duplicate applicant IDs |
| Applicants with `TARGET = 1` | 24,825 (8.07%) |
| Cash loans vs revolving loans | 90.5% vs 9.5% of rows; default rate 8.3% vs 5.5% |
| Default rate by gender | Men 10.1%, women 7.0%; 4 rows coded `XNA` |
| Applicants with a bureau record / with earlier Home Credit applications | 85.7% / 94.6% |
| Earlier applications by outcome (1,670,214 rows) | Approved 62.1%, cancelled 18.9%, refused 17.4%, unused offer 1.6% |
| Age at application | 20.5 to 69.1 years |
| Loan amount (`AMT_CREDIT`) | Median 513,531; currency not stated in the data |

## Experiment plan: review capacity and cost sensitivity

Once a model exists, seven experiments will replace our placeholders with measured trade-offs and show how much each assumption matters. None can run yet: they need the data and a trained, calibrated model.

| # | Question | Method | Output |
| --- | --- | --- | --- |
| E1 | How big should the manual review band be? | Sweep review capacity from 0% to 15% of applications on the validation set. At each size, send the applicants nearest the break-even PD to review and compute profit | Profit-vs-capacity curve; capacity where an extra file stops paying for itself |
| E2 | How much does the answer depend on margin, LGD and review cost? | Grid over the ranges in the economics table; recompute the best policy and its profit each time | Heat map of profit and of the optimal cutoff |
| E3 | How good must reviewers be for review to be worth it? | Vary the share of defaults they catch from 0% to 60% | The break-even reviewer accuracy |
| E4 | Where exactly should the cutoffs be? | Profit curve over thresholds, then the three-way policy with a conformal "unsure" zone | Approve, review and decline cutoffs, and the shares of applicants in each |
| E5 | Does the model beat the alternatives in money terms? | Compare approve-everyone, scorecard (logistic regression), and gradient-boosting policies on the locked test set, with bootstrap intervals | Profit table against the 10% target (amount-weighted, D54) |
| E6 | Does a margin that grows with the loan term change the policy? *(added 19 Nov, ADR 0003)* | Repeat E4 with the term-scaled margin, so each loan has its own break-even PD | Cutoffs, decline rate and profit, flat vs term-scaled margin |
| E7 | Should thin-file applicants near the cutoff go to review instead of decline? *(added 19 Nov, D53)* | Within E1's capacity, give thin-file applicants a wider review band; compare profit, thin-file approval rate and age-band fairness | Profit cost of each extra thin-file approval |

### How to read the results

- **Cost of review:** files reviewed x review cost.
- **Benefit of review:** defaults caught x LGD avoided, minus the margin lost on any good applicants wrongly declined.
- **Choosing capacity:** the best size is where the profit of one more reviewed file equals the cost of the underwriter time needed to handle it.
- **Two ways to size the band are compared:** E1 sends the applicants nearest the break-even PD to review; E4 sends those the conformal method marks as uncertain. The one with higher profit at the same capacity wins.
- **Honesty rule:** if E3 shows the policy only works when reviewers are very accurate, we say that the review band is a bet, not a result.

Results are written back to `configs/economics.yaml` and `reports/decision_policy.md` in Phase 7.

## Scope, risks and limits

The project delivers the full decision system first and the two stretch goals afterwards, and it is honest about eight known risks.

### Scope

- **Core:** calibrated default model, three-way decision policy with a manual review band, reason codes for declines, fairness audit, API, monitoring, governance pack.
- **Stretch, in scope:** a **survival model** (when a borrower is likely to default, not only whether) and **counterfactual explanations** (what would have to change for a declined applicant to be approved). They start after the core system passes its checks.
- **Not in scope:** pricing or credit-limit setting, collections strategy, and a full solution to reject inference.

### Risks

| Risk | Why it matters | How we handle it |
| --- | --- | --- |
| Label is payment difficulty, not write-off | Profit figures are estimates | State it wherever profit appears |
| Selection bias (only approved loans have outcomes) | Model may be over-optimistic on people the lender used to reject | Document; discuss reject inference; propose a small exploration budget for later |
| Placeholder economics | Wrong margin or LGD moves the cutoff | Sensitivity experiments E2 and E3; one config file |
| Random split, no dates | Cannot measure ageing over time | Simulated drift in Phase 9; say so in the model card |
| Leakage from related tables | Inflated test scores | Leakage rules; unit tests; ablation to see the effect |
| Proxies for gender or age | Hidden unfairness | Proxy tests; fairness metrics by group |
| Poor calibration | Wrong cutoff even with high AUC | Calibration step; Brier score and curves |
| Decline cap vs profit-optimal cutoff | The break-even cutoff declines 10 to 11% in a preliminary run, close to the 10% cap | Report capped and uncapped policies (E4); decide afterwards (D14) |

## Next steps and glossary

1. **Phase 2 (done):** data card (`data/README.md`), exploratory analysis (`notebooks/01_eda.ipynb`, `reports/eda_summary.md`) and the feature-by-feature leakage table (`reports/leakage_table.md`).
2. **Phase 3:** the tested data pipeline and the related-table aggregations.
3. **Phase 4:** the official baselines, approve everyone and the logistic scorecard, so that every later model has numbers to beat.
4. **Open sign-offs:** guardrails D13 and D16; the decline cap after E4 (D14).

### Glossary

| Term | Meaning |
| --- | --- |
| PD | Probability of default: the model's estimated chance an applicant will have trouble repaying |
| LGD | Loss given default: share of the loan we lose when it goes bad |
| EAD | Exposure at default: how much is owed when it goes bad, roughly the loan amount |
| Break-even PD | The risk level at which approving a loan earns exactly zero |
| Calibration | Whether predicted probabilities match real frequencies (10% predicted means about 10% happen) |
| ROC-AUC / PR-AUC | Scores for how well the model ranks risky people above safe ones |
| Brier score | Average squared error of the predicted probabilities; lower is better |
| Leakage | The model using information that would not exist at decision time |
| Reject inference | Guessing what would have happened to applicants who were turned down |
| SHAP | A method that shows how much each input pushed one prediction up or down; used for reason codes |
| Conformal prediction | A method that flags predictions the model is unsure about, which we send to review |
| PSI | Population stability index: a measure of how much the data has shifted since training |
| Scorecard | The traditional logistic-regression credit score, our baseline |
| Ablation | Removing one part (for example the bureau tables) to measure what it contributed |

## Sources

The public figures below come from search results read on 17 November 2026; the pages were not opened in full, so treat the numbers as ballpark ranges, not audited facts.

- [LoanPro: Loss Given Default](https://www.loanpro.io/glossary/loss-given-default): unsecured personal loan LGD of 50–70%.
- [Vergent: Loss Given Default](https://www.vergentlms.com/?p=8609): unsecured consumer loan LGD of 60–90%.
- [Installment loan product economics](https://mazino2d.github.io/2026-04-14-1-product-economics/): net interest margin of 12–18%, gross yield of 22–30%.
- [HousingWire on the Freddie Mac cost-to-originate study](https://www.housingwire.com/articles/top-cost-effective-retail-lenders-produce-loans-at-half-the-industry-average-freddie-mac/): mortgage origination cost, used only as a sign that underwriting is costly.
- [Stealth Agents: AI credit scoring statistics](https://stealthagents.com/research/ai-credit-scoring-automation): vendor claims on review time, not on reviewer accuracy.
- [Home Credit project write-up](https://gegznav.github.io/ds-projects/home-credit): wording of the `TARGET` definition.
