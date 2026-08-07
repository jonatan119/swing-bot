"""
Tracks which symbols were recently alerted so the same setup doesn't fire
a fresh Discord message every single scan while it's still valid.

State is a simple JSON file: {"AAPL": "2026-08-04", "MSFT": "2026-08-05", ...}
It's written to config.STATE_FILE_PATH and committed back to the repo by
the GitHub Actions workflow after each run (see .github/workflows/scan.yml),
so it persists across runs even though each run starts from a fresh
container.
"""
import json
import os
from datetime import date, datetime, timedelta

import config


def load_state():
    """Returns {symbol: last_alert_date_str}. Empty dict if no file yet."""
    if not os.path.exists(config.STATE_FILE_PATH):
        return {}
    try:
        with open(config.STATE_FILE_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # Corrupt or unreadable state file - don't crash the whole scan over
        # it, just start fresh (worst case: a few duplicate alerts once).
        return {}


def save_state(state):
    os.makedirs(os.path.dirname(config.STATE_FILE_PATH), exist_ok=True)
    with open(config.STATE_FILE_PATH, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def is_in_cooldown(symbol, state, cooldown_days=None):
    cooldown_days = cooldown_days if cooldown_days is not None else config.ALERT_COOLDOWN_DAYS
    last_alert_str = state.get(symbol)
    if not last_alert_str:
        return False
    try:
        last_alert_date = datetime.strptime(last_alert_str, "%Y-%m-%d").date()
    except ValueError:
        return False
    return (date.today() - last_alert_date) < timedelta(days=cooldown_days)


def mark_alerted(symbol, state):
    state[symbol] = date.today().isoformat()
