"""Central config and environment loader. Import this everywhere."""

import os
from pathlib import Path
import yaml
from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).parent.parent.parent


def load_config() -> dict:
    config_path = _ROOT / "config.yaml"
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    # Allow env var to override document_id
    env_doc_id = os.getenv("GOOGLE_DOC_ID")
    if env_doc_id:
        cfg["google_docs"]["document_id"] = env_doc_id

    return cfg


def get_openai_key() -> str:
    key = os.getenv("OPENAI_API_KEY", "")
    if not key:
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. Add it to your .env file."
        )
    return key


def project_root() -> Path:
    return _ROOT
