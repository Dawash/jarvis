import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = BASE_DIR / "backend" / "uploads"
DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

KEYS_FILE = DATA_DIR / "api_keys.json"

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
SECRET_KEY = os.getenv("SECRET_KEY", "change-me")

MAX_CONCURRENT_AGENTS = int(os.getenv("MAX_CONCURRENT_AGENTS", "10"))
AGENT_TIMEOUT = int(os.getenv("AGENT_TIMEOUT", "300"))

MEMORY_DB_PATH = os.getenv("MEMORY_DB_PATH", str(DATA_DIR / "memory.db"))
ENABLE_SELF_EVOLUTION = os.getenv("ENABLE_SELF_EVOLUTION", "true").lower() == "true"
EVOLUTION_LOG_PATH = os.getenv("EVOLUTION_LOG_PATH", str(DATA_DIR / "evolution.log"))


def _load_saved_keys() -> dict:
    """Load API keys from persistent JSON file."""
    if KEYS_FILE.exists():
        try:
            return json.loads(KEYS_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_keys(keys: dict):
    """Save API keys to persistent JSON file."""
    KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEYS_FILE.write_text(json.dumps(keys, indent=2))


class APIKeys:
    """Mutable API key store — keys can be set from .env, saved file, or UI at runtime."""

    def __init__(self):
        saved = _load_saved_keys()
        self.anthropic = saved.get("anthropic") or os.getenv("ANTHROPIC_API_KEY", "")
        self.openai = saved.get("openai") or os.getenv("OPENAI_API_KEY", "")
        self.google = saved.get("google") or os.getenv("GOOGLE_API_KEY", "")

    def update(self, anthropic: str | None = None, openai: str | None = None, google: str | None = None):
        if anthropic is not None:
            self.anthropic = anthropic
        if openai is not None:
            self.openai = openai
        if google is not None:
            self.google = google
        self._persist()

    def _persist(self):
        _save_keys({
            "anthropic": self.anthropic,
            "openai": self.openai,
            "google": self.google,
        })

    @property
    def has_any(self) -> bool:
        return bool(self.anthropic)

    def to_status(self) -> dict:
        """Return masked status for UI (never expose full keys)."""
        def mask(key: str) -> dict:
            if not key:
                return {"set": False, "preview": ""}
            return {"set": True, "preview": key[:8] + "..." + key[-4:]}
        return {
            "anthropic": mask(self.anthropic),
            "openai": mask(self.openai),
            "google": mask(self.google),
            "ready": self.has_any,
        }


api_keys = APIKeys()
