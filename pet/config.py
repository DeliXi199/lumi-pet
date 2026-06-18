from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SETTINGS_FILE = ROOT / "pet_settings.json"
AGENT_PANEL_STATE_FILE = ROOT / "agent_panel_state.json"
INSTANCE_LOCK_FILE = ROOT / "pet_app.lock"

PI_BIN_DIR = Path(r"D:\Tools\npm-global")
PI_CMD = PI_BIN_DIR / "pi.cmd"
PI_DATA_DIR = Path(r"D:\Tools\pi-agent-data")
GIT_BASH_DIR = Path(r"D:\Program Files\Git\bin")
# NOTE: the trailing character here was a full-width quote in the original
# source, which is a SyntaxError. Fixed to a normal ASCII double quote.
DEFAULT_PROXY_URL = "http://127.0.0.1:7897"
