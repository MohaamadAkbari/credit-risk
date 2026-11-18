PY      ?= python
RAW     := data/home-credit-default-risk
INTERIM := data/interim
NB      := notebooks/01_eda.ipynb

.DEFAULT_GOAL := help
.PHONY: help install data interim leakage eda preliminary phase2 test lint

help:  ## List targets
	@grep -E '^[a-z0-9]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

install:  ## Install the package and dev tools (editable)
	$(PY) -m pip install -e ".[dev]"

data:  ## Download and unzip the Kaggle data (accept the competition rules on kaggle.com first)
	@if [ -f $(RAW)/application_train.csv ]; then echo "$(RAW) already present"; else \
	  kaggle competitions download -c home-credit-default-risk -p data/ && \
	  unzip -q data/home-credit-default-risk.zip -d $(RAW); fi

$(INTERIM)/application_train.parquet: | $(RAW)/application_train.csv
	$(PY) -m credit_risk.data.interim $(RAW) $(INTERIM)

$(RAW)/application_train.csv:
	@echo "Raw data missing: run 'make data'"; exit 1

interim: $(INTERIM)/application_train.parquet  ## Raw CSV -> Parquet in data/interim (about 1 minute)

leakage: interim  ## Rebuild the leakage table (configs/feature_availability.csv, reports/leakage_table.md)
	$(PY) -m credit_risk.data.availability

eda: interim  ## Re-execute the EDA notebook in place (figures go to reports/figures)
	$(PY) -m jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=900 $(NB)

preliminary:  ## Rough profit check on the main table (exploration, not a baseline)
	$(PY) scripts/preliminary_check.py $(RAW)

phase2: leakage eda  ## Everything behind the Phase 2 reports

test:  ## Unit tests (no data needed)
	$(PY) -m pytest

lint:  ## Static checks
	$(PY) -m ruff check src scripts tests
