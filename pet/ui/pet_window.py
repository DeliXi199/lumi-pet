import math
import random
import time
from queue import Empty

from ..model import PetModel
from ..qt import QApplication, QPainter, QPoint, QPointF, QRectF, QTimer, QWidget, Qt
from ..utils import clamp
from .agent_panel import AgentPanel
from .control_panel import ControlPanel
from .pet_renderer import PetRendererMixin


class PetWindow(PetRendererMixin, QWidget):
    def __init__(self, model: PetModel, key_queue=None):
        super().__init__()
        self.model = model
        self.key_queue = key_queue
        self.panel = None
        self.agent_panel = None
        self.option_menu_open = False
        self.option_hover = -1
        self.option_menu_started = 0.0
        self.option_menu_anchor = None
        self.option_menu_positions = []
        self.bubble_text = ""
        self.bubble_started = 0.0
        self.bubble_until = 0.0
        self.idle_bubble_timer = 18.0 + random.random() * 10.0
        self.reply_lines = [
            "嗯嗯，我在听～",
            "这个想法不错！",
            "说说看，我都听着呢",
            "哈，有意思 ✨",
            "我懂你的意思",
            "陪着你，别急",
            "继续，我喜欢听",
            "收到！",
        ]
        self.option_items = [
            ("设置", "⚙️", "config", "打开设置，一起调一调吧～"),
            ("工作", "💼", "work", "进入工作模式，我陪你专注 💪"),
            ("学习", "📚", "study", "一起学习，慢慢想就好 📚"),
            ("AI 聊天", "💬", "chat", "我在听，来跟我聊聊吧～"),
            ("Agent", "⌘", "agent", "Agent 终端准备好了，代理会自动接上"),
            ("玩耍", "🎮", "play", "耶！陪你玩一会儿 🎉"),
        ]
        self.dragging_window = False
        self.press_pos = QPointF()
        self.last_global = QPoint()
        self.setWindowTitle("桌面宠物")
        self.setFixedSize(390, 390)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.setMouseTracking(True)
        self.stage = QRectF(15, 15, 360, 360)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)
        self.last = time.perf_counter()

    def tick(self):
        self.drain_global_keys()
        now = time.perf_counter()
        dt = min(now - self.last, 0.05)
        self.last = now
        self.model.update(dt)
        self.update_bubble(dt)
        self.update()
        if self.panel and self.panel.isVisible():
            self.panel.refresh()
        if self.agent_panel and self.agent_panel.isVisible():
            self.agent_panel.refresh()

    def drain_global_keys(self):
        if not self.key_queue:
            return
        drained = 0
        while drained < 64:
            try:
                self.key_queue.get_nowait()
            except Empty:
                break
            self.model.notify_typing()
            drained += 1

    def update_bubble(self, dt):
        if self.bubble_text and self.model.t >= self.bubble_until:
            self.bubble_text = ""
        if self.option_menu_open or self.bubble_text:
            return
        self.idle_bubble_timer -= dt
        if self.idle_bubble_timer <= 0:
            self.idle_bubble_timer = 16 + random.random() * 18
            phase = self.model.circadian(self.model.current_minutes())[2]
            time_lines = {
                "深夜": ["夜深了，早点休息呀 🌙", "这么晚还醒着？我陪你", "安静的深夜，适合发呆 ✨"],
                "清晨": ["早安～新的一天开始啦 ☀️", "清晨的光，刚刚好", "睡醒了吗？伸个懒腰吧"],
                "上午": ["上午好，状态不错哦", "趁现在精神好，加油！", "要不要定个小目标？"],
                "正午": ["中午啦，记得吃饭 🍚", "歇一会儿，养养神", "正午的光最暖"],
                "午后": ["午后有点犯困呢～", "来杯茶提提神？", "慢悠悠的下午 ✨"],
                "黄昏": ["黄昏好美，看一眼吧 🌆", "今天辛苦啦", "夕阳下，放慢一点"],
                "夜晚": ["晚上好，今天过得怎样？", "夜色温柔，放松点 🌙", "忙完了就早点休息呀"],
            }
            idle_lines = [
                "今天过得怎么样？",
                "要不要喝口水～",
                "我一直在这儿陪你",
                "发会儿呆也不错 ✨",
                "深呼吸，放松点",
                "需要我做点什么吗？",
            ]
            pool = time_lines.get(phase, idle_lines) if random.random() < 0.6 else idle_lines
            self.say(random.choice(pool), 3.2)

    def say(self, text, duration=3.2):
        self.bubble_text = text
        self.bubble_started = self.model.t
        self.bubble_until = self.model.t + duration * 2.8 + 3

    def open_panel(self):
        if self.panel is None:
            self.panel = ControlPanel(self.model, self)
        if not self.panel.isVisible():
            screen = QApplication.primaryScreen().availableGeometry()
            pos = QPoint(
                screen.left() + (screen.width() - self.panel.width()) // 2,
                screen.top() + (screen.height() - self.panel.height()) // 2,
            )
            self.panel.move(pos)
        self.panel.show()
        self.panel.raise_()
        self.panel.activateWindow()
        self.panel.refresh()

    def open_agent(self):
        if self.agent_panel is None:
            self.agent_panel = AgentPanel(self.model, self)
        self.agent_panel.showMaximized()
        self.agent_panel.raise_()
        self.agent_panel.activateWindow()
        self.agent_panel.refresh()

    def pet_center(self):
        return QPointF(self.stage.x() + self.model.pos[0], self.stage.y() + self.model.pos[1])

    def option_item_pos(self, index, radius=124, progress=1.0):
        center = self.option_menu_anchor if self.option_menu_anchor is not None else self.pet_center()
        if 0 <= index < len(self.option_menu_positions):
            target = self.option_menu_positions[index]
        else:
            angle = math.radians(-90 + index * 360 / len(self.option_items))
            target = QPointF(center.x() + math.cos(angle) * radius, center.y() + math.sin(angle) * radius)
        return QPointF(
            center.x() + (target.x() - center.x()) * progress,
            center.y() + (target.y() - center.y()) * progress,
        )

    def option_at(self, pos):
        for i, _item in enumerate(self.option_items):
            c = self.option_item_pos(i)
            if math.hypot(pos.x() - c.x(), pos.y() - c.y()) <= 34:
                return i
        return -1

    def open_option_menu(self):
        self.option_menu_anchor = self.pet_center()
        self.option_menu_positions = []
        for i in range(len(self.option_items)):
            angle = math.radians(-90 + i * 360 / len(self.option_items))
            self.option_menu_positions.append(
                QPointF(
                    self.option_menu_anchor.x() + math.cos(angle) * 124,
                    self.option_menu_anchor.y() + math.sin(angle) * 124,
                )
            )
        self.option_menu_open = True
        self.option_hover = -1
        self.option_menu_started = self.model.t
        self.dragging_window = False
        self.bubble_text = ""
        self.model.wander = [0.0, 0.0]
        self.model.menu_open = True
        self.model.menu_lean = [0.0, 0.0]
        self.model.last_interact = self.model.t
        self.model.react("await", 9999)
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def close_option_menu(self):
        self.option_menu_open = False
        self.option_hover = -1
        self.option_menu_anchor = None
        self.option_menu_positions = []
        self.model.menu_open = False
        self.model.menu_lean = [0.0, 0.0]
        self.setCursor(Qt.CursorShape.ArrowCursor)
        if self.model.react_mood in {"await", "ask"}:
            self.model.react_until = 0

    def toggle_option_menu(self):
        if self.option_menu_open:
            self.close_option_menu()
        else:
            self.open_option_menu()

    def perform_option(self, index):
        label, _icon, mood_key, message = self.option_items[index]
        self.close_option_menu()
        self.model.last_interact = self.model.t
        self.model.autopilot = False
        self.model.manual_mood = "work" if mood_key == "agent" else mood_key
        if label == "设置":
            self.say(message, 3.2)
            self.open_panel()
            return
        if mood_key == "agent":
            self.say(message, 3.2)
            self.open_agent()
            return
        if mood_key == "chat":
            self.open_panel()
            if self.panel:
                self.panel.focus_talk()
        if mood_key == "play":
            self.model.react("surprised", 0.5)
        self.say(message, 3.6)
        if mood_key == "play":
            self.model.sfx_chime()

    def submit_chat(self, text):
        self.model.autopilot = False
        self.model.manual_mood = "chat"
        self.model.last_interact = self.model.t
        self.model.react("happy", 0.7)
        self.say(random.choice(self.reply_lines) if text.strip() else "在听～", 3.6)

    def to_canvas(self, pos):
        return pos.x() - self.stage.x(), pos.y() - self.stage.y()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.toggle_option_menu()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self.option_menu_open:
            index = self.option_at(event.position())
            if index >= 0:
                self.perform_option(index)
            else:
                self.close_option_menu()
            return
        x, y = self.to_canvas(event.position())
        d = math.hypot(x - self.model.pos[0], y - self.model.pos[1])
        if d < self.model.current_radius * 1.15:
            self.dragging_window = True
            self.press_pos = event.position()
            self.last_global = event.globalPosition().toPoint()
            self.model.last_pointer = [x, y]
            self.model.pointer_moved = 0
            self.model.pointer_down_at = self.model.t
            self.model.last_interact = self.model.t
            self.setCursor(Qt.CursorShape.SizeAllCursor)

    def mouseMoveEvent(self, event):
        x, y = self.to_canvas(event.position())
        mv = math.hypot(x - self.model.last_pointer[0], y - self.model.last_pointer[1])
        self.model.pointer_speed = self.model.pointer_speed * 0.8 + mv * 0.2
        self.model.mouse = [x, y, 0 <= x <= 360 and 0 <= y <= 360]
        if self.option_menu_open:
            self.option_hover = self.option_at(event.position())
            if self.option_hover >= 0:
                angle = math.radians(-90 + self.option_hover * 360 / len(self.option_items))
                self.model.menu_lean = [math.cos(angle) * 23, math.sin(angle) * 23]
            else:
                self.model.menu_lean = [0.0, 0.0]
            self.setCursor(Qt.CursorShape.PointingHandCursor if self.option_hover >= 0 else Qt.CursorShape.ArrowCursor)
            self.model.last_pointer = [x, y]
            return
        if self.dragging_window:
            self.model.pointer_moved += mv
            if self.model.pointer_moved > 3.5:
                global_pos = event.globalPosition().toPoint()
                delta = global_pos - self.last_global
                self.move(self.pos() + delta)
                self.last_global = global_pos
        else:
            d = math.hypot(x - self.model.pos[0], y - self.model.pos[1])
            if d < self.model.current_radius:
                self.model.stroke_accum += mv
                self.model.last_interact = self.model.t
                if self.model.stroke_accum > 75:
                    self.model.react("happy", 1.4)
                    self.model.energy = min(1, self.model.energy + 0.3)
                    self.model.stroke_accum = 0
                    self.model.sfx_stroke()
        self.model.last_pointer = [x, y]

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            return
        if event.button() == Qt.MouseButton.LeftButton and self.dragging_window:
            if self.model.pointer_moved <= 3.5 and self.model.t - self.model.pointer_down_at < 0.3:
                self.model.react("surprised", 0.9)
                self.model.ripples.append([25.0, 0.6])
                self.model.vel[1] -= 210
                self.model.last_interact = self.model.t
                self.model.sfx_drop()
            self.dragging_window = False
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def leaveEvent(self, event):
        if not self.dragging_window:
            self.model.mouse[2] = False

    def keyPressEvent(self, event):
        if self.option_menu_open and event.key() == Qt.Key.Key_Escape:
            self.close_option_menu()
            event.accept()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        if self.option_menu_open:
            self.close_option_menu()
        super().focusOutEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.draw_pet(p)
        self.draw_option_menu(p)
        self.draw_bubble(p)
