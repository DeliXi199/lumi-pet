from __future__ import annotations

from ..model import PetModel
from ..qt import QApplication, QDialog, QFont, QGridLayout, QHBoxLayout, QLabel, QPoint, QPushButton, QSignalBlocker, QSlider, QTextEdit, QVBoxLayout, QWidget, Qt
from ..utils import clamp, color_mix
from .buttons import CloseButton


class ControlPanel(QDialog):
    def __init__(self, model: PetModel, pet: PetWindow):
        super().__init__(pet)
        self.model = model
        self.pet = pet
        self.dragging_panel = False
        self.drag_start = QPoint()
        self.drag_origin = QPoint()
        self.styled_theme = None
        self.setWindowTitle("宠物控制台")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAutoFillBackground(True)
        self.resize(540, 620)
        self.mood_buttons = {}
        self.theme_buttons = {}
        self.build_ui()

    def build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(8)
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        title = QLabel("宠物控制台")
        title.setObjectName("panelTitle")
        title.setFont(QFont("Microsoft YaHei UI", 18, QFont.Weight.DemiBold))
        title_row.addWidget(title)
        title_row.addStretch()
        self.close_btn = CloseButton(self.model, self)
        self.close_btn.clicked.connect(self.hide)
        title_row.addWidget(self.close_btn, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(title_row)
        self.status = QLabel("")
        self.status.setObjectName("statusText")
        root.addWidget(self.status)
        self.talk = QTextEdit()
        self.talk.setMinimumHeight(86)
        self.talk.setPlaceholderText("在这里打字 —— 打得越快它越兴奋；停下太久它会犯困")
        root.addWidget(self.talk)
        root.addWidget(self.section("神态 Mood"))
        mood_grid = QGridLayout()
        mood_grid.setHorizontalSpacing(8)
        mood_grid.setVerticalSpacing(8)
        auto = self.make_button("自动", checkable=True)
        auto.clicked.connect(lambda: self.set_mood("auto"))
        self.mood_buttons["auto"] = auto
        mood_grid.addWidget(auto, 0, 0)
        for i, key in enumerate(self.model.manual_moods):
            btn = self.make_button(self.model.moods[key].label.split(" · ")[0], checkable=True)
            btn.clicked.connect(lambda checked=False, k=key: self.set_mood(k))
            self.mood_buttons[key] = btn
            mood_grid.addWidget(btn, (i + 1) // 5, (i + 1) % 5)
        root.addLayout(mood_grid)
        root.addWidget(self.section("配色 Palette"))
        theme_grid = QGridLayout()
        theme_grid.setHorizontalSpacing(8)
        theme_grid.setVerticalSpacing(8)
        for i, key in enumerate(self.model.themes):
            btn = self.make_button(self.model.themes[key].label, checkable=True)
            btn.clicked.connect(lambda checked=False, k=key: self.set_theme(k))
            self.theme_buttons[key] = btn
            theme_grid.addWidget(btn, i // 4, i % 4)
        root.addLayout(theme_grid)
        root.addWidget(self.section("时间 / 昼夜"))
        self.time_label = QLabel("")
        root.addWidget(self.time_label)
        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setRange(0, 1440)
        self.time_slider.setSingleStep(5)
        self.time_slider.setPageStep(60)
        self.time_slider.valueChanged.connect(self.time_changed)
        root.addWidget(self.time_slider)
        root.addWidget(self.section("系统繁忙度"))
        self.busy_label = QLabel("")
        root.addWidget(self.busy_label)
        self.busy_slider = QSlider(Qt.Orientation.Horizontal)
        self.busy_slider.setRange(0, 100)
        self.busy_slider.valueChanged.connect(lambda v: self.set_busy(v / 100))
        root.addWidget(self.busy_slider)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.sound_btn = self.make_button("静音中", checkable=True)
        self.sound_btn.clicked.connect(self.toggle_sound)
        self.real_btn = self.make_button("真实时间", checkable=True)
        self.real_btn.clicked.connect(lambda: self.set_time_mode("real"))
        self.fast_btn = self.make_button("加速一天", checkable=True)
        self.fast_btn.clicked.connect(lambda: self.set_time_mode("fast" if self.model.time_mode != "fast" else "manual"))
        self.top_btn = self.make_button("取消置顶", checkable=True)
        self.top_btn.clicked.connect(self.toggle_topmost)
        hide_btn = self.make_button("隐藏")
        hide_btn.clicked.connect(self.hide)
        quit_btn = self.make_button("关闭宠物")
        quit_btn.clicked.connect(QApplication.quit)
        for btn in (self.sound_btn, self.real_btn, self.fast_btn, self.top_btn, hide_btn, quit_btn):
            actions.addWidget(btn)
        root.addLayout(actions)
        hint = QLabel("左键拖动宠物移动 · 点一下是戳 · 身上来回划是抚摸 · 右键宠物打开选项")
        hint.setObjectName("hintText")
        hint.setWordWrap(True)
        root.addWidget(hint)
        self.install_drag_filters()
        self.refresh()

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
        base = theme.base
        accent = theme.accent
        panel = color_mix(base, (13, 15, 20), 0.84)
        panel_lift = color_mix(base, (25, 29, 38), 0.72)
        input_bg = color_mix(base, (14, 17, 24), 0.78)
        button_bg = color_mix(base, (24, 28, 38), 0.70)
        button_hover = color_mix(base, (38, 45, 58), 0.58)
        button_checked = color_mix(accent, (42, 50, 70), 0.38)
        text = color_mix(base, (255, 255, 255), 0.82)
        muted = color_mix(base, (184, 193, 210), 0.60)
        accent_soft = color_mix(accent, (255, 255, 255), 0.35)
        accent_deep = color_mix(accent, (10, 12, 18), 0.44)
        groove = color_mix(base, (34, 39, 50), 0.74)

        self.setStyleSheet(
            f"""
            QDialog {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {theme.bg[0]}, stop:1 {theme.bg[1]});
                color: {self.css_rgb(text)};
                border: 1px solid {self.css_rgba(accent, 118)};
                border-radius: 0;
            }}
            QLabel {{
                color: {self.css_rgb(muted)};
            }}
            QLabel#panelTitle {{
                color: {self.css_rgb(text)};
                padding: 2px 2px 4px 2px;
            }}
            QLabel#statusText {{
                color: {self.css_rgb(accent_soft)};
                background: {self.css_rgba(panel_lift, 212)};
                border: 1px solid {self.css_rgba(accent, 116)};
                border-radius: 8px;
                padding: 7px 9px;
            }}
            QLabel#hintText {{
                color: {self.css_rgba(muted, 190)};
                padding-top: 4px;
            }}
            QLabel[panelRole="section"] {{
                color: {self.css_rgb(accent_soft)};
                padding-top: 8px;
            }}
            QTextEdit {{
                background: {self.css_rgba(input_bg, 236)};
                color: {self.css_rgb(text)};
                selection-background-color: {self.css_rgba(accent, 132)};
                border: 1px solid {self.css_rgba(accent, 104)};
                border-radius: 8px;
                padding: 9px;
            }}
            QTextEdit:focus {{
                border: 1px solid {self.css_rgba(accent_soft, 210)};
            }}
            QPushButton {{
                background: {self.css_rgb(button_bg)};
                color: {self.css_rgb(text)};
                border: 1px solid {self.css_rgba(accent, 108)};
                border-radius: 8px;
                padding: 6px 10px;
                min-height: 26px;
            }}
            QPushButton:hover {{
                background: {self.css_rgb(button_hover)};
                border-color: {self.css_rgba(accent_soft, 190)};
            }}
            QPushButton:pressed {{
                background: {self.css_rgb(accent_deep)};
            }}
            QPushButton:checked {{
                background: {self.css_rgb(button_checked)};
                border-color: {self.css_rgb(accent_soft)};
                color: white;
            }}
            QSlider::groove:horizontal {{
                height: 8px;
                background: {self.css_rgb(groove)};
                border-radius: 4px;
            }}
            QSlider::sub-page:horizontal {{
                background: {self.css_rgba(accent, 190)};
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                width: 18px;
                height: 18px;
                margin: -6px 0;
                border-radius: 9px;
                background: {self.css_rgb(accent_soft)};
                border: 2px solid {self.css_rgb(panel)};
            }}
            QSlider::handle:horizontal:hover {{
                background: white;
            }}
            """
        )
        self.update_theme_button_styles(text)

    def update_theme_button_styles(self, text):
        for key, btn in self.theme_buttons.items():
            theme = self.model.themes[key]
            swatch = theme.base
            bg = color_mix(swatch, (21, 25, 34), 0.74)
            hover = color_mix(swatch, (42, 48, 62), 0.55)
            checked = color_mix(swatch, (38, 44, 58), 0.34)
            btn.setStyleSheet(
                f"""
                QPushButton {{
                    background: {self.css_rgb(bg)};
                    color: {self.css_rgb(text)};
                    border: 1px solid {self.css_rgba(swatch, 150)};
                    border-left: 10px solid {self.css_rgb(swatch)};
                    border-radius: 8px;
                    padding: 6px 10px;
                    padding-left: 12px;
                    min-height: 26px;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background: {self.css_rgb(hover)};
                    border-color: {self.css_rgba(swatch, 220)};
                    border-left: 10px solid {self.css_rgb(swatch)};
                }}
                QPushButton:checked {{
                    background: {self.css_rgb(checked)};
                    border: 2px solid {self.css_rgb(swatch)};
                    border-left: 10px solid {self.css_rgb(swatch)};
                    color: white;
                }}
                """
            )

    def install_drag_filters(self):
        self.installEventFilter(self)
        for widget in self.findChildren(QWidget):
            widget.installEventFilter(self)
            if isinstance(widget, QLabel):
                widget.setCursor(Qt.CursorShape.SizeAllCursor)

    def eventFilter(self, obj, event):
        event_name = event.type().name
        if obj is getattr(self, "talk", None) and event_name == "KeyPress":
            self.model.notify_typing()
            if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter} and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                text = self.talk.toPlainText().strip()
                self.talk.clear()
                self.pet.submit_chat(text)
                return True
        if event_name == "MouseButtonPress" and event.button() == Qt.MouseButton.LeftButton:
            if not self.is_interactive_drag_target(obj):
                self.dragging_panel = True
                self.drag_start = event.globalPosition().toPoint()
                self.drag_origin = self.pos()
                self.grabMouse()
                self.setCursor(Qt.CursorShape.SizeAllCursor)
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
            if isinstance(widget, (QPushButton, QSlider, QTextEdit)):
                return True
            widget = widget.parentWidget()
        return False

    def section(self, text):
        label = QLabel(text)
        label.setProperty("panelRole", "section")
        label.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.DemiBold))
        return label

    def make_button(self, text, checkable=False):
        btn = QPushButton(text)
        btn.setCheckable(checkable)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    def focus_talk(self):
        self.talk.setFocus(Qt.FocusReason.OtherFocusReason)

    def refresh(self):
        self.apply_theme_style()
        self.close_btn.update()
        self.status.setText(self.model.status_text())
        mode = "跟随真实" if self.model.time_mode == "real" else "加速演示" if self.model.time_mode == "fast" else "手动"
        self.time_label.setText(f"时间 / 昼夜：{mode}")
        self.busy_label.setText(f"系统繁忙度：{round(self.model.busy_manual * 100)}%")
        with QSignalBlocker(self.time_slider):
            self.time_slider.setValue(int(clamp(self.model.current_minutes() if self.model.time_mode == "real" else self.model.manual_minutes, 0, 1440)))
        with QSignalBlocker(self.busy_slider):
            self.busy_slider.setValue(int(clamp(self.model.busy_manual * 100, 0, 100)))
        self.sound_btn.setText("有声" if self.model.sound_on else "静音中")
        self.sound_btn.setChecked(self.model.sound_on)
        self.real_btn.setChecked(self.model.time_mode == "real")
        self.fast_btn.setChecked(self.model.time_mode == "fast")
        self.top_btn.setChecked(bool(self.pet.windowFlags() & Qt.WindowType.WindowStaysOnTopHint))
        self.top_btn.setText("取消置顶" if self.top_btn.isChecked() else "保持置顶")
        for key, btn in self.mood_buttons.items():
            btn.setChecked(self.model.autopilot if key == "auto" else (not self.model.autopilot and self.model.manual_mood == key))
        for key, btn in self.theme_buttons.items():
            btn.setChecked(self.model.theme_key == key)

    def set_mood(self, mood):
        if mood == "auto":
            self.model.autopilot = True
        else:
            self.model.autopilot = False
            self.model.manual_mood = mood
            self.model.last_interact = self.model.t
        self.model.save_settings()
        self.refresh()

    def set_theme(self, key):
        self.model.theme_key = key
        self.model.save_settings()
        self.refresh()

    def set_busy(self, value):
        self.model.busy_manual = clamp(value, 0, 1)
        self.model.save_settings()

    def time_changed(self, value):
        if self.time_slider.isSliderDown():
            snapped = int(round(value / 5) * 5)
            if snapped != value:
                with QSignalBlocker(self.time_slider):
                    self.time_slider.setValue(snapped)
            self.model.manual_minutes = snapped
            self.model.time_mode = "manual"
            self.model.save_settings()
            self.refresh()

    def set_time_mode(self, mode):
        if mode == "fast" and self.model.time_mode != "fast":
            self.model.manual_minutes = self.model.current_minutes()
        self.model.time_mode = mode
        self.model.save_settings()
        self.refresh()

    def toggle_sound(self):
        self.model.sound_on = not self.model.sound_on
        if self.model.sound_on:
            self.model.sfx_chime()
        self.model.save_settings()
        self.refresh()

    def toggle_topmost(self):
        flags = self.pet.windowFlags()
        if flags & Qt.WindowType.WindowStaysOnTopHint:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        else:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.pet.setWindowFlags(flags)
        self.pet.show()
        self.refresh()
