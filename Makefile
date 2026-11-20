PY      ?= python
RAW     := data/home-credit-default-risk
INTERIM := data/interim
NB      := notebooks/01_eda.ipynb

.DEFAULT_GOAL := help
.PHONY: help install data interim validate verify leakage dictionary eda checks dashboard preliminary phase2 split features shapes phase3 test lint

help:  ## List targets
	@grep -E '^[a-z0-9]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

install:  ## Install the package and dev tools (editable)
	$(PY) -m pip install -e ".[dev]"

data:  ## Download and unzip the Kaggle data (accept the competition rules on kaggle.com first)
	@if [ -f $(RAW)/application_train.csv ]; then echo "$(RAW) already present"; else \
	  kaggle competitions download -c home-credit-default-risk -p data/ && \
	  $(PY) scripts/check_archive.py data/home-credit-default-risk.zip && \
	  unzip -q data/home-credit-default-risk.zip -d $(RAW); fi

$(INTERIM)/application_train.parquet: | $(RAW)/application_train.csv
	$(PY) -m credit_risk.data.interim $(RAW) $(INTERIM)

$(RAW)/application_train.csv:
	@echo "Raw data missing: run 'make data'"; exit 1

interim: $(INTERIM)/application_train.parquet  ## Raw CSV -> Parquet in data/interim (about 1 minute)

validate: $(INTERIM)/.validated  ## Check the data against rules and the recorded release (configs/data_contract.json)

# Runs once per change of the interim data or the contract; split and features refuse to build on data that fails.
$(INTERIM)/.validated: $(INTERIM)/application_train.parquet configs/data_contract.json configs/feature_availability.csv
	$(PY) -m credit_risk.data.validate
	@touch $@

leakage: interim  ## Rebuild the leakage table (configs/feature_availability.csv, reports/leakage_table.md)
	$(PY) -m credit_risk.data.availability

dictionary: interim  ## Data dictionary for all 218 columns (configs/data_dictionary.csv, reports/data_dictionary.md)
	$(PY) -m credit_risk.data.dictionary

dashboard: dictionary shapes  ## Aggregated datasets for the stakeholder dashboard (reports/dashboard/*.json)
	$(PY) scripts/dashboard_data.py

eda: interim  ## Re-execute the EDA notebook in place (figures go to reports/figures)
	$(PY) -m jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=900 $(NB)

checks:  ## Checks added by the Phase 2 manager review (also run in notebook section 10)
	$(PY) scripts/phase2_review_checks.py $(INTERIM)

preliminary:  ## Rough profit check on the main table (exploration, not a baseline)
	$(PY) scripts/preliminary_check.py $(RAW)

phase2: leakage dictionary eda checks  ## Everything behind the Phase 2 reports

split: validate  ## Build the person-grouped train/valid/test split; refuses to change a locked split (add ARGS=--relock)
	$(PY) -m credit_risk.data.split $(ARGS)

features: validate  ## Stage A/B/C feature tables and the audit table in data/processed (about 20 s)
	$(PY) -m credit_risk.features.build

shapes: split features  ## Shape and information value of every feature, training fold only
	$(PY) -m credit_risk.features.shapes

phase3: validate split features shapes  ## Everything behind the Phase 3 reports

verify:  ## Check data/processed against the fingerprints in configs/feature_manifest.json
	$(PY) -m credit_risk.features.build --check

test:  ## Unit tests (no data needed)
	$(PY) -m pytest

lint:  ## Static checks
	$(PY) -m ruff check src scripts tests
