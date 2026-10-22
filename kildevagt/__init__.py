"""Kildevagt: a prototype of one scraper core shared by many sources."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv():
    """Read KEY=VALUE lines from .env (never committed) into the environment."""
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep and not line.startswith("#"):
                os.environ.setdefault(key.strip(), value.strip())


def user_agent() -> str:
    """Name the project and say how to reach us, so a site owner can write instead of block."""
    _load_dotenv()
    contact = os.environ.get("KILDEVAGT_CONTACT")
    if not contact:
        raise SystemExit("Set KILDEVAGT_CONTACT (an email address) in .env: "
                         "sites we fetch from must be able to reach whoever runs this.")
    return f"Kildevagt-prototype/0.1 (research prototype; contact {contact})"
