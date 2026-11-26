"""Run the official evaluator with isolated networking and durable result copies.

No changes to tests, patches, grading, or the generated evaluation script.
Only sets container network mode to none for our bridge-free Docker daemon.
"""
import argparse
import json
import os
import runpy
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import docker

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("kind", choices=["gold", "noop", "model"])
parser.add_argument("--run-id", default=None)
args = parser.parse_args()
run_id = args.run_id or f"trajfix_{args.kind}_{datetime.now(timezone.utc):%Y%m%dT%H%M%S%f}"
if not all(c.isalnum() or c in "_-" for c in run_id):
    raise SystemExit("run-id must contain only letters, digits, underscores, or hyphens")
runtime = Path("/tmp/trajfix-real-eval") / run_id
runtime.mkdir(parents=True, exist_ok=True)
dataset = root / "data/smoke_instance.json"
instance = json.loads(dataset.read_text())[0]
if args.kind == "gold":
    predictions = "gold"
elif args.kind == "noop":
    patch = "diff --git a/trajfix_environment_probe.txt b/trajfix_environment_probe.txt\nnew file mode 100644\n--- /dev/null\n+++ b/trajfix_environment_probe.txt\n@@ -0,0 +1 @@\n+Environment verification; no source changes.\n"
    predictions = str(runtime / "noop.jsonl")
    Path(predictions).write_text(json.dumps({"instance_id": instance["instance_id"],
        "model_name_or_path": "noop_control", "model_patch": patch}) + "\n")
else:
    predictions = str(root / "results/live_rollout/predictions.jsonl")
    if not Path(predictions).is_file():
        raise SystemExit("Run live_rollout.py first")
os.environ["DOCKER_HOST"] = "unix:///tmp/trajfix-docker/run/docker.sock"
original_create = docker.models.containers.ContainerCollection.create
def create_without_network(self, *a, **kw):
    kw.setdefault("network_mode", "none")
    kw.setdefault("mem_limit", "16g")
    kw.setdefault("nano_cpus", 4_000_000_000)
    return original_create(self, *a, **kw)
docker.models.containers.ContainerCollection.create = create_without_network
os.chdir(runtime)
sys.argv = ["swebench.harness.run_evaluation", "--dataset_name", str(dataset),
    "--predictions_path", predictions, "--instance_ids", instance["instance_id"],
    "--run_id", run_id, "--max_workers", "1", "--timeout", "600",
    "--namespace", "swebench", "--cache_level", "instance", "--clean", "False",
    "--report_dir", str(runtime / "reports")]
try:
    runpy.run_module("swebench.harness.run_evaluation", run_name="__main__")
finally:
    shutil.copytree(runtime, root / "results" / run_id, dirs_exist_ok=True)
