from __future__ import annotations

import time
from queue import SimpleQueue

from ..agent.panel_state import load_agent_panel_state, save_agent_panel_state
from ..agent.sessions import find_session_summary, make_agent_session_id
from ..model import PetModel
from ..qt import (
    QAction,
    QApplication,
    QComboBox,
    QDialog,
    QFont,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QPoint,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QTextEdit,
    QTimer,
    QVBoxLayout,
    QWidget,
    Qt,
)
from ..utils import clamp, color_mix
from .agent_panel_events import AgentPanelEventsMixin
from .agent_panel_render import AgentPanelRenderMixin
from .agent_panel_rpc import AgentPanelRpcMixin
from .agent_panel_sessions import AgentPanelSessionsMixin
from .buttons import AgentSendButton, WindowControlButton

# Codex-style minimal busy spinner.
SPINNER_FRAMES = ("\u280b", "\u2819", "\u2839", "\u2838", "\u283c", "\u2834", "\u2826", "\u2827", "\u2807", "\u280f")

# Spinner refresh cadence in ms - fast enough to look smooth like Codex.
ACTIVITY_TICK_MS = 90

# Slash commands offered in the autocomplete popup (Codex-like).
SLASH_COMMANDS = (
    ("/new", "\u65b0\u5efa\u4f1a\u8bdd"),
    ("/clear", "\u6e05\u7a7a\u5f53\u524d\u663e\u793a"),
    ("/status", "\u67e5\u770b\u8fde\u63a5\u4e0e\u72b6\u6001"),
    ("/model", "\u67e5\u770b\u5f53\u524d\u6a21\u578b"),
    ("/diff", "\u67e5\u770b\u5de5\u4f5c\u533a git \u6539\u52a8"),
    ("/name", "\u91cd\u547d\u540d\u5f53\u524d\u4f1a\u8bdd"),
    ("/compact", "\u538b\u7f29\u4e0a\u4e0b\u6587"),
    ("/help", "\u67e5\u770b\u5168\u90e8\u547d\u4ee4"),
)
# No-argument commands that can run immediately when chosen.
SLASH_NO_ARG = {"/new", "/clear", "/status", "/model", "/diff", "/help"}
_SLASH_POPUP_QSS = (
    "QListWidget#slashPopup{background:#191b21; color:#d4d7de;"
    " border:1px solid #2c3039; border-radius:10px; padding:4px; outline:0; font-size:13px;}"
    "QListWidget#slashPopup::item{padding:5px 10px; border-radius:6px;}"
    "QListWidget#slashPopup::item:selected{background:rgba(80,130,255,46); color:#ffffff;}"
)

# Inline styles for the Codex-like input toolbar (kept out of the themed QSS).
_SEND_CIRCLE_QSS = (
    "QPushButton#sendButton{background:#3d7dff; color:#ffffff; border:none;"
    " border-radius:17px; font-size:17px; font-weight:700; padding:0;}"
    "QPushButton#sendButton:hover{background:#5790ff;}"
    "QPushButton#sendButton:disabled{background:rgba(61,125,255,110); color:rgba(255,255,255,150);}"
)
_INPUT_TOOL_QSS = (
    "QPushButton#inputToolButton{background:transparent; color:#9aa0aa; border:none;"
    " border-radius:15px; font-size:15px; padding:0;}"
    "QPushButton#inputToolButton:hover{background:rgba(255,255,255,20); color:#d4d7de;}"
)
_MODEL_CHIP_QSS = (
    "QPushButton#modelChip{background:rgba(255,255,255,16); color:#aeb4be; border:none;"
    " border-radius:13px; padding:4px 12px; font-size:12px;}"
    "QPushButton#modelChip:hover{background:rgba(255,255,255,28); color:#e4e6eb;}"
)
AGENT_UI_FONT = "Segoe UI"
AGENT_TEXT_FONT = "Segoe UI"


def tune_agent_font(font):
    try:
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    except Exception:
        pass
    return font


class AgentPanel(AgentPanelEventsMixin, AgentPanelRpcMixin, AgentPanelSessionsMixin, AgentPanelRenderMixin, QDialog):
    def __init__(self, model: PetModel, pet: "PetWindow"):
        super().__init__(pet)
        self.model = model
        self.pet = pet
        self.dragging_panel = False
        self.drag_start = QPoint()
        self.drag_origin = QPoint()
        self.styled_theme = None
        self.last_status_update = 0.0
        self.pi_running = False
        self.rpc_enabled = True
        self.rpc = None
        self.rpc_state = {}
        self.rpc_stats = {}
        self.rpc_pending_prompt = False
        self.print_process = None
        self.print_stop_requested = False
        self.active_agent_index = None
        self.font_scale = 1.1
        self._base_message_pt = None
        self.last_prompt = ""
        self.last_agent_text = ""
        # Prompt history (Codex-like \u2191/\u2193 recall).
        self.prompt_history = []
        self._history_index = None
        # Active streaming reasoning ("thinking") block, if the agent emits one.
        self.active_reasoning_index = None
        # Transcript view hides thinking/tool noise, leaving only the dialogue.
        self.transcript_mode = False
        self._slash_matches = []
        self._diff_running = False
        self.display_messages = []
        self.tool_message_indices = {}
        # Live tool calls of the current run are grouped into a single card.
        self.active_tool_group_index = None
        self.tool_step_indices = {}
        self._run_diagnostic_lines = []
        self._run_had_agent_output = False
        # Coalesced rendering: avoid re-rendering the whole transcript on every
        # streamed token (that froze the UI during long final summaries).
        self._render_timer = None
        self._render_dirty = False
        self._render_image_cache = {}
        self._user_bubble_image_paths = []
        self._live_stream_index = None
        self._live_stream_role = None
        self._live_stream_text = ""
        self._finished_live_stream_index = None
        self._stick_to_bottom = True
        self._force_scroll_to_bottom = False
        self._auto_scrolling = False
        # Cache of highlighted code so streaming re-renders don't re-run the
        # syntax highlighter over unchanged code blocks.
        self._highlight_cache = {}
        self.session_summaries = []
        self.session_search_cache = {}
        self.loading_sessions = False
        self.message_queue = SimpleQueue()
        # Ephemeral status (spinner / toast) state.
        self._activity_text = ""
        self._activity_token = 0
        self._flash_text = ""
        self._spin_index = 0
        self.panel_state = load_agent_panel_state()
        self.show_archived_sessions = bool(self.panel_state.get("show_archived_sessions", False))
        self.keep_rpc_on_close = bool(self.panel_state.get("keep_rpc_on_close", True))
        saved_session_id = self.panel_state.get("session_id")
        self.current_session_id = saved_session_id if isinstance(saved_session_id, str) and saved_session_id else make_agent_session_id()
        summary = find_session_summary(self.current_session_id)
        self.current_session_path = summary.path if summary else None
        self.has_saved_geometry = False
        self.setWindowTitle("Codex")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
            | Qt.WindowType.Window
        )
        self.setAutoFillBackground(True)
        self.resize(1180, 760)
        self.build_ui()
        self.restore_saved_geometry()
        self.queue_timer = QTimer(self)
        self.queue_timer.timeout.connect(self.drain_message_queue)
        self.queue_timer.start(80)
        self.activity_timer = QTimer(self)
        self.activity_timer.timeout.connect(self._tick_activity)
        self.refresh_sessions()
        if self.current_session_path:
            self.load_current_session_history()
        else:
            # Clean Codex-like empty state instead of system chatter.
            self.render_messages()
        QTimer.singleShot(250, lambda: self.refresh_rpc_state(announce_start=False))

    # ------------------------------------------------------------------ UI
    def build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(20, 14, 16, 12)
        title_row.setSpacing(10)
        title = QLabel("Codex")
        title.setObjectName("panelTitle")
        title.setFont(tune_agent_font(QFont(AGENT_UI_FONT, 16, QFont.Weight.DemiBold)))
        title_row.addWidget(title)
        title_row.addSpacing(4)

        self.status_dot = QLabel("\u25cf")
        self.status_dot.setObjectName("statusDot")
        title_row.addWidget(self.status_dot)
        self.model_status = QLabel("")
        self.model_status.setObjectName("modelStatus")
        title_row.addWidget(self.model_status)
        self.context_label = QLabel("")
        self.context_label.setObjectName("contextLabel")
        self.context_label.hide()
        title_row.addWidget(self.context_label)

        title_row.addStretch()
        self.minimize_btn = WindowControlButton(self.model, "minimize", self)
        self.minimize_btn.clicked.connect(self.showMinimized)
        self.maximize_btn = WindowControlButton(self.model, "maximize", self)
        self.maximize_btn.clicked.connect(self.toggle_maximized)
        self.close_btn = WindowControlButton(self.model, "close", self)
        self.close_btn.clicked.connect(self.hide)
        for btn in (self.minimize_btn, self.maximize_btn, self.close_btn):
            title_row.addWidget(btn, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(title_row)

        page = QHBoxLayout()
        page.setContentsMargins(14, 0, 14, 14)
        page.setSpacing(12)

        # ---------------------------------------------------------- sidebar
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setMinimumWidth(264)
        self.sidebar.setMaximumWidth(320)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(12, 14, 12, 12)
        sidebar_layout.setSpacing(9)

        history_title = QLabel("\u4f1a\u8bdd")
        history_title.setObjectName("sectionTitle")
        sidebar_layout.addWidget(history_title)

        self.new_session_btn = self.make_button("\uff0b \u65b0\u5efa\u4f1a\u8bdd")
        self.new_session_btn.setObjectName("primaryButton")
        self.new_session_btn.clicked.connect(self.new_session)
        sidebar_layout.addWidget(self.new_session_btn)

        self.session_search = QLineEdit()
        self.session_search.setObjectName("sessionSearch")
        self.session_search.setPlaceholderText("\U0001f50d  \u641c\u7d22\u4f1a\u8bdd")
        self.session_search.textChanged.connect(lambda _text: self.refresh_session_list())
        sidebar_layout.addWidget(self.session_search)

        self.session_list = QListWidget()
        self.session_list.setObjectName("sessionList")
        self.session_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.session_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.session_list.customContextMenuRequested.connect(self.show_session_context_menu)
        self.session_list.itemClicked.connect(self.select_session_item)
        self.session_list.itemActivated.connect(self.select_session_item)
        sidebar_layout.addWidget(self.session_list, 1)

        self.show_archived_btn = self.make_ghost("\u663e\u793a\u5f52\u6863", checkable=True)
        self.show_archived_btn.setChecked(self.show_archived_sessions)
        self.show_archived_btn.clicked.connect(self.toggle_show_archived_sessions)
        sidebar_layout.addWidget(self.show_archived_btn)

        terminal_title = QLabel("\u7ec8\u7aef")
        terminal_title.setObjectName("sectionTitle")
        sidebar_layout.addWidget(terminal_title)
        terminal_actions = QHBoxLayout()
        terminal_actions.setSpacing(6)
        self.vpn_terminal_btn = self.make_ghost("VPN \u7ec8\u7aef")
        self.vpn_terminal_btn.clicked.connect(self.open_vpn_terminal)
        self.plain_terminal_btn = self.make_ghost("\u666e\u901a\u7ec8\u7aef")
        self.plain_terminal_btn.clicked.connect(self.open_plain_terminal)
        terminal_actions.addWidget(self.vpn_terminal_btn)
        terminal_actions.addWidget(self.plain_terminal_btn)
        sidebar_layout.addLayout(terminal_actions)

        page.addWidget(self.sidebar)

        # -------------------------------------------------------- main area
        self.main_area = QFrame()
        self.main_area.setObjectName("mainArea")
        main_layout = QVBoxLayout(self.main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Slim, subdued action strip (secondary controls only).
        action_row = QHBoxLayout()
        action_row.setContentsMargins(16, 10, 16, 8)
        action_row.setSpacing(6)
        self.rpc_state_btn = self.make_ghost("\u72b6\u6001")
        self.rpc_state_btn.clicked.connect(self.refresh_rpc_state)
        self.reconnect_btn = self.make_ghost("\u91cd\u8fde")
        self.reconnect_btn.clicked.connect(self.reconnect_rpc)
        self.keep_rpc_btn = self.make_ghost("\u4fdd\u7559 RPC", checkable=True)
        self.keep_rpc_btn.setChecked(self.keep_rpc_on_close)
        self.keep_rpc_btn.clicked.connect(lambda: self.toggle_keep_rpc_on_close())
        action_row.addWidget(self.rpc_state_btn)
        action_row.addWidget(self.reconnect_btn)
        action_row.addWidget(self.keep_rpc_btn)
        action_row.addStretch()
        self.collapse_all_btn = self.make_ghost("\u6298\u53e0\u5168\u90e8")
        self.collapse_all_btn.clicked.connect(self.collapse_all_sections)
        self.transcript_btn = self.make_ghost("\u7cbe\u7b80\u89c6\u56fe", checkable=True)
        self.transcript_btn.clicked.connect(self.toggle_transcript_mode)
        self.retry_btn = self.make_ghost("\u91cd\u8bd5")
        self.retry_btn.clicked.connect(self.retry_last_prompt)
        self.copy_btn = self.make_ghost("\u590d\u5236\u56de\u590d")
        self.copy_btn.clicked.connect(self.copy_last_reply)
        self.clear_btn = self.make_ghost("\u6e05\u7a7a")
        self.clear_btn.clicked.connect(self.clear_display)
        self.stop_btn = self.make_ghost("\u505c\u6b62")
        self.stop_btn.setObjectName("stopButton")
        self.stop_btn.clicked.connect(self.stop_current_task)
        self.stop_btn.setEnabled(False)
        for btn in (self.collapse_all_btn, self.transcript_btn, self.retry_btn, self.copy_btn, self.clear_btn, self.stop_btn):
            action_row.addWidget(btn)
        main_layout.addLayout(action_row)

        self.message_stream = QTextBrowser()
        self.message_stream.setObjectName("messageStream")
        self.message_stream.setReadOnly(True)
        self.message_stream.setOpenExternalLinks(False)
        self.message_stream.setOpenLinks(False)
        self.message_stream.anchorClicked.connect(self.handle_message_link)
        self.message_stream.setMinimumHeight(360)
        self.message_stream.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.message_stream.setFrameShape(QFrame.Shape.NoFrame)
        self.message_stream.setFont(tune_agent_font(QFont(AGENT_TEXT_FONT, 12)))
        main_layout.addWidget(self.message_stream, 1)
        for _seq, _handler in (
            ("Ctrl++", lambda: self.adjust_font_scale(0.1)),
            ("Ctrl+=", lambda: self.adjust_font_scale(0.1)),
            ("Ctrl+-", lambda: self.adjust_font_scale(-0.1)),
            ("Ctrl+0", lambda: self.reset_font_scale()),
        ):
            _zoom_action = QAction(self)
            _zoom_action.setShortcut(_seq)
            _zoom_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            _zoom_action.triggered.connect(_handler)
            self.addAction(_zoom_action)
        self.apply_message_font()
        self.scroll_bottom_btn = QPushButton("\u2193", self.message_stream.viewport())
        self.scroll_bottom_btn.setObjectName("scrollBottomButton")
        self.scroll_bottom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scroll_bottom_btn.setFixedSize(30, 30)
        self.scroll_bottom_btn.setToolTip("\u56de\u5230\u5e95\u90e8")
        self.scroll_bottom_btn.setStyleSheet(
            "QPushButton{background:rgba(38,41,50,238); color:#d4d7de;"
            " border:1px solid rgba(72,76,87,235); border-radius:15px; font-size:15px;}"
            "QPushButton:hover{background:rgba(52,56,66,248);}"
        )
        self.scroll_bottom_btn.clicked.connect(self.scroll_messages_to_bottom)
        self.scroll_bottom_btn.hide()
        _msg_bar = self.message_stream.verticalScrollBar()
        _msg_bar.valueChanged.connect(self.handle_message_scroll_value_changed)
        _msg_bar.rangeChanged.connect(self.handle_message_scroll_range_changed)

        self.activity_label = QLabel("")
        self.activity_label.setObjectName("activityLabel")
        self.activity_label.setContentsMargins(20, 0, 20, 0)
        self.activity_label.hide()
        main_layout.addWidget(self.activity_label)

        # Codex-like unified input container.
        input_wrap = QHBoxLayout()
        input_wrap.setContentsMargins(16, 8, 16, 6)
        input_wrap.setSpacing(0)
        self.input_container = QFrame()
        self.input_container.setObjectName("inputContainer")
        self.input_container.setMinimumHeight(106)
        self.input_container.setMaximumHeight(180)
        self.input_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        input_col = QVBoxLayout(self.input_container)
        input_col.setContentsMargins(12, 10, 12, 10)
        input_col.setSpacing(8)
        self.prompt_input = QTextEdit()
        self.prompt_input.setObjectName("promptInput")
        self.prompt_input.setFrameShape(QFrame.Shape.NoFrame)
        self.prompt_input.setFont(tune_agent_font(QFont(AGENT_TEXT_FONT, 12)))
        self.prompt_input.setMinimumHeight(44)
        self.prompt_input.setMaximumHeight(112)
        self.prompt_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.prompt_input.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.prompt_input.setPlaceholderText("\u7ed9 Codex \u53d1\u9001\u4efb\u52a1\u2026")
        self.prompt_input.textChanged.connect(self.update_prompt_height)
        input_col.addWidget(self.prompt_input)
        # Keep the input font in lockstep with the message font (same size).
        self.apply_message_font()
        # Slash-command autocomplete popup (child overlay above the input).
        self.slash_popup = QListWidget(self)
        self.slash_popup.setObjectName("slashPopup")
        self.slash_popup.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.slash_popup.setStyleSheet(_SLASH_POPUP_QSS)
        self.slash_popup.itemClicked.connect(
            lambda item: self.accept_slash_item(self.slash_popup.row(item), execute=True)
        )
        self.slash_popup.hide()
        self.prompt_input.textChanged.connect(self.update_slash_popup)
        input_toolbar = QHBoxLayout()
        input_toolbar.setContentsMargins(2, 0, 2, 0)
        input_toolbar.setSpacing(8)
        self.attach_btn = QPushButton("\U0001f4ce")
        self.attach_btn.setObjectName("inputToolButton")
        self.attach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.attach_btn.setFixedSize(30, 30)
        self.attach_btn.setToolTip("\u63d2\u5165\u6587\u4ef6\u8def\u5f84")
        self.attach_btn.setStyleSheet(_INPUT_TOOL_QSS)
        self.attach_btn.clicked.connect(self.insert_file_reference)
        input_toolbar.addWidget(self.attach_btn)
        self.model_chip = QPushButton("\u6a21\u578b")
        self.model_chip.setObjectName("modelChip")
        self.model_chip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.model_chip.setToolTip("点击选择思考强度；Shift+点击刷新状态")
        self.model_chip.setStyleSheet(_MODEL_CHIP_QSS)
        self.model_chip.clicked.connect(self.on_model_chip_clicked)
        input_toolbar.addWidget(self.model_chip)
        input_toolbar.addStretch()
        self.send_btn = AgentSendButton(self)
        self.send_btn.setObjectName("sendButton")
        self.send_btn.clicked.connect(self.send_prompt)
        input_toolbar.addWidget(self.send_btn)
        input_col.addLayout(input_toolbar)
        self.update_prompt_height()
        input_wrap.addWidget(self.input_container, 1)
        main_layout.addLayout(input_wrap)

        self.hint_label = QLabel("Enter \u53d1\u9001  \u00b7  Shift+Enter \u6362\u884c  \u00b7  Esc \u505c\u6b62  \u00b7  /help \u67e5\u770b\u547d\u4ee4")
        self.hint_label.setObjectName("hintLabel")
        self.hint_label.setContentsMargins(20, 0, 20, 10)
        main_layout.addWidget(self.hint_label)

        page.addWidget(self.main_area, 1)
        root.addLayout(page, 1)
        self.install_drag_filters()
        self.refresh()

    # --------------------------------------------------------------- theme
    @staticmethod
    def css_rgb(color):
        return f"rgb({int(color[0])}, {int(color[1])}, {int(color[2])})"

    @staticmethod
    def css_rgba(color, alpha):
        return f"rgba({int(color[0])}, {int(color[1])}, {int(color[2])}, {int(alpha)})"

    def apply_theme_style(self):
        if self.styled_theme == self.model.theme_key:
            return
        self.styled_theme = self.model.theme_key
        theme = self.model.themes[self.model.theme_key]
        accent = theme.accent
        from string import Template

        # Neutral, low-chroma charcoal palette inspired by Codex. The theme
        # accent only appears on the focus ring, send button and live markers.
        bg_top = (15, 16, 19)
        bg_bottom = (10, 11, 13)
        panel = (19, 20, 24)
        input_bg = (23, 25, 30)
        stream_bg = (13, 14, 17)
        border = (40, 43, 51)
        border_soft = (29, 32, 39)
        hover = (31, 34, 41)
        text = (226, 228, 233)
        muted = (143, 149, 159)
        faint = (99, 105, 115)
        accent_soft = color_mix(accent, (236, 239, 245), 0.34)
        send_bg = color_mix(accent, (30, 33, 40), 0.42)
        send_hover = color_mix(accent, (46, 50, 60), 0.36)
        sel = color_mix(accent, (42, 46, 56), 0.45)
        c = {
            "bg_top": self.css_rgb(bg_top),
            "bg_bottom": self.css_rgb(bg_bottom),
            "text": self.css_rgb(text),
            "text130": self.css_rgba(text, 130),
            "muted": self.css_rgb(muted),
            "muted160": self.css_rgba(muted, 160),
            "faint": self.css_rgb(faint),
            "faint200": self.css_rgba(faint, 200),
            "faint150": self.css_rgba(faint, 150),
            "faint120": self.css_rgba(faint, 120),
            "accent_soft": self.css_rgb(accent_soft),
            "accent_soft180": self.css_rgba(accent_soft, 180),
            "accent_soft170": self.css_rgba(accent_soft, 170),
            "accent_soft150": self.css_rgba(accent_soft, 150),
            "accent_soft130": self.css_rgba(accent_soft, 130),
            "panel220": self.css_rgba(panel, 220),
            "panel180": self.css_rgba(panel, 180),
            "panel120": self.css_rgba(panel, 120),
            "border210": self.css_rgba(border, 210),
            "border215": self.css_rgba(border, 215),
            "border220": self.css_rgba(border, 220),
            "border_soft210": self.css_rgba(border_soft, 210),
            "border_soft200": self.css_rgba(border_soft, 200),
            "border_soft140": self.css_rgba(border_soft, 140),
            "hover": self.css_rgb(hover),
            "hover170": self.css_rgba(hover, 170),
            "stream230": self.css_rgba(stream_bg, 230),
            "stream235": self.css_rgba(stream_bg, 235),
            "stream120": self.css_rgba(stream_bg, 120),
            "input245": self.css_rgba(input_bg, 245),
            "sel150": self.css_rgba(sel, 150),
            "sel120": self.css_rgba(sel, 120),
            "send_bg": self.css_rgb(send_bg),
            "send_bg240": self.css_rgba(send_bg, 240),
            "send_bg120": self.css_rgba(send_bg, 120),
            "send_hover": self.css_rgb(send_hover),
            "stop": self.css_rgb((226, 122, 122)),
            "stop_hover": self.css_rgba((150, 60, 60), 90),
        }
        template = Template(
            """
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 $bg_top, stop:1 $bg_bottom);
                color: $text;
                border: 1px solid $border210;
                font-family: "Segoe UI", "Microsoft YaHei UI";
            }
            QFrame#sidebar {
                background: $panel180;
                border: 1px solid $border_soft210;
                border-radius: 12px;
            }
            QFrame#mainArea {
                background: transparent;
                border: none;
            }
            QLabel { color: $muted; }
            QLabel#panelTitle { color: $text; padding: 0 2px; }
            QLabel#statusDot { color: $faint; padding-left: 2px; font-size: 11px; }
            QLabel#modelStatus { color: $faint; font-size: 12px; }
            QLabel#contextLabel { color: $faint; font-size: 11px; padding-left: 8px; }
            QLabel#sectionTitle {
                color: $faint; font-size: 11px; font-weight: 700;
                letter-spacing: 0px; padding: 8px 2px 2px 2px;
            }
            QLabel#hintLabel { color: $faint200; font-size: 11px; }
            QFrame#inputContainer {
                background: $stream235;
                border: 1px solid $border_soft210;
                border-radius: 16px;
            }
            QFrame#inputContainer[focused="true"] {
                border: 1px solid $accent_soft180;
                background: $input245;
            }
            QTextEdit#promptInput {
                background: transparent; border: none; color: $text;
                selection-background-color: $sel150;
                padding: 2px 4px;
            }
            QLabel#activityLabel {
                color: $accent_soft; font-size: 12px; padding: 3px 0 1px 0;
                font-family: "Cascadia Code", "Consolas", "Segoe UI", "Microsoft YaHei UI";
            }
            QLineEdit#sessionSearch {
                background: $stream230; color: $text;
                selection-background-color: $sel150;
                border: 1px solid $border_soft210; border-radius: 9px;
                padding: 7px 11px;
            }
            QLineEdit#sessionSearch:focus { border: 1px solid $accent_soft180; }
            QListWidget#sessionList {
                background: $stream120; color: $text;
                border: 1px solid transparent; border-radius: 10px;
                padding: 5px; outline: 0;
            }
            QListWidget#sessionList::item {
                padding: 2px 3px; border-radius: 10px; margin: 1px 2px;
                color: $muted;
            }
            QListWidget#sessionList::item:hover { background: $hover170; color: $text; }
            QListWidget#sessionList::item:selected {
                background: $sel150; color: $text;
            }
            QLabel#sessionName { color: $text; font-size: 13px; background: transparent; }
            QLabel#sessionTime { color: $faint; font-size: 11px; background: transparent; }
            QPushButton#rowActionButton {
                background: transparent; color: $muted;
                border: none; border-radius: 6px; padding: 0;
                font-size: 13px; min-height: 0;
            }
            QPushButton#rowActionButton:hover { background: $hover; color: $text; }
            QTextBrowser#messageStream {
                background: transparent; color: $text;
                selection-background-color: $sel150;
                border: none; border-radius: 0;
                padding: 8px 28px 6px 28px;
            }
            QFrame#inputContainer {
                background: $input245;
                border: 1px solid $border215; border-radius: 22px;
            }
            QTextEdit#promptInput {
                background: transparent; color: $text;
                selection-background-color: $sel150;
                border: none; padding: 4px 4px;
            }
            QPushButton {
                background: $panel220; color: $text;
                border: 1px solid $border_soft200; border-radius: 9px;
                padding: 6px 10px; min-height: 22px;
            }
            QPushButton:hover { background: $hover; border-color: $accent_soft150; }
            QPushButton:pressed { background: $border220; }
            QPushButton:disabled { color: $faint150; background: $panel120; }
            QPushButton#primaryButton {
                background: $send_bg240; color: white; font-weight: 600;
                border: 1px solid $accent_soft180;
            }
            QPushButton#primaryButton:hover { background: $send_hover; }
            QPushButton#ghostButton {
                background: transparent; color: $muted;
                border: 1px solid transparent; border-radius: 8px;
                padding: 5px 9px; min-height: 20px;
            }
            QPushButton#ghostButton:hover { background: $hover170; color: $text; }
            QPushButton#ghostButton:checked {
                background: $sel120; color: $text;
                border: 1px solid $accent_soft130;
            }
            QPushButton#stopButton { color: $stop; }
            QPushButton#stopButton:hover { background: $stop_hover; color: white; }
            QPushButton#stopButton:disabled { color: $faint120; background: transparent; }
            QScrollBar:vertical { width: 9px; background: transparent; margin: 3px 2px; }
            QScrollBar::handle:vertical { background: $border220; border-radius: 4px; min-height: 32px; }
            QScrollBar::handle:vertical:hover { background: $muted160; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; background: none; border: none; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
            QScrollBar:horizontal { height: 9px; background: transparent; margin: 2px 3px; }
            QScrollBar::handle:horizontal { background: $border220; border-radius: 4px; min-width: 32px; }
            QScrollBar::handle:horizontal:hover { background: $muted160; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; background: none; border: none; }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }
            """
        )
        self.setStyleSheet(template.substitute(c))

    # ----------------------------------------------------------- behaviour
    def install_drag_filters(self):
        self.installEventFilter(self)
        for widget in self.findChildren(QWidget):
            widget.installEventFilter(self)
            if isinstance(widget, QLabel) and widget.objectName() in {"panelTitle", "modelStatus", "statusDot"}:
                widget.setCursor(Qt.CursorShape.SizeAllCursor)

    def _set_input_focused(self, focused):
        container = getattr(self, "input_container", None)
        if container is None:
            return
        container.setProperty("focused", "true" if focused else "false")
        style = container.style()
        style.unpolish(container)
        style.polish(container)

    def eventFilter(self, obj, event):
        event_name = event.type().name
        if obj is getattr(self, "prompt_input", None) and event_name == "FocusIn":
            self._set_input_focused(True)
        if obj is getattr(self, "prompt_input", None) and event_name == "FocusOut":
            self._set_input_focused(False)
            self.hide_slash_popup()
        if obj is getattr(self, "prompt_input", None) and event_name == "KeyPress":
            key = event.key()
            mods = event.modifiers()
            popup = getattr(self, "slash_popup", None)
            if popup is not None and popup.isVisible():
                if key in {Qt.Key.Key_Up, Qt.Key.Key_Down}:
                    row = popup.currentRow() + (-1 if key == Qt.Key.Key_Up else 1)
                    popup.setCurrentRow(max(0, min(popup.count() - 1, row)))
                    return True
                if key == Qt.Key.Key_Escape:
                    self.hide_slash_popup()
                    return True
                if key == Qt.Key.Key_Tab:
                    self.accept_slash_item(popup.currentRow(), execute=False)
                    return True
                if key in {Qt.Key.Key_Return, Qt.Key.Key_Enter} and not (mods & Qt.KeyboardModifier.ShiftModifier):
                    self.accept_slash_item(popup.currentRow(), execute=True)
                    return True
            if key == Qt.Key.Key_Escape and self.pi_running:
                self.stop_current_task()
                return True
            if key in {Qt.Key.Key_Return, Qt.Key.Key_Enter} and not (mods & Qt.KeyboardModifier.ShiftModifier):
                self.send_prompt()
                return True
            if key in {Qt.Key.Key_Up, Qt.Key.Key_Down} and not (mods & Qt.KeyboardModifier.ShiftModifier):
                if self.try_history_navigation(key == Qt.Key.Key_Up):
                    return True
            else:
                self._history_index = None
        if event_name == "KeyPress" and event.key() == Qt.Key.Key_Escape and self.pi_running:
            self.stop_current_task()
            return True
        if event_name == "MouseButtonDblClick" and event.button() == Qt.MouseButton.LeftButton:
            if self.is_title_drag_target(obj, event):
                self.toggle_maximized()
                return True
        if event_name == "MouseButtonPress" and event.button() == Qt.MouseButton.LeftButton:
            if self.is_title_drag_target(obj, event):
                self.start_panel_drag(event.globalPosition().toPoint())
                return True
        elif event_name == "MouseMove" and self.dragging_panel:
            delta = event.globalPosition().toPoint() - self.drag_start
            self.move(self.drag_origin + delta)
            return True
        elif event_name == "MouseButtonRelease" and self.dragging_panel:
            if event.button() == Qt.MouseButton.LeftButton:
                self.dragging_panel = False
                self.releaseMouse()
                self.unsetCursor()
                return True
        return super().eventFilter(obj, event)

    def is_interactive_drag_target(self, obj):
        widget = obj if isinstance(obj, QWidget) else None
        while widget and widget is not self:
            if isinstance(widget, (QPushButton, QTextEdit, QComboBox, QLineEdit, QListWidget)):
                return True
            widget = widget.parentWidget()
        return False

    def is_title_drag_target(self, obj, event):
        if self.is_interactive_drag_target(obj):
            return False
        if not hasattr(event, "globalPosition"):
            return False
        local_pos = self.mapFromGlobal(event.globalPosition().toPoint())
        return 0 <= local_pos.y() <= 54

    def start_panel_drag(self, global_pos):
        if self.isMaximized():
            screen = QApplication.screenAt(global_pos) or QApplication.primaryScreen()
            available = screen.availableGeometry()
            ratio_x = (global_pos.x() - available.left()) / max(1, available.width())
            self.showNormal()
            self.refresh()
            width = self.width()
            height = self.height()
            x = int(global_pos.x() - width * ratio_x)
            y = int(global_pos.y() - 24)
            x = int(clamp(x, available.left(), max(available.left(), available.right() - width + 1)))
            y = int(clamp(y, available.top(), max(available.top(), available.bottom() - height + 1)))
            self.move(x, y)
        self.dragging_panel = True
        self.drag_start = global_pos
        self.drag_origin = self.pos()
        self.grabMouse()
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def make_button(self, text, checkable=False):
        btn = QPushButton(text)
        btn.setCheckable(checkable)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    def make_ghost(self, text, checkable=False):
        btn = QPushButton(text)
        btn.setObjectName("ghostButton")
        btn.setCheckable(checkable)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    def insert_file_reference(self):
        path, ok = QInputDialog.getText(
            self, "\u63d2\u5165\u6587\u4ef6", "\u8f93\u5165\u6587\u4ef6\u6216\u76ee\u5f55\u8def\u5f84\uff1a"
        )
        if not ok:
            return
        path = (path or "").strip()
        if not path:
            return
        reference = path if path.startswith("@") else "@" + path
        self.prompt_input.insertPlainText(reference + " ")
        self.prompt_input.setFocus(Qt.FocusReason.OtherFocusReason)

    # ----------------------------------------------------- prompt history
    def record_prompt_history(self, prompt):
        prompt = (prompt or "").strip()
        if not prompt:
            return
        history = getattr(self, "prompt_history", None)
        if history is None:
            history = self.prompt_history = []
        if not history or history[-1] != prompt:
            history.append(prompt)
            del history[:-100]
        self._history_index = None

    def try_history_navigation(self, go_back):
        history = getattr(self, "prompt_history", [])
        if not history:
            return False
        if self._history_index is None:
            if self.prompt_input.toPlainText().strip():
                return False
            if not go_back:
                return False
            self._history_index = len(history) - 1
            self._set_prompt_from_history(history[self._history_index])
            return True
        if go_back:
            if self._history_index > 0:
                self._history_index -= 1
                self._set_prompt_from_history(history[self._history_index])
            return True
        if self._history_index < len(history) - 1:
            self._history_index += 1
            self._set_prompt_from_history(history[self._history_index])
        else:
            self._history_index = None
            self.prompt_input.clear()
        return True

    def _set_prompt_from_history(self, text):
        self.prompt_input.setPlainText(text)
        cursor = self.prompt_input.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.prompt_input.setTextCursor(cursor)

    # ------------------------------------------------------ slash autocomplete
    def update_slash_popup(self):
        popup = getattr(self, "slash_popup", None)
        if popup is None:
            return
        text = self.prompt_input.toPlainText()
        if not text.startswith("/") or "\n" in text or " " in text:
            self.hide_slash_popup()
            return
        prefix = text.lower()
        matches = [(n, d) for (n, d) in SLASH_COMMANDS if n.startswith(prefix)]
        if not matches or (len(matches) == 1 and matches[0][0] == prefix):
            self.hide_slash_popup()
            return
        self._slash_matches = matches
        popup.clear()
        for name, desc in matches:
            popup.addItem(f"{name}    {desc}")
        popup.setCurrentRow(0)
        self._position_slash_popup()
        popup.show()
        popup.raise_()

    def _position_slash_popup(self):
        popup = getattr(self, "slash_popup", None)
        container = getattr(self, "input_container", None)
        if popup is None or container is None:
            return
        top_left = container.mapTo(self, QPoint(0, 0))
        visible = max(1, min(len(self._slash_matches), 6))
        height = visible * 28 + 10
        popup.setFixedWidth(container.width())
        popup.setFixedHeight(height)
        popup.move(top_left.x(), top_left.y() - height - 6)

    def hide_slash_popup(self):
        popup = getattr(self, "slash_popup", None)
        if popup is not None and popup.isVisible():
            popup.hide()

    def accept_slash_item(self, row, execute):
        matches = getattr(self, "_slash_matches", [])
        if row is None or row < 0 or row >= len(matches):
            self.hide_slash_popup()
            return
        name = matches[row][0]
        self.hide_slash_popup()
        if execute and name in SLASH_NO_ARG:
            self.prompt_input.clear()
            self.handle_local_command(name)
        else:
            self.prompt_input.setPlainText(name + " ")
            cursor = self.prompt_input.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.prompt_input.setTextCursor(cursor)
        self.prompt_input.setFocus(Qt.FocusReason.OtherFocusReason)

    def toggle_maximized(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self.refresh()

    def refresh(self):
        previous_theme = self.styled_theme
        self.apply_theme_style()
        if previous_theme != self.styled_theme and self.display_messages:
            self.render_messages()
        for btn_name in ("minimize_btn", "maximize_btn", "close_btn"):
            btn = getattr(self, btn_name, None)
            if btn:
                btn.update()
        now = time.monotonic()
        if now - self.last_status_update > 1.5:
            self.last_status_update = now
            self.update_status_labels()

    # ----------------------------------------------------- activity / toast
    def _render_activity_label(self):
        """Paint the spinner + status text into the dedicated status label.

        Keeping this on a lightweight QLabel (instead of repainting the whole
        HTML transcript) lets the spinner animate smoothly and never collide
        with the streamed answer text.
        """
        label = getattr(self, "activity_label", None)
        if label is None:
            return
        activity = (getattr(self, "_activity_text", "") or "").strip()
        flash = (getattr(self, "_flash_text", "") or "").strip()
        if activity:
            marker = SPINNER_FRAMES[getattr(self, "_spin_index", 0) % len(SPINNER_FRAMES)]
            suffix = ""
            started = getattr(self, "_run_started_at", None)
            if getattr(self, "pi_running", False) and started is not None:
                secs = int(max(0.0, time.monotonic() - started))
                suffix = f"   ·   {secs}s   ·   Esc 中断"
            label.setText(f"{marker}  {activity}{suffix}")
            label.show()
        elif flash:
            label.setText(flash)
            label.show()
        else:
            label.clear()
            label.hide()

    def _tick_activity(self):
        if not self._activity_text:
            self.activity_timer.stop()
            self._render_activity_label()
            return
        self._spin_index = (self._spin_index + 1) % len(SPINNER_FRAMES)
        self._render_activity_label()

    def set_activity(self, text):
        text = (text or "").strip()
        self._activity_text = text
        if text:
            if not self.activity_timer.isActive():
                self.activity_timer.start(ACTIVITY_TICK_MS)
        else:
            self.activity_timer.stop()
        self._render_activity_label()

    def flash_status(self, text, msec=2600):
        # Transient toast. Never clobbers an ongoing (spinner) activity.
        text = (text or "").strip()
        if not text or self._activity_text:
            return
        self._activity_token += 1
        token = self._activity_token
        self._flash_text = text
        self._render_activity_label()

        def clear():
            if self._activity_token == token and not self._activity_text:
                self._flash_text = ""
                self._render_activity_label()

        QTimer.singleShot(msec, clear)

    # --------------------------------------------------------- geometry/io
    def restore_saved_geometry(self):
        geometry = self.panel_state.get("geometry")
        if not isinstance(geometry, dict):
            return
        try:
            x = int(geometry.get("x", self.x()))
            y = int(geometry.get("y", self.y()))
            w = int(geometry.get("w", self.width()))
            h = int(geometry.get("h", self.height()))
        except (TypeError, ValueError):
            return
        screen = QApplication.primaryScreen().availableGeometry()
        w = int(clamp(w, 560, min(1120, screen.width())))
        h = int(clamp(h, 480, min(900, screen.height())))
        x = int(clamp(x, screen.left(), max(screen.left(), screen.right() - w)))
        y = int(clamp(y, screen.top(), max(screen.top(), screen.bottom() - h)))
        self.resize(w, h)
        self.move(x, y)
        self.has_saved_geometry = True

    def save_state(self):
        self.panel_state["session_id"] = self.current_session_id
        self.panel_state["show_archived_sessions"] = self.show_archived_sessions
        self.panel_state["keep_rpc_on_close"] = self.keep_rpc_on_close
        self.panel_state["geometry"] = {
            "x": self.x(),
            "y": self.y(),
            "w": self.width(),
            "h": self.height(),
        }
        save_agent_panel_state(self.panel_state)

    def hideEvent(self, event):
        self.save_state()
        if not self.keep_rpc_on_close:
            self.stop_rpc()
        super().hideEvent(event)

    def closeEvent(self, event):
        self.save_state()
        if not self.keep_rpc_on_close:
            self.stop_rpc()
        self.cleanup_render_images()
        super().closeEvent(event)
