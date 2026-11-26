"""Exercise upstream execution, trajectory serialization, and HTIR construction.

Uses upstream DeterministicModel with scripted actions, NOT an LLM or benchmark.
Only our small fixture is executed locally; real SWE runs must use Docker.
"""
import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

from minisweagent.agents.default import DefaultAgent
from minisweagent.environments.local import LocalEnvironment
from minisweagent.models.test_models import DeterministicModel, make_output
from failure_analysis.htir import compile_swe_htir, render_view_summary

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "offline_smoke"
OUT.mkdir(parents=True, exist_ok=True)
TASK = "Fix add(a, b), which incorrectly subtracts its operands."


def run_case(fixed: bool) -> dict:
    name = "scripted_fixed" if fixed else "scripted_failed"
    with tempfile.TemporaryDirectory(prefix="trajfix-fixture-") as tmp:
        work = Path(tmp)
        (work / "calc.py").write_text("def add(a, b):\n    return a - b\n")
        (work / "test_calc.py").write_text(
            "import unittest\nfrom calc import add\n"
            "class TestAdd(unittest.TestCase):\n"
            "    def test_positive(self): self.assertEqual(add(2, 3), 5)\n"
            "    def test_negative(self): self.assertEqual(add(-2, 3), 1)\n"
        )
        command = f"{shlex.quote(sys.executable)} -B -m unittest -v test_calc"
        before = subprocess.run(command, shell=True, cwd=work, capture_output=True, text=True)
        assert before.returncode != 0, "Fixture must fail before repair"
        outputs = [make_output("Inspect the implementation.", [{"command": "cat calc.py"}], cost=0)]
        if fixed:
            outputs.append(make_output("Apply the scripted fixture correction.",
                                       [{"command": "sed -i 's/return a - b/return a + b/' calc.py"}], cost=0))
        outputs.extend([
            make_output("Execute the fixture tests.", [{"command": command}], cost=0),
            make_output("Submit fixture.", [{"command": "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"}], cost=0),
        ])
        # Upstream saves after every step. Keep those repeated writes on local
        # disk; publish one final snapshot to the shared filesystem.
        trajectory = work / f"{name}.traj.json"
        agent = DefaultAgent(
            DeterministicModel(outputs=outputs, cost_per_call=0),
            LocalEnvironment(cwd=str(work)),
            system_template="Offline scripted integration fixture.",
            instance_template="{{task}}", step_limit=6, cost_limit=0, output_path=trajectory,
        )
        result = agent.run(TASK)
        assert result["exit_status"] == "Submitted", result
        published = OUT / trajectory.name
        staging = OUT / (trajectory.name + ".tmp")
        staging.write_bytes(trajectory.read_bytes())
        staging.replace(published)
        trajectory = published
        after = subprocess.run(command, shell=True, cwd=work, capture_output=True, text=True)
        passed = after.returncode == 0
        assert passed == fixed, after.stdout + after.stderr
        log = OUT / f"{name}.tests.txt"
        log.write_text(after.stdout + after.stderr)
        report = OUT / f"{name}.report.json"
        report.write_text(json.dumps({name: {"resolved": passed}}))
        bundle = compile_swe_htir(name, "resolved" if passed else "test_failure", {
            "traj_path": str(trajectory), "report_path": str(report), "test_output_path": str(log),
        }, TASK)
        (OUT / f"{name}.htir.json").write_text(json.dumps(bundle, indent=2))
        (OUT / f"{name}.htir.txt").write_text(render_view_summary(bundle))
        data = json.loads(trajectory.read_text())
        assert len(data["model_calls"]) == len(outputs)
        assert bundle["stats"]["command_count"] >= 2
        return {"case": name, "tests_passed": passed, "model_calls": len(outputs),
                "htir_commands": bundle["stats"]["command_count"]}


results = [run_case(False), run_case(True)]
summary = {"status": "passed", "kind": "scripted_offline_integration",
           "real_llm_calls": 0, "benchmark_evaluation": False,
           "harnessfix_diagnosis_or_repair_executed": False, "cases": results}
(OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
