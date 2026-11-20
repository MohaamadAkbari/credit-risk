"""Feature tables, one row per applicant (SK_ID_CURR), for ablation stages A, B and C (D25).

Every module declares SOURCES, the exact (table -> columns) it reads; build() loads only those.
tests/test_feature_sources.py checks every declared column against configs/feature_availability.csv,
so a feature cannot read the label, a protected attribute or an unvetted column without a test failing.
"""
