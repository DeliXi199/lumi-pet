import os
import shutil
import socket
import subprocess

from ..config import DEFAULT_PROXY_URL, GIT_BASH_DIR, PI_BIN_DIR, PI_CMD, PI_DATA_DIR, ROOT


def port_is_open(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.12):
            return True
    except OSError:
        return False


def detect_agent_proxy():
    for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY"):
        value = os.environ.get(key) or os.environ.get(key.lower())
        if value:
            return value
    for port in (7897, 7890, 7899, 10809, 10808, 1080):
        if port_is_open(port):
            return f"http://127.0.0.1:{port}"
    return DEFAULT_PROXY_URL


def build_agent_env(proxy_url):
    env = os.environ.copy()
    existing_path = env.get("Path") or env.get("PATH") or ""
    path_parts = [str(PI_BIN_DIR), str(GIT_BASH_DIR), existing_path]
    env["Path"] = ";".join(part for part in path_parts if part)
    env["PATH"] = env["Path"]
    env["PI_CODING_AGENT_DIR"] = str(PI_DATA_DIR)
    env["HTTP_PROXY"] = proxy_url
    env["HTTPS_PROXY"] = proxy_url
    env["ALL_PROXY"] = proxy_url
    env.setdefault("NO_PROXY", "localhost,127.0.0.1,::1")
    return env


def resolve_pi_command(env=None):
    if PI_CMD.exists():
        return str(PI_CMD)
    search_path = None
    if env is not None:
        search_path = env.get("Path") or env.get("PATH")
    return shutil.which("pi", path=search_path) or shutil.which("pi.cmd", path=search_path) or "pi"


def build_plain_terminal_env():
    env = os.environ.copy()
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "PI_CODING_AGENT_DIR"):
        env.pop(key, None)
        env.pop(key.lower(), None)
    return env


def launch_agent_terminal(with_proxy=True):
    proxy_url = detect_agent_proxy() if with_proxy else None
    if with_proxy:
        PI_DATA_DIR.mkdir(parents=True, exist_ok=True)
        env = build_agent_env(proxy_url)
    else:
        env = build_plain_terminal_env()
    subprocess.Popen(
        ["powershell.exe", "-NoLogo", "-NoExit"],
        cwd=str(ROOT),
        env=env,
        creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
    )
    return proxy_url
