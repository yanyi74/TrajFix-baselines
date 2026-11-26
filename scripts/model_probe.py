"""Small live gateway check; read existing credentials without copying or logging them."""
import json
from pathlib import Path
from model_config import get_model_config
import requests

root = Path(__file__).resolve().parents[1]
settings = get_model_config()
base, key = settings["base"], settings["key"]
model = settings["model"].removeprefix("openai/")
response = requests.post(base.rstrip('/') + '/chat/completions',
    headers={"Authorization": "Bearer " + key},
    json={"model": model, "messages": [{"role": "user", "content": "Reply with OK only."}],
          "max_tokens": 128, "temperature": 0}, timeout=60)
result = {"model": model, "http_status": response.status_code}
if response.ok:
    data = response.json()
    result["usage"] = data.get("usage")
    result["has_choices"] = bool(data.get("choices"))
    result["finish_reason"] = data.get("choices", [{}])[0].get("finish_reason")
    result["content"] = data.get("choices", [{}])[0].get("message", {}).get("content")
else:
    result["error"] = "Gateway returned non-success status; response body withheld"
(root / "results").mkdir(exist_ok=True)
(root / "results/model_probe.json").write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
