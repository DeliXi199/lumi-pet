import subprocess
import threading
import time
from pathlib import Path
from queue import Empty

from ..agent.env import build_agent_env, detect_agent_proxy, launch_agent_terminal, resolve_pi_command
from ..agent.rpc import PiRpcProcess
from ..config import PI_DATA_DIR, ROOT
from ..qt import QApplication, QAction, QMenu, Qt
from ..utils import clamp, extract_message_text, summarize_tool_payload

# Status-dot colors (Codex-like, theme independent).
DOT_BUSY = "#d2a24c"
DOT_CONNECTED = "#56bc9a"
DOT_IDLE = "#6b7079"


class AgentPanelRpcMixin:
    def ensure_rpc_process(self):
        if self.rpc is None or not self.rpc.alive:
            self.rpc = PiRpcProcess(self.current_session_id, self.current_session_path, self.message_queue)
        self.rpc.start()
        return self.rpc

    def update_status_labels(self, proxy_url=None, env=None):
        proxy_url = proxy_url or detect_agent_proxy()
        env = env or build_agent_env(proxy_url)
        pi_command = resolve_pi_command(env)
        pi_state = "\u53ef\u7528" if pi_command != "pi" else "\u672a\u53d1\u73b0"
        proxy_label = proxy_url.replace("http://", "")
        mode = "RPC" if self.rpc_enabled else "print"
        connected = bool(self.rpc and self.rpc.alive)
        connection = "\u5df2\u8fde" if connected else "\u672a\u8fde"
        model = ""
        thinking = ""
        if isinstance(self.rpc_state, dict):
            model = self.rpc_state.get("model") or self.rpc_state.get("modelId") or ""
            if isinstance(model, dict):
                provider = model.get("provider") or model.get("providerId") or ""
                model_name = model.get("modelId") or model.get("id") or model.get("name") or ""
                model = "/".join(part for part in (provider, model_name) if part)
            if not model and isinstance(self.rpc_state.get("modelInfo"), dict):
                model = self.rpc_state["modelInfo"].get("modelId") or self.rpc_state["modelInfo"].get("model") or ""
            thinking = self.rpc_state.get("thinkingLevel") or ""
        model_display = model
        if len(model_display) > 28:
            model_display = model_display[:25] + "..."
        # Single status dot replaces the old row of pills. Details live in the
        # tooltip so the header stays clean and Codex-like.
        if self.pi_running:
            dot_color = DOT_BUSY
        elif connected:
            dot_color = DOT_CONNECTED
        else:
            dot_color = DOT_IDLE
        if hasattr(self, "status_dot"):
            self.status_dot.setStyleSheet(f"color: {dot_color}; padding-left: 2px; font-size: 11px;")
            self.status_dot.setToolTip(
                f"Proxy {proxy_label}\nPi {pi_state}\n{mode} {connection}"
            )
        detail = model_display or "unknown"
        if thinking:
            detail = f"{detail}  \u00b7  {thinking}"
        self.model_status.setText(detail)
        self.model_status.setToolTip(str(model or "unknown"))
        chip = getattr(self, "model_chip", None)
        if chip is not None:
            chip_text = detail or "\u6a21\u578b"
            if len(chip_text) > 22:
                chip_text = chip_text[:21] + "\u2026"
            chip.setText(chip_text)
        self._update_context_label()

    def extract_context_usage(self):
        stats = getattr(self, "rpc_stats", None)
        if isinstance(stats, dict):
            usage = stats.get("contextUsage")
            if isinstance(usage, dict):
                used = self._first_number(usage, ("tokens", "usedTokens", "used", "contextTokens", "totalTokens"))
                total = self._first_number(usage, ("contextWindow", "maxContextTokens", "windowSize", "limit", "total"))
                percent = self._first_number(usage, ("percent", "usedPercent"))
                if total is None:
                    total = self._state_context_window()
                if used is None and percent is not None and total:
                    used = total * percent / 100.0
                if total and total > 0:
                    if used is None:
                        return None, None, float(total)
                    used = max(0.0, min(float(used), float(total)))
                    if percent is None:
                        percent = 100.0 * used / float(total)
                    left_pct = max(0.0, 100.0 - float(percent))
                    return left_pct, used, float(total)

        state = self.rpc_state
        if not isinstance(state, dict):
            return None
        used = None
        total = None
        containers = [state, state.get("usage"), state.get("contextUsage"),
                      state.get("tokenUsage"), state.get("context"),
                      state.get("model"), state.get("modelInfo")]
        for container in containers:
            if not isinstance(container, dict):
                continue
            used = self._first_number(container, ("usedTokens", "used", "promptTokens", "totalTokens", "tokenCount", "contextTokens"))
            total = self._first_number(container, ("contextWindow", "maxContextTokens", "windowSize", "limit", "total", "maxTokens"))
            if used is not None and total:
                break
            if total and used is None:
                break
        if not total or total <= 0:
            return None
        if used is None:
            return None, None, float(total)
        used = max(0.0, min(float(used), float(total)))
        left_pct = max(0.0, 100.0 * (total - used) / total)
        return left_pct, used, float(total)

    @staticmethod
    def _first_number(container, keys):
        if not isinstance(container, dict):
            return None
        for key in keys:
            value = container.get(key)
            if isinstance(value, (int, float)):
                return float(value)
        return None

    def _state_context_window(self):
        state = self.rpc_state if isinstance(self.rpc_state, dict) else {}
        for container in (state, state.get("model"), state.get("modelInfo"), state.get("context")):
            total = self._first_number(container, ("contextWindow", "maxContextTokens", "windowSize", "limit", "total", "maxTokens"))
            if total:
                return total
        return None

    @staticmethod
    def _format_token_count(value):
        try:
            n = float(value)
        except (TypeError, ValueError):
            return "0"
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
        if n >= 1_000:
            return f"{n / 1_000:.1f}K".replace(".0K", "K")
        return str(int(n))

    def _update_context_label(self):
        label = getattr(self, "context_label", None)
        if label is None:
            return
        usage = self.extract_context_usage()
        if not usage:
            label.setText("上下文 --")
            label.setToolTip("当前 RPC 统计还没有返回 contextUsage；发送消息或刷新状态后会自动更新。")
            label.show()
            return
        left_pct, used, total = usage
        total_str = self._format_token_count(total)
        if used is None:
            label.setText(f"上下文 ?/{total_str}")
            label.setToolTip(f"上下文窗口 {int(total)} tokens；当前已用量需要等待下一次模型回复或 stats 刷新。")
        else:
            used_str = self._format_token_count(used)
            label.setText(f"上下文 {used_str}/{total_str} · 剩 {left_pct:.0f}%")
            label.setToolTip(f"已用 {int(used)} / {int(total)} tokens（剩余 {left_pct:.0f}%）")
        label.show()

    def summarize_rpc_state(self, state):
        if not isinstance(state, dict):
            return summarize_tool_payload(state, limit=280)
        model = state.get("model")
        if isinstance(model, dict):
            provider = model.get("provider") or model.get("providerId") or ""
            model_name = model.get("modelId") or model.get("id") or model.get("name") or ""
            model = "/".join(part for part in (provider, model_name) if part)
        thinking = state.get("thinkingLevel") or "unknown"
        session_name = state.get("sessionName") or "(\u672a\u547d\u540d)"
        messages = state.get("messageCount", 0)
        pending = state.get("pendingMessageCount", 0)
        streaming = "\u6d41\u5f0f\u4e2d" if state.get("isStreaming") else "\u7a7a\u95f2"
        return f"{streaming} \u00b7 \u6a21\u578b {model or 'unknown'} \u00b7 \u601d\u8003 {thinking} \u00b7 \u6d88\u606f {messages} \u00b7 \u5f85\u5904\u7406 {pending} \u00b7 {session_name}"

    def apply_rpc_state(self, response, announce=True):
        state = response.get("data") if isinstance(response, dict) else response
        self.rpc_state = state if isinstance(state, dict) else {}
        if isinstance(state, dict):
            session_id = state.get("sessionId")
            session_file = state.get("sessionFile")
            if isinstance(session_id, str) and session_id:
                self.current_session_id = session_id
            if isinstance(session_file, str) and session_file:
                self.current_session_path = Path(session_file)
        self.update_status_labels()
        if announce:
            # Status summary is a transient toast now, not a transcript line.
            self.flash_status(self.summarize_rpc_state(state))

    def apply_rpc_stats(self, response):
        stats = response.get("data") if isinstance(response, dict) else response
        self.rpc_stats = stats if isinstance(stats, dict) else {}
        if isinstance(stats, dict):
            session_id = stats.get("sessionId")
            session_file = stats.get("sessionFile")
            if isinstance(session_id, str) and session_id:
                self.current_session_id = session_id
            if isinstance(session_file, str) and session_file:
                self.current_session_path = Path(session_file)
        self.update_status_labels()

    def queue_rpc_stats(self, rpc, report_error=False):
        try:
            stats = rpc.send({"type": "get_session_stats"}, timeout=12)
            self.message_queue.put(("rpc_stats", stats, None))
        except Exception as exc:
            if report_error:
                self.message_queue.put(("flash", f"上下文统计刷新失败：{exc}", None))

    def apply_rpc_messages(self, response):
        data = response.get("data", {}) if isinstance(response, dict) else {}
        messages = data.get("messages", []) if isinstance(data, dict) else []
        if not isinstance(messages, list):
            return
        latest_agent = ""
        for message in messages:
            if not isinstance(message, dict):
                continue
            if message.get("role") == "assistant":
                text = extract_message_text(message)
                if text and not self.is_placeholder_agent_text(text):
                    latest_agent = text
        if latest_agent and latest_agent != self.last_agent_text:
            self.append_message("agent", latest_agent)
        self.refresh_sessions()

    def sync_rpc_messages(self):
        rpc = self.rpc
        if not rpc or not rpc.alive:
            return

        def worker():
            try:
                response = rpc.send({"type": "get_messages"}, timeout=12)
                self.message_queue.put(("rpc_messages", response, None))
                state = rpc.send({"type": "get_state"}, timeout=12)
                self.message_queue.put(("rpc_state_silent", state, None))
                self.queue_rpc_stats(rpc)
            except Exception as exc:
                self.message_queue.put(("flash", f"\u540c\u6b65\u5386\u53f2\u5931\u8d25\uff1a{exc}", None))

        threading.Thread(target=worker, daemon=True).start()

    THINKING_LEVELS = ("minimal", "low", "medium", "high", "xhigh")
    THINKING_LEVEL_LABELS = {
        "minimal": "Minimal · 最快",
        "low": "Low · 低",
        "medium": "Medium · 中",
        "high": "High · 高",
        "xhigh": "XHigh · 超高",
    }

    def current_thinking_level(self):
        state = self.rpc_state if isinstance(self.rpc_state, dict) else {}
        return str(state.get("thinkingLevel") or "").strip()

    def on_model_chip_clicked(self):
        # Shift+click keeps the old "refresh status" shortcut; a plain click
        # opens a direct reasoning-effort picker.
        mods = QApplication.keyboardModifiers()
        if mods & Qt.KeyboardModifier.ShiftModifier:
            self.refresh_rpc_state(announce_start=True)
        else:
            self.show_thinking_level_menu()

    def show_thinking_level_menu(self):
        if self.pi_running:
            self.flash_status("任务运行中，稍后再切换思考强度")
            return
        current = self.current_thinking_level()
        menu = QMenu(self)
        menu.setObjectName("thinkingLevelMenu")
        menu.setStyleSheet(
            "QMenu#thinkingLevelMenu{background:#191b21; color:#d4d7de;"
            " border:1px solid #2c3039; border-radius:10px; padding:6px;}"
            "QMenu#thinkingLevelMenu::item{padding:7px 26px 7px 12px; border-radius:7px;}"
            "QMenu#thinkingLevelMenu::item:selected{background:rgba(80,130,255,46); color:#ffffff;}"
            "QMenu#thinkingLevelMenu::indicator{width:14px; height:14px;}"
        )

        for level in self.THINKING_LEVELS:
            label = self.THINKING_LEVEL_LABELS.get(level, level)
            if level == current:
                label = f"{label}  ✓"
            action = QAction(label, menu)
            action.setCheckable(True)
            action.setChecked(level == current)
            action.triggered.connect(lambda _checked=False, target=level: self.set_thinking_level(target))
            menu.addAction(action)

        menu.addSeparator()
        refresh_action = QAction("刷新状态", menu)
        refresh_action.triggered.connect(lambda _checked=False: self.refresh_rpc_state(announce_start=True))
        menu.addAction(refresh_action)

        chip = getattr(self, "model_chip", None)
        if chip is None:
            menu.exec(self.mapToGlobal(self.rect().center()))
            return
        menu.exec(chip.mapToGlobal(chip.rect().bottomLeft()))

    def set_thinking_level(self, level):
        level = str(level or "").strip()
        if level not in self.THINKING_LEVELS:
            return
        if level == self.current_thinking_level():
            return
        if self.pi_running:
            self.flash_status("任务运行中，稍后再切换思考强度")
            return
        self.flash_status(f"正在切换思考强度：{level}…")

        def worker():
            try:
                rpc = self.ensure_rpc_process()
                rpc.send({"type": "set_thinking_level", "level": level}, timeout=12)
                state = rpc.send({"type": "get_state"}, timeout=12)
                self.message_queue.put(("rpc_state_silent", state, None))
                self.queue_rpc_stats(rpc)
            except Exception as exc:
                self.message_queue.put(("message", "system", f"切换思考强度失败：{exc}"))

        threading.Thread(target=worker, daemon=True).start()

    def refresh_rpc_state(self, announce_start=True):
        if self.pi_running:
            self.flash_status("\u4efb\u52a1\u8fd0\u884c\u4e2d\uff0c\u7a0d\u540e\u518d\u5237\u65b0\u72b6\u6001")
            return
        if announce_start:
            self.set_activity("\u6b63\u5728\u5237\u65b0\u72b6\u6001\u2026")

        def worker():
            try:
                rpc = self.ensure_rpc_process()
                response = rpc.send({"type": "get_state"}, timeout=12)
                self.message_queue.put(("rpc_state", response, None))
                self.queue_rpc_stats(rpc, report_error=True)
            except Exception as exc:
                self.message_queue.put(("message", "system", f"\u72b6\u6001\u5237\u65b0\u5931\u8d25\uff1a{exc}"))
            finally:
                self.message_queue.put(("activity", "", None))

        threading.Thread(target=worker, daemon=True).start()

    def reconnect_rpc(self):
        if self.pi_running:
            self.flash_status("\u4efb\u52a1\u8fd0\u884c\u4e2d\uff0c\u5148\u505c\u6b62\u518d\u91cd\u8fde")
            return
        self.flash_status("\u6b63\u5728\u91cd\u8fde\u2026")
        self.stop_rpc()
        self.rpc_state = {}
        self.rpc_stats = {}
        self.update_status_labels()
        self.refresh_rpc_state(announce_start=False)

    def toggle_keep_rpc_on_close(self):
        self.keep_rpc_on_close = self.keep_rpc_btn.isChecked()
        self.save_state()
        state = "\u4fdd\u7559" if self.keep_rpc_on_close else "\u5173\u95ed"
        self.flash_status(f"\u5173\u95ed\u9762\u677f\u65f6\u5c06{state} RPC \u8fde\u63a5")

    def send_prompt(self):
        prompt = self.prompt_input.toPlainText().strip()
        if not prompt:
            return
        if self.handle_local_command(prompt):
            return
        if self.pi_running:
            self.send_follow_up_prompt(prompt)
            return
        self.prompt_input.clear()
        self.last_prompt = prompt
        self.record_prompt_history(prompt)
        self.append_message("user", self.prompt_display_text(prompt))
        self.set_activity("\u6b63\u5728\u8fde\u63a5 Codex\u2026")
        self.run_pi_prompt(prompt)

    def update_prompt_height(self):
        if not hasattr(self, "prompt_input"):
            return
        document_height = int(self.prompt_input.document().size().height()) + 18
        height = int(clamp(document_height, 44, 112))
        self.prompt_input.setFixedHeight(height)
        container = getattr(self, "input_container", None)
        if container is not None:
            container.setFixedHeight(int(clamp(height + 62, 106, 180)))

    def prompt_display_text(self, prompt):
        if "\n" not in prompt:
            return prompt
        if "```" in prompt:
            return prompt
        lines = prompt.splitlines()
        if len(lines) >= 6 or len(prompt) > 900:
            return "```text\n" + prompt.replace("```", "'''") + "\n```"
        return prompt

    def handle_local_command(self, prompt):
        if not prompt.startswith("/"):
            return False
        command, _, arg = prompt.partition(" ")
        command = command.lower().strip()
        arg = arg.strip()
        if command in {"/status", "/state"}:
            self.prompt_input.clear()
            self.refresh_rpc_state(announce_start=True)
            return True
        if command in {"/new", "/clear-session"}:
            self.prompt_input.clear()
            self.new_session()
            return True
        if command == "/clear":
            self.prompt_input.clear()
            self.clear_display()
            return True
        if command == "/name":
            if not arg:
                self.flash_status("\u7528\u6cd5\uff1a/name \u4f1a\u8bdd\u540d")
                return True
            self.prompt_input.clear()
            self.rename_current_session(arg)
            return True
        if command == "/compact":
            self.prompt_input.clear()
            self.compact_current_session(arg)
            return True
        if command == "/model":
            self.prompt_input.clear()
            self.refresh_rpc_state(announce_start=True)
            return True
        if command == "/diff":
            self.prompt_input.clear()
            self.show_git_diff()
            return True
        if command in {"/help", "/?"}:
            self.prompt_input.clear()
            self.append_message(
                "system",
                "\u53ef\u7528\u547d\u4ee4\uff1a/new \u65b0\u5efa\u4f1a\u8bdd \u00b7 /clear \u6e05\u7a7a\u663e\u793a \u00b7 /status \u67e5\u770b\u72b6\u6001 \u00b7 /model \u67e5\u770b\u6a21\u578b \u00b7 /diff \u67e5\u770b\u6539\u52a8 \u00b7 /name \u4f1a\u8bdd\u540d \u00b7 /compact [\u8bf4\u660e] \u00b7 /help \u5e2e\u52a9",
            )
            return True
        self.flash_status(f"\u672a\u77e5\u547d\u4ee4\uff1a{command}")
        return True

    def compact_current_session(self, instructions=""):
        if self.pi_running:
            self.flash_status("\u4efb\u52a1\u8fd0\u884c\u4e2d\uff0c\u5b8c\u6210\u540e\u518d\u538b\u7f29\u4e0a\u4e0b\u6587")
            return
        self.set_activity("\u6b63\u5728\u538b\u7f29\u4e0a\u4e0b\u6587\u2026")

        def worker():
            try:
                rpc = self.ensure_rpc_process()
                payload = {"type": "compact"}
                if instructions:
                    payload["customInstructions"] = instructions
                rpc.send(payload, timeout=20)
                state = rpc.send({"type": "get_state"}, timeout=12)
                self.message_queue.put(("flash", "\u4e0a\u4e0b\u6587\u538b\u7f29\u5df2\u63d0\u4ea4", None))
                self.message_queue.put(("rpc_state_silent", state, None))
                self.queue_rpc_stats(rpc)
            except Exception as exc:
                self.message_queue.put(("message", "system", f"\u538b\u7f29\u5931\u8d25\uff1a{exc}"))
            finally:
                self.message_queue.put(("activity", "", None))

        threading.Thread(target=worker, daemon=True).start()

    def show_git_diff(self):
        if getattr(self, "_diff_running", False):
            self.flash_status("\u6b63\u5728\u8bfb\u53d6\u6539\u52a8\u2026")
            return
        self._diff_running = True
        self.set_activity("\u6b63\u5728\u8bfb\u53d6 git \u6539\u52a8\u2026")

        def worker():
            try:
                def run(args):
                    proc = subprocess.run(
                        args, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        text=True, encoding="utf-8", errors="replace",
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                    return proc.returncode, (proc.stdout or ""), (proc.stderr or "")

                rc_u, unstaged, err_u = run(["git", "diff"])
                rc_s, staged, err_s = run(["git", "diff", "--cached"])
                if rc_u != 0 and rc_s != 0:
                    msg = (err_u or err_s or "").strip() or "\u4e0d\u662f git \u4ed3\u5e93"
                    self.message_queue.put(("flash", f"git \u4e0d\u53ef\u7528\uff1a{msg}", 3200))
                    return
                sections = []

                def fence(title, body):
                    body = body.strip("\n")
                    if len(body) > 7000:
                        body = body[:7000] + "\n\u2026(\u5df2\u622a\u65ad)"
                    sections.append(f"{title}\n```diff\n{body}\n```")

                if staged.strip():
                    fence("# \u5df2\u6682\u5b58\uff08staged\uff09", staged)
                if unstaged.strip():
                    fence("# \u672a\u6682\u5b58\uff08unstaged\uff09", unstaged)
                if not sections:
                    _, status, _ = run(["git", "status", "--short"])
                    if status.strip():
                        self.message_queue.put(("message", "local_output", "# git status\n```\n" + status.strip() + "\n```"))
                    else:
                        self.message_queue.put(("flash", "\u5de5\u4f5c\u533a\u6ca1\u6709\u6539\u52a8", None))
                    return
                self.message_queue.put(("message", "local_output", "\n\n".join(sections)))
            except FileNotFoundError:
                self.message_queue.put(("flash", "\u672a\u627e\u5230 git", 3200))
            except Exception as exc:
                self.message_queue.put(("message", "system", f"git diff \u5931\u8d25\uff1a{exc}"))
            finally:
                self._diff_running = False
                self.message_queue.put(("activity", "", None))

        threading.Thread(target=worker, daemon=True).start()

    def send_follow_up_prompt(self, prompt):
        if self.is_print_process_active():
            self.flash_status("\u6b63\u5728\u8fd0\u884c fallback pi -p\uff0c\u4e0d\u80fd\u8ffd\u52a0")
            return
        rpc = self.rpc
        if not rpc or not rpc.alive:
            self.flash_status("RPC \u8fd8\u5728\u8fde\u63a5\uff0c\u7a0d\u540e\u518d\u53d1\u9001\u8ffd\u8fdb")
            return
        self.prompt_input.clear()
        self.last_prompt = prompt
        self.record_prompt_history(prompt)
        self.append_message("user", self.prompt_display_text(prompt))
        self.flash_status("\u5df2\u4f5c\u4e3a follow-up \u53d1\u9001")

        def worker():
            try:
                rpc.send({"type": "follow_up", "message": prompt}, timeout=12)
            except Exception as exc:
                self.message_queue.put(("message", "system", f"follow-up \u53d1\u9001\u5931\u8d25\uff1a{exc}"))

        threading.Thread(target=worker, daemon=True).start()

    def run_pi_prompt(self, prompt):
        self.pi_running = True
        self.rpc_pending_prompt = True
        self.active_agent_index = None
        self.active_reasoning_index = None
        self.reset_run_diagnostics()
        # Start a fresh tool card for this run.
        self.active_tool_group_index = None
        self.tool_step_indices = {}
        self.begin_run_timing()
        self.send_btn.setEnabled(True)
        self.send_btn.setText("\u2191")
        self.prompt_input.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.update_status_labels()

        def worker():
            try:
                if not self.rpc_enabled:
                    raise RuntimeError("RPC \u5df2\u964d\u7ea7")
                if self.rpc is None or not self.rpc.alive:
                    self.rpc = PiRpcProcess(self.current_session_id, self.current_session_path, self.message_queue)
                self.rpc.send({"type": "prompt", "message": prompt}, timeout=45)
                # Task accepted: no transcript line, the spinner already conveys it.
            except Exception as exc:
                self.message_queue.put(("flash", f"RPC \u4e0d\u53ef\u7528\uff0c\u964d\u7ea7\u5230 pi -p\uff1a{exc}", 4200))
                self.run_pi_print(prompt, from_fallback=True)

        threading.Thread(target=worker, daemon=True).start()

    def is_print_process_active(self):
        return self.print_process is not None and self.print_process.poll() is None

    def run_pi_print(self, prompt, from_fallback=False):
        def worker():
            try:
                proxy_url = detect_agent_proxy()
                PI_DATA_DIR.mkdir(parents=True, exist_ok=True)
                env = build_agent_env(proxy_url)
                command = [resolve_pi_command(env), "--session-id", self.current_session_id, "-p", prompt]
                self.message_queue.put(("status", proxy_url, env))
                self.message_queue.put(("print_started", None, None))
                self.print_stop_requested = False
                process = subprocess.Popen(
                    command,
                    cwd=str(ROOT),
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                self.print_process = process
                stdout, stderr = process.communicate()
                stdout = (stdout or "").strip()
                stderr = (stderr or "").strip()
                stopped = self.print_stop_requested
                if stopped:
                    self.message_queue.put(("flash", "pi -p \u5df2\u505c\u6b62", None))
                elif stdout:
                    self.message_queue.put(("message", "agent", stdout))
                elif process.returncode == 0:
                    self.message_queue.put(("flash", "pi \u6ca1\u6709\u8fd4\u56de\u6587\u672c\u8f93\u51fa", None))
                if stderr and not stopped:
                    self.message_queue.put(("rpc_stderr", stderr, None))
                    self.message_queue.put(("message", "system", stderr))
                if process.returncode != 0 and not stopped:
                    exit_text = f"pi \u9000\u51fa\u7801\uff1a{process.returncode}"
                    self.message_queue.put(("rpc_stderr", exit_text, None))
                    self.message_queue.put(("message", "system", exit_text))
            except FileNotFoundError as exc:
                self.message_queue.put(("message", "system", f"pi \u672a\u627e\u5230\uff1a{exc}"))
            except OSError as exc:
                self.message_queue.put(("message", "system", f"pi \u6267\u884c\u5931\u8d25\uff1a{exc}"))
            finally:
                self.print_process = None
                self.print_stop_requested = False
                self.message_queue.put(("refresh_sessions", None, None))
                self.message_queue.put(("done", None, None))

        if from_fallback:
            worker()
        else:
            self.pi_running = True
            self.reset_run_diagnostics()
            self.send_btn.setEnabled(False)
            self.prompt_input.setEnabled(False)
            self.stop_btn.setEnabled(True)
            threading.Thread(target=worker, daemon=True).start()

    def drain_message_queue(self):
        while True:
            try:
                kind, role, payload = self.message_queue.get_nowait()
            except Empty:
                break
            if kind == "message":
                self.append_message(role, payload)
            elif kind == "activity":
                self.set_activity(role)
            elif kind == "flash":
                self.flash_status(role, payload or 2600)
            elif kind == "status":
                self.update_status_labels(role, payload)
            elif kind == "print_started":
                self.send_btn.setEnabled(False)
                self.send_btn.setText("\u2191")
                self.prompt_input.setEnabled(False)
                self.stop_btn.setEnabled(True)
                self.set_activity("\u6b63\u5728\u8fd0\u884c pi -p\u2026")
            elif kind == "rpc_state":
                self.apply_rpc_state(role)
            elif kind == "rpc_state_silent":
                self.apply_rpc_state(role, announce=False)
            elif kind == "rpc_stats":
                self.apply_rpc_stats(role)
            elif kind == "rpc_messages":
                self.apply_rpc_messages(role)
            elif kind == "rpc_event":
                self.handle_rpc_event(role)
            elif kind == "rpc_stderr":
                self.record_run_diagnostic(role)
            elif kind == "rpc_exit":
                if self.pi_running and not self.is_print_process_active():
                    if payload:
                        self.record_run_diagnostic(f"Pi RPC \u9000\u51fa\uff1a{payload}")
                    self.finish_run()
                elif payload:
                    self.append_message("system", f"Pi RPC \u9000\u51fa\uff1a{payload}")
                self.rpc = None
                self.update_status_labels()
            elif kind == "refresh_sessions":
                self.refresh_sessions()
            elif kind == "done":
                self.finish_run()

    def finish_run(self):
        self.pi_running = False
        self.rpc_pending_prompt = False
        self.active_agent_index = None
        self.active_reasoning_index = None
        self.finish_live_stream(render=False)
        self.set_activity("")
        self.send_btn.setEnabled(True)
        self.send_btn.setText("\u2191")
        self.prompt_input.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.finalize_run_timing()
        self.update_status_labels()
        self.prompt_input.setFocus(Qt.FocusReason.OtherFocusReason)
        self.refresh_sessions()

    def begin_run_timing(self):
        self._run_started_at = time.monotonic()

    def reset_run_diagnostics(self):
        self._run_diagnostic_lines = []
        self._run_had_agent_output = False

    def record_run_diagnostic(self, text):
        lines = []
        for line in str(text or "").splitlines():
            line = line.strip()
            if line:
                lines.append(line)
        if not lines:
            return
        current = list(getattr(self, "_run_diagnostic_lines", []))
        current.extend(lines)
        self._run_diagnostic_lines = current[-80:]
        if self.pi_running:
            self.flash_status("\u8fd0\u884c\u8bca\u65ad\u5df2\u8bb0\u5f55")
        else:
            category = self.classify_diagnostic_category(lines)
            if category in self.FRIENDLY_DIAGNOSTICS:
                title, hint = self.FRIENDLY_DIAGNOSTICS[category]
                self.append_message("system", f"{title}\uff1a{hint}")
            else:
                self.append_message("system", "\n".join(self.dedupe_diagnostic_lines(lines)))

    @staticmethod
    def summarize_diagnostic_lines(lines):
        cleaned = [str(line).strip() for line in lines if str(line).strip()]
        if not cleaned:
            return ""
        last = cleaned[-1]
        count = sum(1 for line in cleaned if line == last)
        return f"{last} \u00d7{count}" if count > 1 else last

    @staticmethod
    def diagnostics_have_error(lines):
        markers = ("\u9519\u8bef", "\u5931\u8d25", "\u5f02\u5e38", "\u8d85\u65f6", "error", "failed", "exception", "timeout")
        probe = "\n".join(str(line) for line in lines).lower()
        return any(marker in probe for marker in markers)

    # Connection/network fingerprints from the Node agent (fetch/undici),
    # proxy, DNS and socket layers. Used to recognize transient failures the
    # way Codex does before deciding whether to surface a hard error.
    NETWORK_ERROR_MARKERS = (
        "fetch failed",
        "econnrefused",
        "econnreset",
        "enotfound",
        "eai_again",
        "etimedout",
        "epipe",
        "socket hang up",
        "network error",
        "networkerror",
        "getaddrinfo",
        "und_err",
        "undici",
        "tunneling socket",
        "proxy",
        "\u4ee3\u7406",
        "\u7f51\u7edc",
        "\u8fde\u63a5\u5931\u8d25",
    )

    FRIENDLY_DIAGNOSTICS = {
        "network": (
            "\u7f51\u7edc\u8fde\u63a5\u5931\u8d25",
            "\u65e0\u6cd5\u8fde\u63a5\u5230\u6a21\u578b\u670d\u52a1\uff08fetch failed\uff09\u3002\u8bf7\u68c0\u67e5\u7f51\u7edc\u6216\u4ee3\u7406\uff08\u5982 VPN / \u4ee3\u7406 PowerShell\uff09\u662f\u5426\u7545\u901a\uff0c\u7136\u540e\u91cd\u8bd5\u3002",
        ),
        "timeout": (
            "\u8bf7\u6c42\u8d85\u65f6",
            "\u6a21\u578b\u670d\u52a1\u54cd\u5e94\u8fc7\u6162\u6216\u7f51\u7edc\u4e0d\u7a33\u5b9a\uff0c\u53ef\u7a0d\u540e\u91cd\u8bd5\u3002",
        ),
        "auth": (
            "\u9274\u6743\u5931\u8d25",
            "API Key \u53ef\u80fd\u65e0\u6548\u6216\u5df2\u8fc7\u671f\uff0c\u8bf7\u68c0\u67e5\u5bc6\u94a5\u914d\u7f6e\u540e\u91cd\u8bd5\u3002",
        ),
        "rate_limit": (
            "\u8bf7\u6c42\u53d7\u9650",
            "\u8bf7\u6c42\u8fc7\u4e8e\u9891\u7e41\u6216\u989d\u5ea6\u4e0d\u8db3\uff08429\uff09\uff0c\u8bf7\u7a0d\u540e\u518d\u8bd5\u3002",
        ),
    }

    @classmethod
    def classify_diagnostic_category(cls, lines):
        probe = "\n".join(str(line) for line in lines).lower()
        if not probe.strip():
            return None
        if any(m in probe for m in ("401", "unauthorized", "invalid api key", "invalid_api_key", "api key", "\u9274\u6743", "\u672a\u6388\u6743")):
            return "auth"
        if any(m in probe for m in ("429", "rate limit", "too many requests", "quota", "\u989d\u5ea6", "\u9891\u7e41")):
            return "rate_limit"
        if any(m in probe for m in cls.NETWORK_ERROR_MARKERS):
            return "network"
        if any(m in probe for m in ("timeout", "timed out", "\u8d85\u65f6")):
            return "timeout"
        return None

    @staticmethod
    def dedupe_diagnostic_lines(lines):
        counts = {}
        order = []
        for line in lines:
            text = str(line).strip()
            if not text:
                continue
            if text not in counts:
                counts[text] = 0
                order.append(text)
            counts[text] += 1
        return [f"{text}  \u00d7{counts[text]}" if counts[text] > 1 else text for text in order]

    def attach_run_diagnostics(self, group):
        lines = list(getattr(self, "_run_diagnostic_lines", []))
        if not lines:
            return
        deduped = self.dedupe_diagnostic_lines(lines)
        raw_block = "```text\n" + "\n".join(deduped) + "\n```"
        category = self.classify_diagnostic_category(lines)
        had_output = bool(getattr(self, "_run_had_agent_output", False))

        # Codex-style triage: a network/timeout hiccup the agent already
        # recovered from (a reply still arrived) is demoted to a quiet
        # "auto-retried" note instead of flagging the whole run as failed.
        if had_output and category in {"network", "timeout"}:
            step = {
                "key": "__runtime_diagnostics__",
                "text": "\u7f51\u7edc\u4e00\u5ea6\u4e2d\u65ad\uff0c\u5df2\u81ea\u52a8\u91cd\u8bd5\u5e76\u5b8c\u6210\u3002\n\n" + raw_block,
                "tool_name": "\u7f51\u7edc\u72b6\u6001",
                "tool_status": "\u5df2\u81ea\u52a8\u91cd\u8bd5",
                "is_error": False,
                "summary": "\u7f51\u7edc\u4e00\u5ea6\u4e2d\u65ad\uff0c\u5df2\u81ea\u52a8\u6062\u590d",
                "collapsed": True,
            }
        elif category in self.FRIENDLY_DIAGNOSTICS:
            title, hint = self.FRIENDLY_DIAGNOSTICS[category]
            step = {
                "key": "__runtime_diagnostics__",
                "text": f"**{title}**\n\n{hint}\n\n" + raw_block,
                "tool_name": "\u8fd0\u884c\u8bca\u65ad",
                "tool_status": "\u9519\u8bef",
                "is_error": True,
                "summary": title,
                "collapsed": False,
            }
        else:
            is_error = self.diagnostics_have_error(lines)
            step = {
                "key": "__runtime_diagnostics__",
                "text": raw_block,
                "tool_name": "\u8fd0\u884c\u8bca\u65ad",
                "tool_status": "\u9519\u8bef" if is_error else "\u8bca\u65ad",
                "is_error": is_error,
                "summary": self.summarize_diagnostic_lines(deduped),
                "collapsed": not is_error,
            }

        steps = group.setdefault("steps", [])
        for existing in steps:
            if existing.get("key") == step["key"]:
                existing.update(step)
                break
        else:
            steps.append(step)
        if step["is_error"]:
            group["collapsed"] = False
        self._run_diagnostic_lines = []

    @staticmethod
    def is_placeholder_agent_text(text):
        stripped = str(text or "").strip()
        if not stripped:
            return True
        return all(ch in ".\u2026" for ch in stripped)

    def upsert_agent_text(self, text):
        if self.is_placeholder_agent_text(text):
            self.set_activity("\u6b63\u5728\u751f\u6210\u56de\u590d\u2026")
            return
        self._run_had_agent_output = True
        if self.active_agent_index is None:
            self.active_agent_index = self.append_message("agent", text)
            self.begin_live_stream(self.active_agent_index, "agent", text)
        else:
            self.update_message(self.active_agent_index, text)

    def finalize_run_timing(self):
        started = getattr(self, "_run_started_at", None)
        if started is None:
            return
        self._run_started_at = None
        elapsed = max(0.0, time.monotonic() - started)
        index = getattr(self, "active_tool_group_index", None)
        if (
            index is not None
            and 0 <= index < len(self.display_messages)
            and self.display_messages[index].get("role") == "tool_group"
        ):
            group = self.display_messages[index]
            group["running"] = False
            group["elapsed"] = elapsed
        else:
            # No tools ran this turn; show a lightweight processed marker.
            group = {
                "role": "tool_group",
                "running": False,
                "collapsed": True,
                "elapsed": elapsed,
                "steps": [],
            }
            self.display_messages.append(group)
        if (
            not getattr(self, "_run_had_agent_output", False)
            and not getattr(self, "_run_diagnostic_lines", [])
            and not group.get("steps")
        ):
            self._run_diagnostic_lines = [
                "\u672a\u6536\u5230\u6a21\u578b\u56de\u590d\uff1b\u8bf7\u6c42\u53ef\u80fd\u5728\u7f51\u7edc\u6216 API \u5c42\u5931\u8d25\u3002"
            ]
        self.attach_run_diagnostics(group)
        self.active_tool_group_index = None
        self.tool_step_indices = {}
        self.render_messages()
        # queue_update and other low-value events are intentionally ignored.

    def stop_rpc(self):
        rpc = self.rpc
        self.rpc = None
        if rpc:
            rpc.stop()

    def retry_last_prompt(self):
        if self.pi_running or not self.last_prompt:
            return
        self.prompt_input.setPlainText(self.last_prompt)
        self.send_prompt()

    def copy_last_reply(self):
        if not self.last_agent_text:
            self.flash_status("\u8fd8\u6ca1\u6709\u53ef\u590d\u5236\u7684\u56de\u590d")
            return
        QApplication.clipboard().setText(self.last_agent_text)
        self.flash_status("\u5df2\u590d\u5236\u6700\u540e\u4e00\u6761\u56de\u590d")

    def stop_current_task(self):
        if not self.pi_running:
            return
        process = self.print_process
        if process and process.poll() is None:
            self.print_stop_requested = True
            self.set_activity("\u6b63\u5728\u505c\u6b62\u2026")

            def stop_print_worker():
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    try:
                        process.kill()
                    except OSError:
                        pass

            threading.Thread(target=stop_print_worker, daemon=True).start()
            return
        rpc = self.rpc
        if rpc and rpc.alive:
            self.set_activity("\u6b63\u5728\u505c\u6b62\u2026")

            def worker():
                try:
                    rpc.send({"type": "abort"}, timeout=6)
                    state = rpc.send({"type": "get_state"}, timeout=12)
                    self.message_queue.put(("rpc_state_silent", state, None))
                    self.queue_rpc_stats(rpc)
                except Exception as exc:
                    self.message_queue.put(("message", "system", f"\u505c\u6b62\u8bf7\u6c42\u5931\u8d25\uff1a{exc}"))
                finally:
                    self.message_queue.put(("done", None, None))

            threading.Thread(target=worker, daemon=True).start()
        else:
            self.flash_status("\u4efb\u52a1\u6b63\u5728\u6536\u5c3e\uff0c\u7a0d\u7b49\u7247\u523b")

    def open_vpn_terminal(self):
        try:
            proxy_url = launch_agent_terminal(with_proxy=True)
            self.update_status_labels(proxy_url)
            self.flash_status(f"\u5df2\u6253\u5f00 VPN PowerShell\uff1a{proxy_url}")
        except OSError as exc:
            self.append_message("system", f"VPN \u7ec8\u7aef\u6253\u5f00\u5931\u8d25\uff1a{exc}")
            self.pet.say(f"Agent \u7ec8\u7aef\u6253\u5f00\u5931\u8d25\uff1a{exc}", 4.0)

    def open_plain_terminal(self):
        try:
            launch_agent_terminal(with_proxy=False)
            self.flash_status("\u5df2\u6253\u5f00\u666e\u901a PowerShell\uff08\u4e0d\u5e26\u4ee3\u7406\uff09")
        except OSError as exc:
            self.append_message("system", f"\u666e\u901a\u7ec8\u7aef\u6253\u5f00\u5931\u8d25\uff1a{exc}")
            self.pet.say(f"\u666e\u901a\u7ec8\u7aef\u6253\u5f00\u5931\u8d25\uff1a{exc}", 4.0)
