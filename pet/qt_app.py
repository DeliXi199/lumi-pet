import sys
from queue import SimpleQueue

from .model import PetModel
from .qt import QApplication, QTextEdit, QTimer, QUrl, QWidget, pynput_keyboard
from . import single_instance
from .single_instance import acquire_single_instance_lock, release_single_instance_lock
from .ui.pet_window import PetWindow


class AppKeyFilter(QWidget):
    def __init__(self, model):
        super().__init__()
        self.model = model

    def eventFilter(self, obj, event):
        if isinstance(obj, QTextEdit):
            return False
        if event.type().name in {"KeyPress", "ShortcutOverride"}:
            self.model.notify_typing()
        return False


def run_qt(self_test=False, smoke_test=False, agent_panel_smoke=False):
    if not self_test and not smoke_test and not agent_panel_smoke:
        if not acquire_single_instance_lock():
            print("pet already running")
            return 0
    app = QApplication(sys.argv)
    if single_instance.SINGLE_INSTANCE_LOCK:
        app.aboutToQuit.connect(release_single_instance_lock)
    model = PetModel()
    key_filter = AppKeyFilter(model)
    app.installEventFilter(key_filter)
    key_queue = SimpleQueue()
    listener = None
    if pynput_keyboard is not None and not self_test:
        listener = pynput_keyboard.Listener(on_press=lambda key: key_queue.put(1))
        listener.start()
        app.aboutToQuit.connect(listener.stop)
    pet = PetWindow(model, key_queue)
    screen = app.primaryScreen().availableGeometry()
    pet.move(screen.right() - pet.width() - 42, screen.bottom() - pet.height() - 48)
    pet.show()
    if smoke_test:
        pet.open_panel()
        pet.open_agent()
        if pet.agent_panel:
            pet.agent_panel.handle_rpc_event(
                {
                    "type": "tool_execution_start",
                    "toolCallId": "smoke-tool",
                    "toolName": "smoke",
                    "args": {"command": "echo ok"},
                }
            )
            pet.agent_panel.handle_rpc_event(
                {
                    "type": "tool_execution_end",
                    "toolCallId": "smoke-tool",
                    "toolName": "smoke",
                    "result": {"content": [{"type": "text", "text": "ok"}]},
                    "isError": False,
                }
            )
        QTimer.singleShot(1000, app.quit)
    if agent_panel_smoke:
        pet.open_agent()
        if pet.agent_panel:
            panel = pet.agent_panel
            panel.append_message("agent", "# AgentPanel smoke\n- **Markdown**\n```text\nok\n```")
            panel.handle_local_command("/help")
            panel.handle_rpc_event(
                {
                    "type": "tool_execution_start",
                    "toolCallId": "panel-smoke-tool",
                    "toolName": "smoke",
                    "args": {"command": "echo ok"},
                }
            )
            panel.handle_rpc_event(
                {
                    "type": "tool_execution_update",
                    "toolCallId": "panel-smoke-tool",
                    "toolName": "smoke",
                    "partialResult": {"content": [{"type": "text", "text": "partial"}]},
                }
            )
            panel.handle_rpc_event(
                {
                    "type": "tool_execution_end",
                    "toolCallId": "panel-smoke-tool",
                    "toolName": "smoke",
                    "result": {"content": [{"type": "text", "text": "ok"}]},
                    "isError": False,
                }
            )
            tool_groups = [item for item in panel.display_messages if item.get("role") == "tool_group"]
            if len(tool_groups) != 1 or len(tool_groups[0].get("steps", [])) != 1:
                raise RuntimeError("tool event merge failed")
            tool_group_index = panel.display_messages.index(tool_groups[0])
            if not tool_groups[0].get("steps", [])[0].get("collapsed"):
                raise RuntimeError("tool step should collapse after completion")
            panel.handle_message_link(QUrl(f"runstep-toggle:{tool_group_index}:0"))
            if tool_groups[0].get("steps", [])[0].get("collapsed"):
                raise RuntimeError("tool step toggle failed")
            old_pinned = panel.state_id_set("pinned_sessions")
            old_archived = panel.state_id_set("archived_sessions")
            key = panel.current_session_key()
            try:
                pinned = set(old_pinned)
                archived = set(old_archived)
                pinned.add(key)
                archived.add(key)
                panel.save_state_id_set("pinned_sessions", pinned)
                panel.save_state_id_set("archived_sessions", archived)
                if key not in panel.state_id_set("pinned_sessions") or key not in panel.state_id_set("archived_sessions"):
                    raise RuntimeError("session state smoke failed")
            finally:
                panel.save_state_id_set("pinned_sessions", old_pinned)
                panel.save_state_id_set("archived_sessions", old_archived)
        QTimer.singleShot(1000, app.quit)
    if self_test:
        for _ in range(6):
            model.update(1 / 30)
        print(f"self-test ok: qt=True moods={len(model.moods)} themes={len(model.themes)}")
        return 0
    return app.exec()


def main():
    sys.exit(
        run_qt(
            "--self-test" in sys.argv,
            "--smoke-test" in sys.argv,
            "--agent-panel-smoke" in sys.argv,
        )
    )
