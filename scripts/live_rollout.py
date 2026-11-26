"""One bounded real-model rollout with the upstream HarnessFix base agent.

Agent receives only the issue text and the pre-fix repository. Gold patch,
test patch, and evaluator results are never included in its model context.
"""
import json
import os
import shutil
import signal
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
os.environ["MSWEA_GLOBAL_CONFIG_DIR"] = str(root / ".runtime/mini-config")
os.environ["MSWEA_SILENT_STARTUP"] = "1"
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
os.environ["DOCKER_HOST"] = "unix:///tmp/trajfix-docker/run/docker.sock"
os.environ["PATH"] = "/tmp/trajfix-docker/bin:" + os.environ["PATH"]

import yaml
from model_config import get_model_config
from minisweagent.agents.default import DefaultAgent
from minisweagent.environments.docker import DockerEnvironment
from minisweagent.models.litellm_textbased_model import LitellmTextbasedModel

settings = get_model_config()
os.environ["OPENAI_API_KEY"] = settings["key"]
base = settings["base"]
model_name = settings["model"]
record = json.loads((root / "data/smoke_instance.json").read_text())[0]
config = yaml.safe_load((root / "vendor/HarnessFix/task_agent/mini-swe-agent/src/minisweagent/config/extra/swebench_xml.yaml").read_text())
runtime = Path("/tmp/trajfix-live-rollout")
runtime.mkdir(exist_ok=True)
out = root / "results/live_rollout"
out.mkdir(parents=True, exist_ok=True)

class LoggedAgent(DefaultAgent):
    def step(self):
        print(f"Step {self.n_calls+1}", flush=True)
        result = super().step()
        if result:
            print(f"Observation return code: {result[-1].get('extra', {}).get('returncode')}", flush=True)
        return result

model_config = config["model"]
model = LitellmTextbasedModel(model_name=model_name,
    action_regex=model_config["action_regex"], format_error_template=model_config["format_error_template"],
    cost_tracking="ignore_errors",
    model_kwargs={"api_base": base, "temperature": 0, "max_tokens": 4096,
                  "timeout": 120, "num_retries": 0})
env = DockerEnvironment(image="swebench/sweb.eval.x86_64.astropy_1776_astropy-12907:latest",
    executable="/tmp/trajfix-docker/bin/docker", cwd="/testbed", timeout=90,
    run_args=["--rm", "--network", "none", "--memory", "16g", "--cpus", "4"],
    env=config["environment"]["env"])
agent_config = dict(config["agent"])
agent_config.update(step_limit=20, cost_limit=2.0, output_path=runtime / "trajectory.json")
agent = LoggedAgent(model, env, **agent_config)
started = time.time()
def deadline(signum, frame):
    raise TimeoutError("Live smoke rollout reached its 15-minute wall-clock limit")
signal.signal(signal.SIGALRM, deadline)
signal.alarm(900)
try:
    # Official images add a SWE-bench preparation commit (permissions/build deps).
    result = env.execute({"command": "git rev-parse HEAD"})
    image_head = result["output"].strip()
    if result["returncode"]:
        raise RuntimeError("Cannot inspect container HEAD")
    if image_head != record["base_commit"]:
        parent = env.execute({"command": "git rev-parse HEAD^"})
        changes = env.execute({"command": f"git diff --raw --no-abbrev {record['base_commit']} HEAD"})
        content_changes = [line.split("\t", 1)[1] for line in changes["output"].splitlines()
                           if "\t" in line and line.split()[2] != line.split()[3]]
        if parent["returncode"] or changes["returncode"] or parent["output"].strip() != record["base_commit"] or content_changes != ["pyproject.toml"]:
            raise RuntimeError("Unexpected changes between official image and benchmark base_commit")
    (runtime / "environment.json").write_text(json.dumps({"base_commit": record["base_commit"],
        "image_head": image_head, "source_content_matches_base": True}, indent=2) + "\n")
    result = agent.run(record["problem_statement"])
    patch = result.get("submission", "")
    (runtime / "predictions.jsonl").write_text(json.dumps({
        "instance_id": record["instance_id"], "model_name_or_path": model_name,
        "model_patch": patch}) + "\n")
    (runtime / "model.patch").write_text(patch)
    (runtime / "summary.json").write_text(json.dumps({"instance_id": record["instance_id"],
        "model": model_name, "exit_status": result.get("exit_status"), "api_calls": agent.n_calls,
        "wall_seconds": round(time.time()-started, 2), "patch_bytes": len(patch.encode()),
        "gold_or_test_patch_in_prompt": False, "benchmark_verified": False}, indent=2) + "\n")
    print((runtime / "summary.json").read_text(), flush=True)
finally:
    signal.alarm(0)
    env.cleanup()
    shutil.copytree(runtime, out, dirs_exist_ok=True)
