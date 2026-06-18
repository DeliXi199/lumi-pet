import json

from ..config import AGENT_PANEL_STATE_FILE


def load_agent_panel_state():
    if not AGENT_PANEL_STATE_FILE.exists():
        return {}
    try:
        data = json.loads(AGENT_PANEL_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_agent_panel_state(data):
    try:
        AGENT_PANEL_STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass
