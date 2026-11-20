"""configs/reason_codes.yaml must refer only to features that exist, and each feature to one group."""
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / "configs" / "reason_codes.yaml").read_text())
MANIFEST = json.loads((ROOT / "configs" / "feature_manifest.json").read_text())
ALL = {f for b in MANIFEST["blocks"].values() for f in b["features"]}


def test_listed_features_and_blocks_exist():
    for name, g in CFG["groups"].items():
        assert set(g.get("features", [])) <= ALL, name
        assert set(g.get("blocks", [])) <= set(MANIFEST["blocks"]), name
    assert set(CFG["hidden"]) <= ALL


def test_each_feature_in_at_most_one_group():
    seen = {}
    for name, g in CFG["groups"].items():
        members = set(g.get("features", []))
        for b in g.get("blocks", []):
            members |= set(MANIFEST["blocks"][b]["features"])
        for f in members:
            assert f not in seen, f"{f} in {seen[f]} and {name}"
            seen[f] = name
    assert not set(CFG["hidden"]) & set(seen)
