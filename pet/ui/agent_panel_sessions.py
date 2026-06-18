from pathlib import Path
import threading
import time

from ..agent.sessions import AgentSessionSummary, list_agent_sessions, load_session_messages, make_agent_session_id
from ..qt import (
    QCursor,
    QFontMetrics,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSignalBlocker,
    QSize,
    Qt,
    QTimer,
    QVBoxLayout,
    QWidget,
)


class SessionRowWidget(QWidget):
    """A Codex-style session row: name + time, with hover pin/archive actions.

    Single click selects the session, double click renames it, and hovering the
    row reveals the pin (置顶) and archive (归档) buttons.
    """

    def __init__(self, panel, summary, item, name_text, meta_text, pinned, archived):
        super().__init__()
        self.panel = panel
        self.summary = summary
        self.item = item
        self.setObjectName("sessionRow")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 6, 8, 6)
        outer.setSpacing(6)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        self.name_label = QLabel()
        self.name_label.setObjectName("sessionName")
        prefix = "\U0001f4cc " if pinned else ""
        full_name = prefix + (name_text or "")
        metrics = QFontMetrics(self.name_label.font())
        self.name_label.setText(metrics.elidedText(full_name, Qt.TextElideMode.ElideRight, 186))
        self.name_label.setToolTip(name_text or "")

        self.time_label = QLabel(meta_text or "")
        self.time_label.setObjectName("sessionTime")

        text_col.addWidget(self.name_label)
        text_col.addWidget(self.time_label)
        outer.addLayout(text_col, 1)

        self.pin_btn = QPushButton("\u2605" if pinned else "\u2606")
        self.pin_btn.setObjectName("rowActionButton")
        self.pin_btn.setFixedSize(24, 24)
        self.pin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pin_btn.setToolTip("\u53d6\u6d88\u7f6e\u9876" if pinned else "\u7f6e\u9876")
        self.pin_btn.clicked.connect(self._toggle_pin)

        self.archive_btn = QPushButton("\u21a9" if archived else "\u2913")
        self.archive_btn.setObjectName("rowActionButton")
        self.archive_btn.setFixedSize(24, 24)
        self.archive_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.archive_btn.setToolTip("\u6062\u590d\u5f52\u6863" if archived else "\u5f52\u6863")
        self.archive_btn.clicked.connect(self._toggle_archive)

        outer.addWidget(self.pin_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        outer.addWidget(self.archive_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        self.pin_btn.hide()
        self.archive_btn.hide()

    def _set_actions_visible(self, visible):
        self.pin_btn.setVisible(visible)
        self.archive_btn.setVisible(visible)

    def enterEvent(self, event):
        self._set_actions_visible(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        # Keep the buttons visible while the cursor is still over a child button.
        if not self.rect().contains(self.mapFromGlobal(QCursor.pos())):
            self._set_actions_visible(False)
        super().leaveEvent(event)

    def _toggle_pin(self):
        self.panel.toggle_pin_summary(self.summary)

    def _toggle_archive(self):
        self.panel.toggle_archive_summary(self.summary)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            panel = self.panel
            item = self.item
            panel.session_list.setCurrentItem(item)
            # Defer the (potentially heavy) session switch so we never rebuild
            # the list while still inside this widget's event handler.
            QTimer.singleShot(0, lambda: panel.select_session_item(item))
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            panel = self.panel
            summary = self.summary
            QTimer.singleShot(0, lambda: panel.request_rename_session(summary))
        super().mouseDoubleClickEvent(event)


class AgentPanelSessionsMixin:
    def current_session_summary(self):
        for summary in self.session_summaries:
            if summary.session_id == self.current_session_id:
                return summary
        return None

    def state_id_set(self, key):
        value = self.panel_state.get(key, [])
        if isinstance(value, list):
            return {str(item) for item in value if item}
        return set()

    def save_state_id_set(self, key, values):
        self.panel_state[key] = sorted(str(item) for item in values if item)
        self.save_state()

    def summary_key(self, summary):
        if isinstance(summary, AgentSessionSummary):
            return summary.session_id or str(summary.path or "")
        return self.current_session_id or ""

    def is_summary_pinned(self, summary):
        return self.summary_key(summary) in self.state_id_set("pinned_sessions")

    def is_summary_archived(self, summary):
        return self.summary_key(summary) in self.state_id_set("archived_sessions")

    def current_session_key(self):
        summary = self.current_session_summary()
        return self.summary_key(summary) if summary else self.current_session_id

    def sort_session_summaries(self):
        pinned = self.state_id_set("pinned_sessions")
        self.session_summaries.sort(key=lambda item: (0 if self.summary_key(item) in pinned else 1, -float(item.updated or 0)))

    def session_message_search_text(self, summary):
        if not summary.path or not Path(summary.path).exists():
            return ""
        path = Path(summary.path)
        try:
            stat = path.stat()
        except OSError:
            return ""
        cache_key = (str(path), stat.st_mtime, stat.st_size)
        cached = self.session_search_cache.get(cache_key)
        if cached is not None:
            return cached
        parts = []
        for _role, text in load_session_messages(path):
            if text:
                parts.append(text)
            if sum(len(part) for part in parts) > 12000:
                break
        haystack = "\n".join(parts).lower()
        self.session_search_cache = {cache_key: haystack}
        return haystack

    def update_session_action_buttons(self):
        btn = getattr(self, "show_archived_btn", None)
        if btn is not None:
            btn.setText("\u9690\u85cf\u5f52\u6863" if self.show_archived_sessions else "\u663e\u793a\u5f52\u6863")

    def format_relative_time(self, ts):
        try:
            ts = float(ts or 0)
        except (TypeError, ValueError):
            return ""
        if ts <= 0:
            return ""
        delta = max(0.0, time.time() - ts)
        if delta < 60:
            return "刚刚"
        if delta < 3600:
            return f"{int(delta // 60)} 分"
        if delta < 86400:
            return f"{int(delta // 3600)} 小时"
        if delta < 604800:
            return f"{int(delta // 86400)} 天"
        if delta < 2592000:
            return f"{int(delta // 604800)} 周"
        if delta < 31536000:
            return f"{int(delta // 2592000)} 个月"
        return f"{int(delta // 31536000)} 年"

    def refresh_sessions(self):
        self.session_summaries = list_agent_sessions()
        if not any(item.session_id == self.current_session_id for item in self.session_summaries):
            self.session_summaries.insert(
                0,
                AgentSessionSummary(
                    session_id=self.current_session_id,
                    path=self.current_session_path,
                    name="\u5f53\u524d\u65b0\u4f1a\u8bdd",
                    updated=time.time(),
                    message_count=len([m for m in self.display_messages if m.get("role") in {"user", "agent"}]),
                    preview=self.last_prompt or "\u5c1a\u672a\u4fdd\u5b58",
                ),
            )
        self.sort_session_summaries()
        self.refresh_session_list()
        self.save_state()

    def refresh_session_list(self):
        if not hasattr(self, "session_list"):
            return
        query = ""
        if hasattr(self, "session_search"):
            query = self.session_search.text().strip().lower()
        archived = self.state_id_set("archived_sessions")
        self.loading_sessions = True
        with QSignalBlocker(self.session_list):
            self.session_list.clear()
            selected_row = -1
            for summary in self.session_summaries:
                key = self.summary_key(summary)
                is_current = summary.session_id == self.current_session_id
                if key in archived and not self.show_archived_sessions and not is_current:
                    continue
                haystack = " ".join(
                    [
                        summary.session_id,
                        summary.name,
                        summary.preview,
                        summary.label,
                        str(summary.path or ""),
                    ]
                ).lower()
                if query and query not in haystack and query not in self.session_message_search_text(summary):
                    continue
                pinned = self.is_summary_pinned(summary)
                is_archived = key in archived
                name_text = summary.name or summary.preview or summary.session_id or "(\u7a7a\u4f1a\u8bdd)"
                name_text = " ".join(str(name_text).split())
                badges = []
                if is_archived:
                    badges.append("\u5f52\u6863")
                rel = self.format_relative_time(summary.updated)
                if rel:
                    badges.append(rel)
                meta_text = " \u00b7 ".join(badges)
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, summary)
                if summary.path:
                    item.setToolTip(str(summary.path))
                self.session_list.addItem(item)
                row = SessionRowWidget(self, summary, item, name_text, meta_text, pinned, is_archived)
                item.setSizeHint(QSize(0, 48))
                self.session_list.setItemWidget(item, row)
                if is_current:
                    selected_row = self.session_list.count() - 1
            if selected_row >= 0:
                self.session_list.setCurrentRow(selected_row)
        self.loading_sessions = False
        self.update_session_action_buttons()

    def show_session_context_menu(self, pos):
        item = self.session_list.itemAt(pos)
        if item is None:
            return
        summary = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(summary, AgentSessionSummary):
            return
        menu = QMenu(self)
        act_rename = menu.addAction("\u91cd\u547d\u540d")
        pinned = self.is_summary_pinned(summary)
        act_pin = menu.addAction("\u53d6\u6d88\u7f6e\u9876" if pinned else "\u7f6e\u9876")
        archived = self.is_summary_archived(summary)
        act_archive = menu.addAction("\u6062\u590d\u5f52\u6863" if archived else "\u5f52\u6863")
        menu.addSeparator()
        act_delete = menu.addAction("\u5220\u9664")
        chosen = menu.exec(self.session_list.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen == act_rename:
            self.request_rename_session(summary)
        elif chosen == act_pin:
            self.toggle_pin_summary(summary)
        elif chosen == act_archive:
            self.toggle_archive_summary(summary)
        elif chosen == act_delete:
            self.delete_session_summary(summary)

    def select_session_item(self, item):
        if self.loading_sessions or item is None:
            return
        summary = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(summary, AgentSessionSummary):
            return
        if summary.session_id == self.current_session_id and summary.path == self.current_session_path:
            return
        self.switch_session(summary)

    def switch_session(self, summary):
        if self.pi_running:
            self.stop_current_task()
        self.stop_rpc()
        self.current_session_id = summary.session_id
        self.current_session_path = summary.path
        self.active_agent_index = None
        self.rpc_state = {}
        self.rpc_stats = {}
        self.tool_message_indices = {}
        self.active_tool_group_index = None
        self.tool_step_indices = {}
        self.last_prompt = ""
        self.reset_live_stream_state()
        self.reset_run_diagnostics()
        self.load_current_session_history()
        self.refresh_sessions()
        QTimer.singleShot(120, lambda: self.refresh_rpc_state(announce_start=False))

    def load_current_session_history(self):
        self.display_messages = []
        self.tool_message_indices = {}
        self.active_tool_group_index = None
        self.tool_step_indices = {}
        self.last_agent_text = ""
        self.reset_live_stream_state()
        self.reset_run_diagnostics()
        if self.current_session_path and Path(self.current_session_path).exists():
            for role, text in load_session_messages(self.current_session_path):
                self.display_messages.append({"role": role, "text": text})
                if role == "agent":
                    self.last_agent_text = text
        # An empty list simply renders the Codex-style empty state.
        self.render_messages()

    def new_session(self):
        if self.pi_running:
            self.stop_current_task()
        self.stop_rpc()
        self.current_session_id = make_agent_session_id()
        self.current_session_path = None
        self.last_prompt = ""
        self.last_agent_text = ""
        self.active_agent_index = None
        self.rpc_state = {}
        self.rpc_stats = {}
        self.tool_message_indices = {}
        self.active_tool_group_index = None
        self.tool_step_indices = {}
        self.reset_live_stream_state()
        self.reset_run_diagnostics()
        self.display_messages = []
        self.render_messages()
        self.flash_status("\u5df2\u65b0\u5efa\u4f1a\u8bdd")
        self.refresh_sessions()
        self.prompt_input.setFocus(Qt.FocusReason.OtherFocusReason)
        QTimer.singleShot(120, lambda: self.refresh_rpc_state(announce_start=False))

    def request_rename_session(self, summary):
        if not isinstance(summary, AgentSessionSummary):
            return
        if summary.session_id != self.current_session_id:
            self.switch_session(summary)
        self.rename_current_session()

    def rename_current_session(self, requested_name=None):
        if self.pi_running:
            self.flash_status("Pi \u8fd0\u884c\u4e2d\uff0c\u7a0d\u540e\u91cd\u547d\u540d")
            return
        if requested_name is None:
            summary = self.current_session_summary()
            current_name = ""
            if summary:
                current_name = summary.name or summary.preview or ""
            name, accepted = QInputDialog.getText(
                self,
                "\u91cd\u547d\u540d\u4f1a\u8bdd",
                "\u4f1a\u8bdd\u540d\uff1a",
                QLineEdit.EchoMode.Normal,
                current_name[:80],
            )
            name = name.strip()
            if not accepted or not name:
                return
        else:
            name = str(requested_name).strip()
            if not name:
                self.flash_status("\u4f1a\u8bdd\u540d\u4e0d\u80fd\u4e3a\u7a7a")
                return
        self.set_activity("\u91cd\u547d\u540d\u4e2d\u2026")

        def worker():
            try:
                rpc = self.ensure_rpc_process()
                rpc.send({"type": "set_session_name", "name": name}, timeout=12)
                state = rpc.send({"type": "get_state"}, timeout=12)
                self.message_queue.put(("flash", f"\u5df2\u91cd\u547d\u540d\uff1a{name}", None))
                self.message_queue.put(("rpc_state_silent", state, None))
                self.message_queue.put(("refresh_sessions", None, None))
            except Exception as exc:
                self.message_queue.put(("message", "system", f"\u91cd\u547d\u540d\u5931\u8d25\uff1a{exc}"))
            finally:
                self.message_queue.put(("activity", "", None))

        threading.Thread(target=worker, daemon=True).start()

    def toggle_pin_summary(self, summary):
        if not isinstance(summary, AgentSessionSummary):
            return
        key = self.summary_key(summary)
        pinned = self.state_id_set("pinned_sessions")
        if key in pinned:
            pinned.remove(key)
            self.flash_status("\u5df2\u53d6\u6d88\u7f6e\u9876")
        else:
            pinned.add(key)
            self.flash_status("\u5df2\u7f6e\u9876\u4f1a\u8bdd")
        self.save_state_id_set("pinned_sessions", pinned)
        # Defer the rebuild so we never destroy the row button mid-click.
        QTimer.singleShot(0, self.refresh_sessions)

    def toggle_archive_summary(self, summary):
        if not isinstance(summary, AgentSessionSummary):
            return
        key = self.summary_key(summary)
        archived = self.state_id_set("archived_sessions")
        if key in archived:
            archived.remove(key)
            self.flash_status("\u5df2\u6062\u590d\u4f1a\u8bdd")
        else:
            archived.add(key)
            self.flash_status("\u5df2\u5f52\u6863\u4f1a\u8bdd")
        self.save_state_id_set("archived_sessions", archived)
        QTimer.singleShot(0, self.refresh_sessions)

    def toggle_pin_current_session(self):
        self.toggle_pin_summary(self.current_session_summary())

    def toggle_archive_current_session(self):
        self.toggle_archive_summary(self.current_session_summary())

    def toggle_show_archived_sessions(self):
        self.show_archived_sessions = self.show_archived_btn.isChecked()
        self.save_state()
        self.update_session_action_buttons()
        self.refresh_session_list()

    def delete_session_summary(self, summary):
        if self.pi_running:
            self.flash_status("\u8bf7\u5148\u505c\u6b62\u4efb\u52a1\u518d\u5220\u9664")
            return
        if not isinstance(summary, AgentSessionSummary) or not summary.path or not Path(summary.path).exists():
            self.flash_status("\u8be5\u4f1a\u8bdd\u6ca1\u6709\u53ef\u5220\u9664\u7684\u5386\u53f2")
            return
        reply = QMessageBox.question(
            self,
            "\u5f7b\u5e95\u5220\u9664\u4f1a\u8bdd",
            f"\u8fd9\u4e2a\u64cd\u4f5c\u4f1a\u5220\u9664\u5386\u53f2\u6587\u4ef6\uff0c\u65e0\u6cd5\u6062\u590d\u3002\n\n\u786e\u5b9a\u5f7b\u5e95\u5220\u9664\uff1f\n{summary.label}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        is_current = summary.session_id == self.current_session_id
        try:
            if is_current:
                self.stop_rpc()
            Path(summary.path).unlink()
        except OSError as exc:
            self.append_message("system", f"\u5220\u9664\u5931\u8d25\uff1a{exc}")
            return
        for key_name in ("pinned_sessions", "archived_sessions"):
            ids = self.state_id_set(key_name)
            ids.discard(self.summary_key(summary))
            self.save_state_id_set(key_name, ids)
        if is_current:
            self.current_session_id = make_agent_session_id()
            self.current_session_path = None
            self.rpc_state = {}
            self.rpc_stats = {}
            self.last_prompt = ""
            self.last_agent_text = ""
            self.active_agent_index = None
            self.tool_message_indices = {}
            self.active_tool_group_index = None
            self.tool_step_indices = {}
            self.reset_live_stream_state()
            self.reset_run_diagnostics()
            self.display_messages = []
            self.render_messages()
        self.flash_status("\u5df2\u5220\u9664\u4f1a\u8bdd")
        QTimer.singleShot(0, self.refresh_sessions)

    def delete_current_session(self):
        self.delete_session_summary(self.current_session_summary())

    def clear_display(self):
        self.display_messages = []
        self.active_agent_index = None
        self.tool_message_indices = {}
        self.active_tool_group_index = None
        self.tool_step_indices = {}
        self.reset_live_stream_state()
        self.reset_run_diagnostics()
        self.render_messages()
        self.flash_status("\u5df2\u6e05\u7a7a\u663e\u793a\uff0c\u5386\u53f2\u6587\u4ef6\u672a\u5220\u9664")
