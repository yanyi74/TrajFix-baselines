"""Load local model settings without serializing credentials into artifacts."""
import os
from pathlib import Path

from dotenv import dotenv_values


def get_model_config():
    root = Path(__file__).resolve().parents[1]
    settings = dict(dotenv_values(root / ".env"))
    credential_file = os.environ.get("TRAJFIX_CREDENTIALS_FILE") or settings.get("TRAJFIX_CREDENTIALS_FILE")
    if credential_file:
        settings = {**dotenv_values(Path(credential_file).expanduser()), **settings}
    settings.update(os.environ)
    key = settings.get("OPENAI_API_KEY") or settings.get("AIHUB_API_KEY")
    base = settings.get("OPENAI_BASE_URL") or settings.get("AIHUB_BASE_URL")
    model = settings.get("TRAJFIX_SMOKE_MODEL") or "openai/deepseek-v4-pro"
    if not key or not base:
        raise ValueError("Set OPENAI_API_KEY and OPENAI_BASE_URL in .env or the environment")
    if not model.startswith("openai/"):
        raise ValueError("This smoke runner expects an OpenAI-compatible model named openai/<model>")
    return {"key": key, "base": base.rstrip("/"), "model": model}
