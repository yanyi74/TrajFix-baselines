import importlib.metadata
import json
import os
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
from dotenv import load_dotenv
from model_config import get_model_config
load_dotenv(root / "vendor/HarnessFix/.env", override=True)
status = {"packages": {}}
for name in ("mini-swe-agent", "swebench", "datasets", "litellm", "docker"):
    try:
        status["packages"][name] = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        status["packages"][name] = None
status["docker_cli"] = shutil.which("docker")
status["docker_host_configured"] = bool(os.environ.get("DOCKER_HOST"))
status["docker_socket_exists"] = Path("/var/run/docker.sock").exists()
status["model_key_configured"] = bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("LITELLM_API_KEY"))
status["model_name_configured"] = bool(os.environ.get("TRAJFIX_MODEL"))
status["smoke_data_ready"] = (root / "data/smoke_manifest.json").exists()
status["docker_daemon_usable"] = False
if status["docker_socket_exists"] or status["docker_host_configured"]:
    try:
        import docker
        client = docker.from_env(timeout=5)
        status["docker_daemon_usable"] = client.ping()
        client.close()
    except Exception as e:
        status["docker_error_type"] = type(e).__name__
status["ready_for_real_run"] = bool(all(status["packages"].values()) and status["docker_cli"]
    and status["docker_daemon_usable"] and status["model_key_configured"] and status["model_name_configured"]
    and status["smoke_data_ready"])
try:
    get_model_config()
    status["live_smoke_gateway_key_present"] = True
except ValueError:
    status["live_smoke_gateway_key_present"] = False
status["ready_for_live_smoke"] = bool(all(status["packages"].values()) and status["docker_cli"]
    and status["docker_daemon_usable"] and status["live_smoke_gateway_key_present"] and status["smoke_data_ready"])
status["ready_for_real_run_scope"] = "full_HarnessFix_pipeline_requires_separate_model_registry_configuration"
print(json.dumps(status, indent=2))
