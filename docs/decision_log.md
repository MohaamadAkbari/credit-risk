# Decision log

Every decision that shapes the system: what was decided, why, and what else was considered. Larger decisions also
have an architecture decision record in `docs/decisions/`. Other documents cite decisions by ID (D01…).

**Status values**

| Status | Meaning |
| --- | --- |
| Accepted | Agreed by the business owner and in use |
| Provisional | In use; to be re-confirmed before the locked test set is scored |
| Proposed | Waiting for sign-off |
| Deferred | Decided later, at the point stated |
| Assumption | A placeholder value with no real figure behind it; tested by sensitivity experiments, not trusted |

## A. Business problem (Phase 0)

| ID | Decision | Rationale | Alternatives considered | Status |
| --- | --- | --- | --- | --- |
| D01 | **Goal:** approve more applicants with thin credit history without raising losses; maximise expected profit per 1,000 applications | A lender loses either by declining good applicants or approving bad ones; profit captures both | Minimise default rate (shrinks the business); maximise approval rate (ignores losses) | Provisional |
| D02 | **Three outcomes per application:** auto-approve, auto-decline, manual review | Underwriters can check only some files; the uncertain middle is where they add most value | Approve/decline only; review everything (too costly) | Provisional |
| D03 | **Baselines:** (a) logistic-regression scorecard; (b) approve everyone, the observed status quo, since every row is a granted loan | The system must beat today's practice in money, not only in ML scores | Compare to a trivial model only | Provisional |
| D04 | **Out of scope for v1:** pricing, credit limits, collections, a full solution to reject inference | One decision per system; reject inference is a research problem of its own | Pricing as a second model | Provisional |
| D05 | **All amounts are a share of loan principal** | The data does not state its currency | Choose a currency | Provisional |

## B. Economic assumptions (ADR 0002)

| ID | Decision | Rationale | Alternatives considered | Status |
| --- | --- | --- | --- | --- |
| D06 | **Margin on a repaid loan: 12% of principal** | Bottom of a 12–18% net-interest-margin range from one public source | 8%, 18% | Assumption (low confidence); tested 8–18% in E2 |
| D07 | **Loss given default: 60%** | Public glossaries give 50–70% and 60–90% for unsecured consumer loans | 50%, 75%, 90% | Assumption (medium confidence); tested 50–90% |
| D08 | **Manual review cost: 0.3% of principal per file** | No consumer-loan figure found | 0.1%, 1.0% | Assumption (low confidence); tested 0.1–1.0% |
| D09 | **Reviewers catch 30% of the defaults in the review band** | Without a value the review band cannot be sized; nothing public found | 0%, 60% | Assumption (very low confidence); tested 0–60% in E3 |
| D10 | **Break-even PD is derived:** margin / (margin + LGD), about 16.7% | The cutoff must come from costs, not from 0.5 | Fixed 0.5; a target approval rate | Provisional |

## C. Review capacity

| ID | Decision | Rationale | Alternatives considered | Status |
| --- | --- | --- | --- | --- |
| D11 | **Review capacity is chosen by experiment:** start at 5% of applications, measure profit for 0–15% (E1) | The right size depends on what a reviewed file is worth, which needs a model to measure | Fix 5% | Accepted |

## D. Targets and guardrails

| ID | Decision | Rationale | Status |
| --- | --- | --- | --- |
| D12 | **Primary target: expected profit at least +10% over approving everyone.** The comparison with the scorecard is reported with a confidence interval, not used as a gate | A preliminary run gains +9 to +11% over approving everyone but only +1.9% over a scorecard-like model (`reports/preliminary_check.md`) | Accepted |
| D13 | Default rate among auto-approved loans at most **6.5%** (portfolio 8.07%) | Profit must not be bought with hidden risk | Proposed |
| D14 | **Decline cap of 10%:** whether it overrides the profit-optimal cutoff is decided after experiment E4 | Profit must not be bought by shrinking the business; preliminary cutoff declines 10–11% | Deferred to E4 |
| D15 | **Fairness audit on gender and age band:** approval-rate ratio and approval ratio among people who repay, each at least 0.8 | Base default rates differ (men 10.1%, women 7.0%), so two metrics; preliminary gender ratios 0.95 and 0.97 | Proposed (see D40) |
| D16 | Scoring under **1 second** (p99); four reason codes per decline | The applicant is waiting; adverse decisions must be explained | Proposed |

## E. ML formulation (Phase 1, ADR 0001)

| ID | Decision | Rationale | Alternatives considered | Status |
| --- | --- | --- | --- | --- |
| D17 | **Primary metric: expected profit**; ROC-AUC, PR-AUC, Brier score and calibration support it | Equal AUC can mean unequal profit; the cutoff is a probability | AUC; accuracy (92% by approving everyone) | Provisional |
| D18 | **Target: `TARGET` (payment difficulty), predicted at the application date** | The label the data provides; the moment of decision | Write-off label (not available) | Provisional |
| D19 | **Calibrated binary classifier, then a separate decision rule** | Policy can change without retraining | One model that outputs the decision | Provisional |
| D20 | **Stratified random 70/15/15 split by applicant; test set locked and scored once** | No application dates, so no time split | Time-based split (impossible) | Provisional |
| D21 | **Leakage rules:** known-at-application check per column; drop related records dated after the application; fit preprocessing on training data only | The most common reason credit models look better on paper than in use | — | Provisional |
| D22 | **Fallback when the model is down:** scorecard, then manual queue; never approve without a score | Production safety | Fail open | Provisional |

## F. Scope and fairness

| ID | Decision | Rationale | Alternatives considered | Status |
| --- | --- | --- | --- | --- |
| D23 | **Gender and age are excluded from model inputs** and kept for fairness monitoring; proxies are tested | Standard practice; exclusion alone is not enough | Use them as inputs | Accepted |
| D24 | **One model for all products**, contract type as an input, results reported per product | Simpler to build and govern | Separate cash and revolving models | Accepted |
| D25 | **Main table first; related tables as a measured ablation** (A main; B + bureau; C all) | Shows what each source adds | All tables from day one | Accepted |
| D26 | **Stretch goals in scope after the core:** survival model, counterfactual explanations | Kept in scope | Defer | Accepted |

## G. Data handling and process

| ID | Decision | Rationale | Status |
| --- | --- | --- | --- |
| D27 | **The data is downloaded by the account holder** under the Kaggle competition rules and never committed | Licence terms | Accepted |
| D28 | **Reports are written for readers with little ML background**, with a glossary | Audience includes business and risk staff | Accepted |
| D29 | **Decisions are recorded as they are made** (this log and `docs/decisions/`) | Auditability | Accepted |
| D30 | **Thin file = no record in the bureau table** (14.3% of applications); approval, default and profit reported for this slice | The goal is about thin-file applicants but the data has no flag | Accepted |
| D31 | **Raw data lives in `data/home-credit-default-risk/`** and is excluded from git | 721 MB zip, 58 million rows | Accepted |
| D32 | **Dates in related tables:** past events are on or before the application; planned end dates may be positive; 365243 means "no date"; bureau rows updated after the application are excluded | Checked against the data | Accepted |
| D33 | **Repository files are the master copy** of every report | One source of truth | Accepted |
| D34 | **One cloud deployment, on AWS** | Matches the deployment plan; account available | Accepted |
| D35 | **A preliminary profit check** (`scripts/preliminary_check.py`) gives first numbers; it is not the official baseline | Replace guesses with data before fixing targets | Accepted |

## H. Data understanding (Phase 2)

| ID | Decision | Rationale | Alternatives considered | Status |
| --- | --- | --- | --- | --- |
| D36 | **Interim layer:** raw CSVs converted to Parquet in `data/interim/` (IDs int32, other numbers float32) by `credit_risk.data.interim`; raw files untouched; features read raw values | 58 million rows do not fit in 4 GB as pandas frames; Parquet loads by column | Chunked CSV reads every time | Accepted |
| D37 | **A leakage verdict for every column** (`configs/feature_availability.csv`, 218 columns). Drop 17 bureau rows updated after the application; allow the two planned end dates; allow `bureau_balance` month 0 with a month ≤ −1 ablation | These are the only positive dates in the data | Drop every positive date (loses 826,995 legitimate planned dates) | Provisional |
| D38 | **Seven columns with undocumented timing are kept** (three external scores, four social-circle counts), marked `review` | Strongest inputs; presented as application-time data. A real deployment must confirm with the provider | Drop them | Provisional |
| D39 | **Missingness is kept as information:** indicator flags and a "missing" category level | Missingness predicts default in both directions | Median or mode filling | Provisional |
| D40 | **Excluding gender and age does not make the model blind to them:** other columns recover gender (ROC-AUC 0.89) and age (R² 0.72). Fairness is judged on outcomes (D15); Phase 6 tests whether removing or constraining the strongest proxies narrows any gap, and at what profit cost | Proxy test in `notebooks/01_eda.ipynb`, section 7 | Drop all proxy columns now | Proposed |
| D41 | **Kaggle's `application_test` is not used for evaluation**; it serves as a shifted population (0.9% revolving loans vs 9.5%) for drift tests | No labels; the locked test set comes from `application_train` (D20) | Ignore it | Provisional |

## I. Data pipeline and features (Phase 3)

| ID | Decision | Rationale | Alternatives considered | Status |
| --- | --- | --- | --- | --- |
| D42 | **Split fixed and fingerprinted:** seed 42, rows sorted by applicant ID before splitting, SHA-256 of each fold's IDs in `configs/split_manifest.json`; a rebuild that differs is refused unless `--relock` | The test set must not change silently between experiments | Re-split on every run | Accepted |
| D43 | **Feature modules declare the exact columns they read**, and the loader reads nothing else; a test checks every declared column against the leakage table | Makes the leakage rules structural rather than a matter of care | Review by hand | Accepted |
| D44 | **No rows in a related table means zero** for counts and sums; ratios, means and maxima stay missing | "No credits" is information, not unknown | Leave everything missing | Provisional |
| D45 | **35 main-table columns left out:** 7 near-constant flags and 28 building-statistics duplicates (`_MEDI` r ≥ 0.99, numeric `_MODE` r ≥ 0.97 with `_AVG`) | Duplicates add width, not information | Keep all three versions | Provisional |
| D46 | **Protected and slicing attributes in a separate audit table** (gender, age, age band, thin file, product), never in a feature table | Keeps them out of the model while available for fairness reports | Keep them in the feature table and drop at training | Accepted |
| D47 | **Preprocessing fitted on the training fold only:** caps at the 0.1% / 99.9% quantiles, median imputation with missing flags, one-hot with levels under 50 rows grouped, optional scaling for linear models | Implements D21 and D39 in one reusable transformer | Fit on all data (leaks) | Provisional |
| D48 | **Bureau amounts summed in the main currency only** (99.9% of rows) | Amounts in different currencies are not comparable | Convert (no rates available) | Provisional |

## Open items

1. Decline cap (D14), after experiment E4.
2. Sign-off on D13 (bad rate at most 6.5%), D16 (latency and reason codes) and D15/D40 (fairness metrics in light of the proxy finding).
3. Real values for D06–D09 if any become available.
4. Experiments E1–E5 once a calibrated model exists; review capacity from E1.
5. Phase 4: official baselines on the locked split (approve everyone, logistic scorecard).
