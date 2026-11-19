# P01 Credit Default Risk — Manager Review of Phase 2 (data understanding)

*19 November 2026. Reviewed: `reports/eda_summary.md`, `data/README.md`, `reports/leakage_table.md`,
`notebooks/01_eda.ipynb`, the decision log (D36–D41), `configs/economics.yaml` and `scripts/preliminary_check.py`.
Every new number below comes from `scripts/phase2_review_checks.py`, run on `data/interim/`.*

## Verdict

The Phase 2 work is solid on what it covers. The joins, the placeholders, the leakage audit and the proxy test are
careful, and the notebook runs end to end. The gaps are in what it **did not look at**, and two of them matter for
the business result:

1. **The profit metric counts every loan as the same size, and the EDA never looked at loan size or loan length.**
   Risk is not flat across either, so the profit target and the cutoff may look different once real amounts count.
2. **Thin-file applicants, the group the business wants to grow, have almost none of the strongest signal.**
   Three "missing data" findings in the EDA are really one finding: no credit-bureau history. This shapes the model,
   the reason codes and the ablation study.

Neither is a mistake in the work that was done. Both should be settled before Phase 4 baselines, because they change
what "better" means and how the results are read.

## Findings

| # | Severity | Finding | Affects | Status (19 Nov) |
| --- | --- | --- | --- | --- |
| 1 | High | Profit treats every loan as size 1; loan size and term were never analysed | D05, D06, D12, E1–E5 | Fixed: D54, ADR 0003, E6; D12 re-confirmed by the owner (19 Nov) |
| 2 | High | Thin-file applicants lack `EXT_SOURCE_3` and bureau-enquiry data; three missingness findings are one | D25, D30, D39, reason codes | Fixed: D50, D53, E7 |
| 3 | Medium | Shape of risk against key inputs not examined; some are not monotonic | Phase 4 scorecard, Phase 5 monotone model | Fixed: D57, `reports/feature_shapes.md` |
| 4 | Medium | About 588 people appear under two application IDs; half of them are split across folds | D20, locked test set | Fixed: D49, split relocked |
| 5 | Medium | Three more placeholder-like codes not found | Phase 3 cleaning | Fixed: D55 |
| 6 | Low | Application hour carries risk; the channel check the leakage table asked for was not done | Leakage table | Fixed: D51 |
| 7 | Low | The "strongest age proxy" `FLAG_EMP_PHONE` is the pensioner flag itself | D40 wording | Fixed: D40, D52 |
| 8 | Low | Redundant pairs outside the building statistics | Scorecard, reason codes | Fixed: D52, `configs/reason_codes.yaml` |
| 9 | Low | Earlier applications that mirror the current one were not checked | Leakage table | Recorded in the leakage table |
| 10 | Low | Whether the ID hides a time order was not tested | D20 | Recorded in D20 and the data card |
| 11 | Low | Kaggle test compared on 3 of 121 columns | D41, Phase 9 | Fixed: adversarial check, D41 |
| 12 | Low | Age bands not written into D15; smallest fairness cell not sized | D15 | Fixed: D56, `configs/economics.yaml` |
| 13 | Low | Phase 2 work is not committed; Phase 3 started before D37–D41 were answered | Repository, process | Fixed (finding corrected below) |

## Details

### 1. The profit unit and loan size (High)

`scripts/preliminary_check.py` computes profit "per 1,000 applicants, loan size = 1", and the config says amounts are
a share of principal. So a loan of 45,000 and one of 4,050,000 count the same. The EDA never checked whether risk
depends on size or length. It does, and not in a straight line:

| Loan amount (fifths) | Default | Loan term in months (fifths) | Default |
| --- | --- | --- | --- |
| up to 255k | 7.2% | 8–15 | 8.1% |
| 255k–432k | 9.2% | 15–20 | 9.9% |
| 432k–604k | **10.1%** | 20–22 | 9.7% |
| 604k–900k | 7.9% | 22–30 | 6.2% |
| above 900k | **6.1%** | 30–45 | 6.5% |

- **Weighted by money, the default rate is 7.52%, not 8.07%.** Large loans are safer, so a count-based metric
  overstates losses on the money that is actually lent and may set the cutoff in the wrong place.
  *Correction, 19 Nov: with a flat margin the cutoff does not move. Margin and loss both scale with the amount, so
  break-even is 16.7% for every loan. What moves is the measured lift (+11.2% → +9.2%) and anything capacity-limited
  (review band, decline cap). The cutoff moves only under a term-scaled margin. See ADR 0003.*
- **The margin is flat (12% per loan) but the term runs from 9.5 to 34.5 months** (5th to 95th percentile, from credit
  ÷ annuity). A 10-month loan and a 34-month loan do not earn the same share of principal.
- **The label window may explain part of the term pattern.** `TARGET` counts difficulty in the first Y instalments.
  Long loans have more of their life after that window, so their lower rate may be partly an artefact. We cannot
  test this, but the write-up should say so.
- Revolving loans: the "principal" is a credit limit, not a drawn amount, so "EAD = full principal" is even more
  conservative for them. 278 revolving rows have no goods price.

**Action.** Add a short EDA section on amount and term. Write ADR 0003, "unit of profit": either weight profit by
`AMT_CREDIT` (recommended, since it is money) or keep unit weights and give the reason. Report both in E1–E5.
Consider a margin that scales with term, or at least test the target under both. The owner should confirm the choice,
because D12 was confirmed on the unit-weight numbers.

### 2. Thin file and the strongest signal (High)

| | Has bureau record | Thin file |
| --- | --- | --- |
| Applicants | 263,491 | 44,020 |
| Default | 7.7% | 10.1% |
| `EXT_SOURCE_3` missing | 6.9% | **96.9%** |
| `AMT_REQ_CREDIT_BUREAU_*` missing | 0.0% | **94.3%** |
| `EXT_SOURCE_1` missing | 55.6% | 60.8% |
| Ranking power of the mean external score (ROC-AUC) | 0.724 | **0.683** |

The EDA lists "missing `EXT_SOURCE_3` → 9.3% default" and "missing bureau enquiries → 10.3%" as separate missingness
signals. They are mostly the thin-file flag repeated. Four consequences were not discussed:

- **The model will be weakest exactly where the business wants to grow.** Only 1,344 thin-file applicants have
  `EXT_SOURCE_3`. `EXT_SOURCE_2` still works for them (0.672), so the group is not blind, but the Phase 6 slice report
  should expect a gap and the Phase 7 review band may need to be wider for this group.
- **Reason codes could punish having no history.** With missing-indicator flags (D39), a decline reason could read
  "external score 3 missing", which means "no credit history". That works against D01. Phase 7 should map these flags
  to one plain reason, or keep them out of reason codes, and the owner should decide whether that is acceptable.
- **Stage A is not bureau-free.** `EXT_SOURCE_3` looks bureau-derived and the six `AMT_REQ_CREDIT_BUREAU_*` columns are
  bureau enquiries, yet both sit in stage A. The A → B ablation (D25) will therefore understate what bureau data adds.
  Either move them to stage B or say so when reporting E-results.
- **Thin-file skews young** (7.7% under 25 vs 3.4%), so growing thin-file approvals interacts with the age fairness
  audit. Report the two slices together.

### 3. Shape of risk (Medium)

The plan calls for a WoE-binned scorecard (Phase 4) and a monotonic-constraint model (Phase 5). Both need to know
which inputs move risk in one direction. The EDA showed this only for the external scores. Loan amount and term are
hump-shaped (above), so a monotone constraint on them would be wrong. The credit-to-goods ratio, never shown in the
EDA, is one of the clearest main-table signals: 4.7% default near 1.0–1.08 up to **11.5%** above 1.21 (financed
extras such as insurance). Annuity-to-income is weak (7.2% to 8.5%). Phase 3 built these ratios without EDA evidence.

**Action.** A one-page table: for each candidate feature, direction (up, down, hump, none) and information value.
That table then drives both the WoE bins and the monotone constraints.

### 4. Same person, several IDs (Medium)

588 groups of rows (1,176 applications) share gender, birth date, ID-document date and registration date. These are
almost certainly the same person applying twice; 24 groups have different outcomes. **289 of these groups are split
across train, validation and test.** That is small (under 0.4% of rows), but D20 says "split by applicant" and the
split is really by application.

**Action.** This is the cheapest moment to fix it, because no model has been trained yet. Either relock the split
grouped on this person key (`--relock`, recorded in the log), or keep it and state the size of the overlap as a
known limit. I recommend relocking.

### 5. Placeholder codes the EDA missed (Medium)

| Column | What I found | Likely meaning |
| --- | --- | --- |
| `OWN_CAR_AGE` | 2,443 rows at 64 and 891 at 65, against 1–2 rows at 63 and 69 | A code, not a car age; recode to missing plus flag |
| `DAYS_LAST_PHONE_CHANGE` | 0 for 37,672 rows (12.3%), default 9.7% | Either the phone was updated in the application itself or 0 means unknown. The leakage table records "≤ 0, checked" but does not interpret 0 |
| `EXT_SOURCE_2` | 202 rows below 0.001 | Possibly a floor or a default value; check the distribution |

### 6. Application hour (Low)

The leakage table says to check that `HOUR_APPR_PROCESS_START` "is not a channel or branch artefact". This was not
done. Default runs from 10–11% at 5–7 am to 6.5% at 5 pm. The pattern may reflect channel, region or time zone
rather than the applicant. It is legitimate at application time, but it would be a strange reason code. Decide
whether to keep it.

### 7. `FLAG_EMP_PHONE` is the pensioner flag (Low)

`FLAG_EMP_PHONE = 0` matches `DAYS_EMPLOYED = 365243` in 55,374 of 55,386 rows. The EDA describes it as the strongest
age proxy "because pensioners give no work phone". More precisely, it **is** pension status, which is legitimate
income information and also an age stand-in. D40 should say this plainly, because the Phase 6 question becomes
"may income type be used", not "may a phone flag be used". It also duplicates the new `EMPLOYED_NA` flag.

### 8. Redundant pairs (Low)

Phase 3 removed the building-statistics duplicates, but four other pairs correlate above 0.95: `OBS_30` / `OBS_60`
social-circle counts (0.998), `AMT_CREDIT` / `AMT_GOODS_PRICE` (0.987), the two region ratings (0.951) and the phone /
employment flag above. They do no harm in gradient boosting, but they make logistic-regression coefficients unstable
and split SHAP credit, which shows up as two reason codes for one cause. Keep one of each for the scorecard and group
them for reason codes.

### 9. Earlier applications that mirror the current one (Low; checked)

The leakage table checked whether a recent bureau credit is the current loan reported back (0.5% match). The same
check was not done on `previous_application`. Results: 648 applicants have an earlier application with exactly the
same amount and annuity (465 of them refused before, so these are re-applications). 1,415 had an approval in the
seven days before, 60% not yet started. Their default rate (8.3%) is the portfolio rate, so there is no sign of a
leak. Add this to the leakage table as evidence.

### 10. No hidden time order (Low; checked)

D20 says a time split is impossible because there are no dates. The EDA did not test whether `SK_ID_CURR` follows
time. It does not appear to: across ID deciles the default rate stays at 7.9–8.3%, and the mean of `EXT_SOURCE_3` and
the revolving share are flat. Record this as the evidence behind D20.

### 11. Kaggle test comparison (Low)

The EDA compared the Kaggle test file on 3 columns and found the revolving gap. D41 then uses the file as "the shifted
population" for Phase 9. We do not know what else shifted. A quick adversarial check (a model that tells train rows
from test rows, plus its top features) would say what the drift simulation actually tests.

### 12. Fairness cells (Low)

The notebook uses age bands <25, 25–34, 35–44, 45–54, 55–64 and 65–74, but D15 does not name them. Every gender × age
cell is large enough: the smallest is men aged 65 and over (1,504 applicants, default 5.6% ± 1.2 points). Write the
bands into D15 and the config, so that Phase 6 cannot pick other bands after seeing results.

### 13. Process (Low)

- The notebook, data card and decision log are modified but not committed; all of Phase 3 is untracked. Commit
  Phase 2 as its own commit, so a reviewer can see where Phase 2 ended.
  *Correction, 19 Nov: Phase 2 was already committed (`3c27998`); the uncommitted edits were Phase 3 documentation and
  a notebook reformat. Phase 3 is now committed on its own (`f96f772`), before the review fixes.*
- `.virtual_documents/` (a Jupyter artefact) is not in `.gitignore`.
- Phase 3 was built while D37–D41 were still "proposed". That is fine under the log's rules, but findings 2 and 4
  above would change Phase 3 outputs.

## What the EDA got right

- The headline thin-file gap is solid: 10.1% vs 7.7% on 44,020 applicants is well outside chance.
- The leakage audit covers all 20 date columns in all tables and found the only real problem (17 rows).
- The proxy test turned a policy assumption (D23) into a measured result (D40). That is the strongest part of the phase.

## What the owner needs to decide

1. **Unit of profit (finding 1):** weight by loan amount (recommended) or keep one unit per loan. D12 was confirmed on
   unit weights, so please re-confirm the +10% target under the chosen unit.
2. **Reason codes for thin-file applicants (finding 2):** may "no credit-bureau history" be given as a decline
   reason?
3. **Relock the split by person (finding 4):** yes (recommended) or document the overlap.

Engineer actions that need no decision: the amount/term and feature-shape sections (1, 3), recoding the three codes
(5), the two extra leakage checks recorded (9, 10), the age bands in D15 (12), and the commit (13).

## Resolution (19 November 2026)

The owner asked for every finding to be resolved using the recommendations above and engineering judgment. Decisions
D49–D57 record what was decided, and the owner may overturn any of them.

| # | What was done | Where |
| --- | --- | --- |
| 1 | Profit is now weighted by loan amount; a term-scaled margin is experiment E6. Under the new measure the preliminary model gains **+9.2%** over approving everyone, under the +10% target, so D12 was put back to the owner, who **re-confirmed it** under amount weighting on 19 November. With per-loan break-evens under the term-scaled margin it would decline about 16% of applicants, which bears on the 10% cap (D14) | ADR 0003, D54, `configs/economics.yaml`, `scripts/preliminary_check.py`, `reports/preliminary_check.md` |
| 2 | The seven bureau-derived main-table columns moved to stage B; stage A uses external scores 1 and 2 only. "No or limited credit-bureau history" is one decline reason, at most once, and its use is measured. E7 tests a wider review band for thin-file applicants | D50, D53, `configs/reason_codes.yaml`, `credit_risk.features.application` |
| 3 | Shape and information value of all 157 features on the training fold: 17 steadily falling, 28 rising, 13 irregular, 1 hump. Loan amount, goods price and term are irregular, so they get no monotone constraint | D57, `make shapes`, `reports/feature_shapes.md` |
| 4 | The split now assigns whole persons to folds and was relocked (0 people span folds; fold default rates 8.07%, 8.07%, 8.08%) | D49, `credit_risk.data.split`, `configs/split_manifest.json` |
| 5 | `OWN_CAR_AGE` 64/65 and `DAYS_LAST_PHONE_CHANGE` 0 are recoded to missing with flags; `EXT_SOURCE_2` near 0 is a real tail (43.6% default) and is kept | D55, `credit_risk.data.clean` |
| 6 | Hour and weekday are excluded (new verdict `exclude`). The hour's risk mostly reflects region: 22% of applications in region rating 3 start by 7 am, 0.6% in rating 1 | D51, leakage table |
| 7 | `FLAG_EMP_PHONE` is dropped as a duplicate of `EMPLOYED_NA`; D40 now names pension status as the age proxy | D40, D52 |
| 8 | `OBS_60` is dropped; the remaining related pairs share one reason-code group | D52, `configs/reason_codes.yaml` |
| 9, 10 | Both checks are recorded as evidence in the leakage table, the data card and D20 | `reports/leakage_table.md`, `data/README.md` |
| 11 | Adversarial check: a model tells the files apart with ROC-AUC **0.887**. Loans in Kaggle's test are shorter (median 16.3 vs 20.0 months), and bureau enquiries sit in other time buckets (any in the last month 0.7% vs 14.2%; last quarter 39.3% vs 16.4%) | D41, EDA summary section 8 |
| 12 | Age bands fixed: <25, 25–34, 35–44, 45–54, 55–64, 65+. Thin-file results are reported with age | D56, `configs/economics.yaml` |
| 13 | Phase 3 committed on its own; `.virtual_documents/` ignored; the review fixes are a separate commit. Also added: the missing `make split / features / shapes / phase3 / checks` targets, which the Phase 3 docs used but the Makefile lacked | `.gitignore`, `Makefile` |

Every number in the resolution comes from `make checks` (notebook section 10), `make shapes` or `make preliminary`.
Tests: 44 pass (10 new). Lint is clean.

**Still with the owner:** a business view on D53 (thin-file decline reason); and, as before, D13, D14, D15 and D16.
D12 was re-confirmed under amount weighting on 19 November.
