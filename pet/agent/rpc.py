import json
import subprocess
import threading
from pathlib import Path
from queue import Empty, Queue, SimpleQueue

from ..config import PI_DATA_DIR, ROOT
from .env import build_agent_env, detect_agent_proxy, resolve_pi_command


class PiRpcProcess:
    DIAGNOSTIC_MARKERS = (
        "error",
        "failed",
        "failure",
        "exception",
        "traceback",
        "timeout",
        "refused",
        "unavailable",
        "错误",
        "失败",
        "异常",
        "超时",
    )

    def __init__(self, session_id, session_path=None, output_queue=None):
        self.session_id = session_id
        self.session_path = Path(session_path) if session_path else None
        self.output_queue = output_queue or SimpleQueue()
        self.process = None
        self.pending = {}
        self.pending_lock = threading.Lock()
        self.request_counter = 0
        self.stderr_tail = ""
        self.alive = False

    def start(self):
        if self.process and self.process.poll() is None:
            return
        proxy_url = detect_agent_proxy()
        PI_DATA_DIR.mkdir(parents=True, exist_ok=True)
        env = build_agent_env(proxy_url)
        # Force child processes (e.g. Python the agent runs) to emit UTF-8 so
        # their stdout is not garbled (mojibake) on Windows code pages.
        env.setdefault("PYTHONIOENCODING", "utf-8")
        env.setdefault("PYTHONUTF8", "1")
        command = [resolve_pi_command(env), "--mode", "rpc"]
        if self.session_path and self.session_path.exists():
            command.extend(["--session", str(self.session_path)])
        else:
            command.extend(["--session-id", self.session_id, "--name", "Pet Agent"])
        self.process = subprocess.Popen(
            command,
            cwd=str(ROOT),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.alive = True
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        self.output_queue.put(("status", proxy_url, env))

    def _read_stdout(self):
        try:
            for line in self.process.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    # Non-JSON stray output is treated as a low-priority status
                    # blip, unless it looks like a runtime error that should be
                    # visible in the run details.
                    if self._looks_like_diagnostic(line):
                        self.output_queue.put(("rpc_stderr", line, None))
                    else:
                        self.output_queue.put(("activity", line, None))
                    continue
                if payload.get("type") == "response" and payload.get("id"):
                    with self.pending_lock:
                        waiter = self.pending.pop(payload.get("id"), None)
                    if waiter:
                        waiter.put(payload)
                    else:
                        self.output_queue.put(("rpc_event", payload, None))
                elif payload.get("type") == "extension_ui_request":
                    self._handle_extension_ui_request(payload)
                else:
                    self.output_queue.put(("rpc_event", payload, None))
        finally:
            self.alive = False
            self.output_queue.put(("rpc_exit", self.session_id, self.stderr_tail.strip()))

    def _read_stderr(self):
        # stderr is shown as run diagnostics in the agent panel. We still keep a
        # tail for exit reporting, but important failures should not be hidden
        # in the terminal only.
        try:
            for line in self.process.stderr:
                text = line.strip()
                if not text:
                    continue
                self.stderr_tail = (self.stderr_tail + "\n" + text)[-2000:]
                self.output_queue.put(("rpc_stderr", text, None))
        except OSError:
            pass

    @classmethod
    def _looks_like_diagnostic(cls, text):
        probe = str(text or "").lower()
        return any(marker in probe for marker in cls.DIAGNOSTIC_MARKERS)

    def _write_json_line(self, payload, raise_errors=False):
        if not self.process or not self.process.stdin or self.process.poll() is not None:
            if raise_errors:
                raise OSError("RPC stdin \u4e0d\u53ef\u7528")
            return
        try:
            self.process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self.process.stdin.flush()
        except OSError:
            if raise_errors:
                raise

    @staticmethod
    def _option_value(option):
        if isinstance(option, dict):
            return option.get("value", option.get("label"))
        return option

    @staticmethod
    def _option_search_text(option):
        if isinstance(option, dict):
            parts = [option.get("label"), option.get("value"), option.get("description"), option.get("text")]
            return " ".join(str(part) for part in parts if part).lower()
        return str(option).lower()

    def _default_approval_option(self, options):
        approval_keywords = (
            "allow all",
            "approve all",
            "always allow",
            "always approve",
            "agree all",
            "yes to all",
            "all",
            "always",
            "approve",
            "allow",
            "agree",
            "yes",
            "\u5168\u90e8",
            "\u59cb\u7ec8",
            "\u540c\u610f",
            "\u5141\u8bb8",
            "\u6279\u51c6",
            "\u786e\u8ba4",
        )
        for keyword in approval_keywords:
            for option in options:
                if keyword in self._option_search_text(option):
                    return self._option_value(option)
        return self._option_value(options[0]) if options else None

    @staticmethod
    def _looks_like_approval(method, title):
        text = f"{method or ''} {title or ''}".lower()
        return any(
            marker in text
            for marker in (
                "confirm",
                "approve",
                "approval",
                "permission",
                "authorize",
                "authorization",
                "consent",
                "allow",
                "\u786e\u8ba4",
                "\u5ba1\u6279",
                "\u6279\u51c6",
                "\u5141\u8bb8",
                "\u6388\u6743",
                "\u540c\u610f",
            )
        )

    def _approve_response(self, response):
        response.update(
            {
                "confirmed": True,
                "approved": True,
                "accepted": True,
                "allowed": True,
                "cancelled": False,
            }
        )

    def _handle_extension_ui_request(self, payload):
        method = payload.get("method")
        title = payload.get("title") or payload.get("message") or method or "extension_ui_request"
        if method == "notify":
            self.output_queue.put(("flash", str(payload.get("message") or ""), None))
            return
        if method in {"setStatus", "setTitle"}:
            # Purely cosmetic Pi side-channel updates: surface as transient status.
            text = payload.get("statusText") or payload.get("title") or ""
            if text:
                self.output_queue.put(("activity", str(text), None))
            return
        response = {"type": "extension_ui_response", "id": payload.get("id")}
        if method == "confirm":
            self._approve_response(response)
            self.output_queue.put(("flash", f"\u5df2\u81ea\u52a8\u5168\u90e8\u540c\u610f\uff1a{title}", None))
        elif method == "select":
            options = payload.get("options") or []
            value = self._default_approval_option(options)
            if value is None:
                response["cancelled"] = True
            else:
                response["cancelled"] = False
                response["value"] = value
                self._approve_response(response)
            self.output_queue.put(("flash", f"\u5df2\u81ea\u52a8\u9009\u62e9\u540c\u610f\u9879\uff1a{title}", None))
        elif method in {"input", "editor"}:
            response["cancelled"] = True
        elif self._looks_like_approval(method, title):
            self._approve_response(response)
            self.output_queue.put(("flash", f"\u5df2\u81ea\u52a8\u6279\u51c6\uff1a{title}", None))
        else:
            response["cancelled"] = True
        self._write_json_line(response)

    def send(self, command, timeout=30):
        self.start()
        if not self.process or not self.process.stdin or self.process.poll() is not None:
            raise RuntimeError("RPC \u8fdb\u7a0b\u672a\u8fd0\u884c")
        with self.pending_lock:
            self.request_counter += 1
            request_id = f"pet_{self.request_counter}"
            waiter = Queue(maxsize=1)
            self.pending[request_id] = waiter
        payload = dict(command)
        payload["id"] = request_id
        try:
            self._write_json_line(payload, raise_errors=True)
        except OSError:
            with self.pending_lock:
                self.pending.pop(request_id, None)
            raise
        try:
            response = waiter.get(timeout=timeout)
        except Empty as exc:
            with self.pending_lock:
                self.pending.pop(request_id, None)
            raise TimeoutError(f"\u7b49\u5f85 RPC \u54cd\u5e94\u8d85\u65f6\uff1a{command.get('type')}") from exc
        if not response.get("success", False):
            raise RuntimeError(response.get("error") or f"RPC \u547d\u4ee4\u5931\u8d25\uff1a{command.get('type')}")
        return response

    def stop(self):
        process = self.process
        self.process = None
        self.alive = False
        if not process or process.poll() is not None:
            return
        try:
            process.terminate()
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
            except OSError:
                pass
