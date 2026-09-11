"""
Lightweight, dependency-free environment loader for BRIGHTS.

Loads key=value pairs from a local `.env` file into os.environ (without overriding
values already set in the real environment). Imported first by app.main so that data
providers see the configured API keys at construction time.
"""

import os


def load_env_file() -> None:
    # backend/.env  (this file lives at backend/app/config.py)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(base_dir, ".env")
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                # Do not override values explicitly set in the environment.
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        # Never let config loading crash the app; providers will just see no keys.
        pass


load_env_file()
