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
| D12 | **Primary target: expected profit at least +10% over approving everyone.** The comparison with the scorecard is reported with a confidence interval, not used as a gate | A preliminary run gains +9 to +11% over approving everyone but only +1.9% over a scorecard-like model (`reports/preliminary_check.md`). **19 Nov:** now measured amount-weighted (D54), where the same run gains +9.2%; the owner re-confirmed the target under this measure | Accepted (re-confirmed amount-weighted, 19 Nov) |
| D13 | Default rate among auto-approved loans at most **6.5%** (portfolio 8.07%) | Profit must not be bought with hidden risk | Proposed |
| D14 | **Decline cap of 10%:** whether it overrides the profit-optimal cutoff is decided after experiment E4 | Profit must not be bought by shrinking the business; preliminary cutoff declines 10–11% | Deferred to E4 |
| D15 | **Fairness audit on gender and age band:** approval-rate ratio and approval ratio among people who repay, each at least 0.8. Age bands fixed in D56 | Base default rates differ (men 10.1%, women 7.0%), so two metrics; preliminary gender ratios 0.95 and 0.97 | Proposed (see D40, D56) |
| D16 | Scoring under **1 second** (p99); four reason codes per decline | The applicant is waiting; adverse decisions must be explained | Proposed |

## E. ML formulation (Phase 1, ADR 0001)

| ID | Decision | Rationale | Alternatives considered | Status |
| --- | --- | --- | --- | --- |
| D17 | **Primary metric: expected profit**; ROC-AUC, PR-AUC, Brier score and calibration support it | Equal AUC can mean unequal profit; the cutoff is a probability | AUC; accuracy (92% by approving everyone) | Provisional |
| D18 | **Target: `TARGET` (payment difficulty), predicted at the application date** | The label the data provides; the moment of decision | Write-off label (not available) | Provisional |
| D19 | **Calibrated binary classifier, then a separate decision rule** | Policy can change without retraining | One model that outputs the decision | Provisional |
| D20 | **Stratified random 70/15/15 split; test set locked and scored once.** Since 19 Nov the unit is the person, not the application (D49) | No application dates, so no time split; the application ID is not a hidden time order either (default 7.9–8.3% across ID deciles, checked 19 Nov) | Time-based split (impossible) | Provisional |
| D21 | **Leakage rules:** known-at-application check per column; drop related records dated after the application; fit preprocessing on training data only | The most common reason credit models look better on paper than in use | — | Provisional |
| D22 | **Fallback when the model is down:** scorecard, then manual queue; never approve without a score | Production safety | Fail open | Provisional |

## F. Scope and fairness

| ID | Decision | Rationale | Alternatives considered | Status |
| --- | --- | --- | --- | --- |
| D23 | **Gender and age are excluded from model inputs** and kept for fairness monitoring; proxies are tested | Standard practice; exclusion alone is not enough | Use them as inputs | Accepted |
| D24 | **One model for all products**, contract type as an input, results reported per product | Simpler to build and govern | Separate cash and revolving models | Accepted |
| D25 | **Main table first; related tables as a measured ablation** (A application form; B + credit-bureau information; C all). Bureau-derived main-table columns count as B (D50) | Shows what each source adds | All tables from day one | Accepted |
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
| D40 | **Excluding gender and age does not make the model blind to them:** other columns recover gender (ROC-AUC 0.89) and age (R² 0.72). Fairness is judged on outcomes (D15); Phase 6 tests whether removing or constraining the strongest proxies narrows any gap, and at what profit cost. The strongest age proxy, `FLAG_EMP_PHONE`, is in fact **pension status** (it equals the pensioner flag in all but 12 rows), so the Phase 6 question is whether income type may be used | Proxy test in `notebooks/01_eda.ipynb`, sections 7 and 10 | Drop all proxy columns now | Proposed |
| D41 | **Kaggle's `application_test` is not used for evaluation**; it serves as a shifted population for drift tests. The shift is strong: a model tells it from the training file with ROC-AUC 0.887, mainly through shorter loans (median 16.3 vs 20.0 months), fewer revolving loans (0.9% vs 9.5%) and bureau enquiries recorded in other time buckets | No labels; the locked test set comes from `application_train` (D20) | Ignore it | Provisional |

## I. Data pipeline and features (Phase 3)

| ID | Decision | Rationale | Alternatives considered | Status |
| --- | --- | --- | --- | --- |
| D42 | **Split fixed and fingerprinted:** seed 42, rows sorted by applicant ID before splitting, whole persons per fold (D49), SHA-256 of each fold's IDs in `configs/split_manifest.json`; a rebuild that differs is refused unless `--relock` | The test set must not change silently between experiments | Re-split on every run | Accepted |
| D43 | **Feature modules declare the exact columns they read**, and the loader reads nothing else; a test checks every declared column against the leakage table | Makes the leakage rules structural rather than a matter of care | Review by hand | Accepted |
| D44 | **No rows in a related table means zero** for counts and sums; ratios, means and maxima stay missing | "No credits" is information, not unknown | Leave everything missing | Provisional |
| D45 | **35 main-table columns left out:** 7 near-constant flags and 28 building-statistics duplicates (`_MEDI` r ≥ 0.99, numeric `_MODE` r ≥ 0.97 with `_AVG`) | Duplicates add width, not information | Keep all three versions | Provisional |
| D46 | **Protected and slicing attributes in a separate audit table** (gender, age, age band, thin file, product), never in a feature table | Keeps them out of the model while available for fairness reports | Keep them in the feature table and drop at training | Accepted |
| D47 | **Preprocessing fitted on the training fold only:** caps at the 0.1% / 99.9% quantiles, median imputation with missing flags, one-hot with levels under 50 rows grouped, optional scaling for linear models | Implements D21 and D39 in one reusable transformer | Fit on all data (leaks) | Provisional |
| D48 | **Bureau amounts summed in the main currency only** (99.9% of rows) | Amounts in different currencies are not comparable | Convert (no rates available) | Provisional |
| D60 | **The data is checked before anything is built** (`make validate`, `credit_risk.data.validate`): rules true of any release (keys, label, flags, score and rating ranges, dates not after the application, columns as in the leakage table, joins) and the profile of this release in `configs/data_contract.json` (row counts, types, missing counts, ranges, levels, raw-file SHA-256). Split and features depend on it; `make data` checks the archive hash. Region ratings outside 1–3 become missing (one −1 in Kaggle's test) | The plan requires schema and quality checks; until now the tests ran on made-up tables only, so a different download would have produced different numbers silently. Our own module reads one column at a time and fits in 4 GB | Pandera or Great Expectations (load whole tables, extra dependencies); checks inside each feature module | Accepted |
| D61 | **Feature tables are fingerprinted by content** (SHA-256 of names, types, index and values) in `configs/feature_manifest.json`; `make verify` and `load_stage` refuse a table that differs | Ties every Phase 4+ result to the exact features; hashing values rather than file bytes survives a change of Parquet writer | DVC (another tool and remote for 4 files); file-byte hashes | Accepted |

## J. Phase 2 manager review (19 November 2026)

Findings and evidence: `docs/04_manager_review_phase2.md`; numbers from `scripts/phase2_review_checks.py` (`make checks`,
also notebook section 10). Decided by Claude in the engineer role, on the owner's instruction to resolve the review with
its recommendations; the owner may overturn any of them.

| ID | Decision | Rationale | Alternatives considered | Status |
| --- | --- | --- | --- | --- |
| D49 | **The split keeps each person in one fold.** A person is an application group sharing gender, birth date, ID-document date and registration date (588 groups, 1,176 applications); folds are drawn over persons, stratified on any default. Relocked 19 Nov | 289 of these people sat in two folds; the split was by application, not by applicant as D20 intended. Fixing it costs nothing before any model is trained | Keep the old split and document the 0.4% overlap | Provisional |
| D50 | **Bureau-derived main-table columns enter at stage B:** `EXT_SOURCE_3` and the six `AMT_REQ_CREDIT_BUREAU_*` counts. Stage A combines only external scores 1 and 2 (`EXT_SOURCE_12_*`); stage B adds the three-score mean, minimum and count | They are missing for 96.9% and 94.3% of thin-file applicants (6.9% and 0% otherwise): bureau information. Left in A they would make the A → B ablation understate what the bureau adds | Keep them in A and caveat the ablation | Provisional |
| D51 | **Application hour and weekday are excluded from inputs** (verdict `exclude`) | They describe the process, not the applicant. The hour's signal is mostly region / time zone (22% of region-3 applications start by 7 am vs 0.6% in region 1); weekday has none. As a decline reason, "applied at 6 am" would be indefensible | Keep both, hide them from reason codes | Provisional |
| D52 | **Two duplicates dropped** (`FLAG_EMP_PHONE` = 1 − `EMPLOYED_NA` in all but 12 rows; `OBS_60_CNT_SOCIAL_CIRCLE`, r = 0.998 with `OBS_30`). Other related columns are **grouped for reason codes** in `configs/reason_codes.yaml`, one reason per group | Duplicates split SHAP credit and fill two of four reason slots with one cause; they also make scorecard coefficients unstable | Drop every correlated pair (loses the credit-to-goods ratio, a strong signal) | Provisional |
| D53 | **"No or limited credit-bureau history" may be a decline reason**, given at most once (all bureau features and their missing flags form one group). Its share among thin-file declines is reported in Phase 6 and monitored in Phase 9. Experiment **E7** tests a wider review band for thin-file applicants near the cutoff | An insufficient credit file is a standard adverse-action reason, and hiding it would make declines harder to explain. Because the business goal is to approve more thin-file applicants (D01), its use is measured rather than assumed harmless | Never give it (declines would cite proxies instead); allow it without limit | Proposed |
| D54 | **Profit is weighted by loan amount** (per 1,000 of principal applied for); unit-weighted reported too. **The margin stays flat at 12%**; a term-scaled margin is experiment **E6** (ADR 0003) | Default is hump-shaped in the amount and lower for large loans (7.52% amount-weighted vs 8.07%); a flat per-loan margin misprices 10- and 34-month loans | Unit weights; term-scaled margin as primary | Accepted (engineer); D12 re-confirmed under it (19 Nov) |
| D55 | **Two more codes recoded to missing plus a flag:** `OWN_CAR_AGE` 64/65 (3,334 rows, `CAR_AGE_CODED`) and `DAYS_LAST_PHONE_CHANGE` 0 (37,672 rows, `PHONE_CHANGE_DAY0`). `EXT_SOURCE_2` below 0.001 is kept: a continuous tail (202 rows, 43.6% default) | Spikes of thousands of rows next to neighbours with 1–3 rows are codes, not values | Leave as values (misleads linear models) | Provisional |
| D56 | **Fairness age bands fixed:** <25, 25–34, 35–44, 45–54, 55–64, 65+ (as in the audit table and `configs/economics.yaml`). Thin-file results are reported together with age, because thin-file applicants skew young (7.7% under 25 vs 3.4%) | Fixing the bands before any model exists prevents choosing them after seeing results. Every gender × age cell has at least 1,504 applicants (men 65+, default 5.6% ± 1.2 points) | Decide in Phase 6 | Provisional |
| D57 | **Feature shapes, from the training fold only, guide scorecard bins and monotone constraints** (`reports/feature_shapes.md`, `configs/feature_shapes.csv`): +1 / −1 only for features whose risk rises or falls steadily; none for hump-shaped or irregular ones such as loan amount and term | A monotone constraint on a non-monotone feature would force a wrong shape; the training fold keeps validation and test unseen | Constrain every feature by intuition | Provisional |

## K. Stakeholder reporting (19 November 2026)

| ID | Decision | Rationale | Alternatives considered | Status |
| --- | --- | --- | --- | --- |
| D58 | **A data dictionary is generated for every column** (`make dictionary`): group, kind, unit, description, range, levels, missing share, Kaggle's note, IV on the training fold, and the chart that suits its kind | The EDA covered leakage per column but not what each column means or how to read it | A hand-written dictionary (drifts from the data) | Accepted |
| D59 | **The stakeholder dashboard reads only aggregated, fixed files** made by `make dashboard` (`reports/dashboard/`), each carrying the script that made it; no applicant-level rows leave the machine | The data cannot be redistributed under the Kaggle rules, and aggregates are all a stakeholder needs | Live queries (no connector holds the data); applicant-level files | Accepted |

## Open items

1. Decline cap (D14), after experiments E4 and E6 (the term-scaled margin raises the preliminary cutoff's decline rate to about 16%).
2. Sign-off on D13 (bad rate at most 6.5%), D16 (latency and reason codes) and D15/D40 (fairness metrics in light of the proxy finding).
3. **Owner may overturn** D49–D57 (decided on the owner's instruction in the Phase 2 review); D53 (thin-file decline reason) most needs a business view.
4. Real values for D06–D09 if any become available.
5. Experiments E1–E7 once a calibrated model exists; review capacity from E1.
6. Phase 4: official baselines on the locked split (approve everyone, logistic scorecard).
