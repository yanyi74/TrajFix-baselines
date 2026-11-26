"""Convert three public HF dataset-server rows into disjoint smoke subsets.

These are evaluation fixtures, not model-training data or a statistically valid
HarnessFix experiment. Preserve all fields required by the official evaluator.
"""
import argparse
import hashlib
import json
from pathlib import Path
from datasets import Dataset, DatasetDict

parser = argparse.ArgumentParser()
parser.add_argument("rows_json", type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
source = json.loads(args.rows_json.read_text())
rows = source["rows"][:3]
assert len(rows) == 3
assert all(not r.get("truncated_cells") for r in rows), "Reject truncated benchmark fields"
records = [r["row"] for r in rows]
assert len({r["instance_id"] for r in records}) == 3
required = {"instance_id", "repo", "base_commit", "problem_statement", "patch", "test_patch", "FAIL_TO_PASS", "PASS_TO_PASS"}
manifest = {"dataset": "princeton-nlp/SWE-bench_Verified", "split": "test",
            "purpose": "smoke_only_not_model_training", "source_sha256": hashlib.sha256(args.rows_json.read_bytes()).hexdigest(), "subsets": {}}
for split, record in zip(("dev", "val", "heldout"), records):
    assert required <= record.keys()
    target = root / "data" / f"smoke_{split}"
    target.mkdir(parents=True, exist_ok=True)
    DatasetDict({"test": Dataset.from_list([record])}).save_to_disk(str(target))
    (target / "instance_ids.txt").write_text(record["instance_id"] + "\n")
    manifest["subsets"][split] = [record["instance_id"]]
(root / "data" / "smoke_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
(root / "data" / "smoke_instance.json").write_text(json.dumps([records[0]], indent=2) + "\n")
print(json.dumps(manifest, indent=2))
