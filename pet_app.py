import json
import math
import random
import sys
import threading
import time
import winsound
from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, SimpleQueue


ROOT = Path(__file__).resolve().parent
SETTINGS_FILE = ROOT / "pet_settings.json"


try:
    from PySide6.QtCore import QPoint, QPointF, QRectF, QSignalBlocker, Qt, QTimer
    from PySide6.QtGui import QAction, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF, QRadialGradient
    from PySide6.QtWidgets import (
        QApplication,
        QButtonGroup,
        QDialog,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QSlider,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
    try:
        from pynput import keyboard as pynput_keyboard
    except ImportError:
        pynput_keyboard = None
except ImportError:
    # Dependency fallback: the project still runs before PySide6 is installed.
    from desktop_pet import DesktopPet

    def main():
        self_test = "--self-test" in sys.argv
        smoke_test = "--smoke-test" in sys.argv
        DesktopPet(self_test=self_test, smoke_test=smoke_test).run()

    if __name__ == "__main__":
        main()
    raise SystemExit


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def lerp(a, b, k):
    return a + (b - a) * k


def color_mix(a, b, amount):
    amount = clamp(amount, 0.0, 1.0)
    return (
        int(a[0] + (b[0] - a[0]) * amount),
        int(a[1] + (b[1] - a[1]) * amount),
        int(a[2] + (b[2] - a[2]) * amount),
    )


@dataclass
class Theme:
    label: str
    base: tuple[int, int, int]
    accent: tuple[int, int, int]
    bg: tuple[str, str]


@dataclass
class Mood:
    label: str
    scale: float
    squash: float
    wobble: float
    glow: float
    breathe: float
    lift: float
    eye_gap: float
    tone: float
    temp: float
    eye_style: str
    core_size: float
    core_pulse: float
    fx: str = ""
    bounce: float = 0.0
    tilt: bool = False
    lean: bool = False
    sway: bool = False
    jitter: bool = False
    core_gaze: bool = False
    core_drift: bool = False
    breathing: bool = False
    sag: bool = False


@dataclass
class PetModel:
    themes: dict[str, Theme] = field(default_factory=dict)
    moods: dict[str, Mood] = field(default_factory=dict)
    manual_moods: list[str] = field(default_factory=list)
    theme_key: str = "moonlight"
    autopilot: bool = True
    manual_mood: str = "idle"
    auto_mood: str = "idle"
    shown_mood: str | None = None
    react_mood: str | None = None
    react_until: float = 0.0
    target_key: str = "idle"
    t: float = 0.0
    pos: list[float] = field(default_factory=lambda: [180.0, 180.0])
    vel: list[float] = field(default_factory=lambda: [0.0, 0.0])
    current_radius: float = 60.0
    mouse: list[float | bool] = field(default_factory=lambda: [180.0, 70.0, False])
    st: dict = field(default_factory=dict)
    energy: float = 0.7
    last_interact: float = -99.0
    stroke_accum: float = 0.0
    look_target: list[float] = field(default_factory=lambda: [0.0, 0.0])
    look_timer: float = 2.0
    perk_timer: float = 10.0
    wander_timer: float = 6.0
    wander: list[float] = field(default_factory=lambda: [0.0, 0.0])
    ripples: list[list[float]] = field(default_factory=list)
    sparkles: list[list[float | bool]] = field(default_factory=list)
    bursts: list[list[float]] = field(default_factory=list)
    blink_timer: float = 2.0
    blink: float = 0.0
    spark_timer: float = 0.0
    zzz_timer: float = 0.0
    key_times: list[float] = field(default_factory=list)
    last_key_at: float = -99.0
    typing_rate: float = 0.0
    busy_manual: float = 0.0
    pointer_speed: float = 0.0
    busy_level: float = 0.0
    focus_time: float = 0.0
    last_rest_at: float = -999.0
    resting_until: float = 0.0
    time_mode: str = "real"
    manual_minutes: float = 720.0
    circ_wake: float = 1.0
    circ_warm: float = 0.0
    sound_on: bool = False
    breath_high: bool = False

    def __post_init__(self):
        self.themes = {
            "moonlight": Theme("月光蓝", (160, 185, 255), (159, 180, 255), ("#14171d", "#0b0c10")),
            "mint": Theme("薄荷雾", (140, 205, 182), (143, 214, 189), ("#101a17", "#080f0d")),
            "haze": Theme("烟紫", (176, 150, 214), (182, 160, 224), ("#16121f", "#0c0a13")),
            "ink": Theme("墨水蓝", (122, 152, 212), (127, 160, 216), ("#0e1422", "#080b14")),
            "warmgray": Theme("月白暖灰", (214, 210, 196), (214, 210, 196), ("#16161a", "#0c0c0e")),
            "ember": Theme("炽橙", (232, 150, 108), (230, 150, 114), ("#1a120d", "#0f0a07")),
            "seafoam": Theme("深海青", (110, 196, 200), (116, 205, 209), ("#0c1a1c", "#070f10")),
            "rose": Theme("灰玫瑰", (224, 158, 168), (224, 158, 168), ("#1c1316", "#100a0c")),
        }
        self.moods = {
            "idle": Mood("待机 · idle", 1.00, 1.00, 0.06, 1.0, 0.9, 0, 46, 0, 0, "dots", 1.0, 0.12),
            "happy": Mood("开心 · happy", 1.13, 0.86, 0.12, 1.7, 2.3, -11, 54, 0.22, 0.5, "arc", 1.3, 0.30, fx="sparkle", bounce=1),
            "excited": Mood("兴奋 · excited", 1.18, 0.82, 0.16, 2.0, 3.4, -13, 56, 0.30, 0.4, "wide", 1.45, 0.40, fx="sparkle", bounce=1.5),
            "curious": Mood("好奇 · curious", 1.06, 0.96, 0.07, 1.3, 1.3, -5, 40, 0.12, 0.15, "wide", 1.05, 0.16, tilt=True, lean=True, core_gaze=True),
            "playful": Mood("调皮 · playful", 1.10, 0.90, 0.13, 1.5, 2.0, -7, 50, 0.18, 0.25, "arc", 1.2, 0.26, sway=True, bounce=1),
            "busy": Mood("紧绷 · busy", 0.97, 1.04, 0.05, 1.05, 2.8, -1, 38, -0.06, -0.3, "squint", 0.85, 0.34, jitter=True, core_drift=True),
            "thinking": Mood("思考 · thinking", 1.0, 1.0, 0.05, 0.95, 0.8, -2, 44, -0.04, -0.2, "squint", 0.9, 0.10, fx="think", core_drift=True),
            "calm": Mood("安宁 · breathe", 1.08, 0.95, 0.03, 1.25, 0.5, -3, 48, 0.05, 0.1, "lines", 1.15, 0.05, breathing=True),
            "sleepy": Mood("困倦 · sleepy", 0.88, 1.24, 0.025, 0.4, 0.35, 19, 50, -0.34, -0.5, "lines", 0.65, 0.07, fx="zzz", sag=True, sway=True),
            "surprised": Mood("惊讶 · surprised", 1.26, 0.74, 0.20, 2.1, 3.2, -17, 60, 0.34, 0.35, "huge", 1.6, 0.42, fx="burst", jitter=True),
        }
        self.manual_moods = ["idle", "happy", "excited", "curious", "playful", "busy", "thinking", "calm", "sleepy", "surprised"]
        self.st = {
            "scale": 1.0,
            "squash": 1.0,
            "wobble": 0.06,
            "glow": 1.0,
            "breathe": 0.9,
            "lift": 0.0,
            "eye_gap": 46.0,
            "tilt": 0.0,
            "hue": [160.0, 185.0, 255.0],
            "core_size": 1.0,
            "core_pulse": 0.12,
            "gx": 0.0,
            "gy": 0.0,
        }
        self.load_settings()

    def load_settings(self):
        if not SETTINGS_FILE.exists():
            return
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self.theme_key = data.get("theme_key", self.theme_key) if data.get("theme_key") in self.themes else self.theme_key
        self.autopilot = bool(data.get("autopilot", self.autopilot))
        self.manual_mood = data.get("manual_mood", self.manual_mood) if data.get("manual_mood") in self.moods else self.manual_mood
        self.time_mode = data.get("time_mode", self.time_mode) if data.get("time_mode") in {"real", "manual", "fast"} else self.time_mode
        self.manual_minutes = float(data.get("manual_minutes", self.manual_minutes))
        self.busy_manual = clamp(float(data.get("busy_manual", self.busy_manual)), 0, 1)

    def save_settings(self):
        data = {
            "theme_key": self.theme_key,
            "autopilot": self.autopilot,
            "manual_mood": self.manual_mood,
            "time_mode": self.time_mode,
            "manual_minutes": self.manual_minutes,
            "busy_manual": self.busy_manual,
        }
        SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def current_minutes(self):
        if self.time_mode == "real":
            now = time.localtime()
            return now.tm_hour * 60 + now.tm_min + now.tm_sec / 60
        return self.manual_minutes

    def circadian(self, mins):
        h = mins / 60
        frames = [
            (0, 0.12, 0.45),
            (5, 0.15, 0.42),
            (7, 0.55, 0.18),
            (9, 0.92, 0.05),
            (13, 1.0, -0.08),
            (17, 0.85, 0.12),
            (20, 0.55, 0.30),
            (22, 0.28, 0.40),
            (24, 0.12, 0.45),
        ]
        wake = 0.5
        warm = 0.0
        for a, b in zip(frames, frames[1:]):
            if a[0] <= h <= b[0]:
                f = (h - a[0]) / (b[0] - a[0])
                wake = lerp(a[1], b[1], f)
                warm = lerp(a[2], b[2], f)
                break
        phase = "深夜" if h < 5 else "清晨" if h < 8 else "上午" if h < 11 else "正午" if h < 14 else "午后" if h < 17 else "黄昏" if h < 20 else "夜晚" if h < 23 else "深夜"
        return wake, warm, phase

    def mood_color(self):
        base = self.themes[self.theme_key].base
        target = self.moods[self.target_key]
        f = 1 + target.tone
        tp = target.temp + self.circ_warm * 0.6
        return (
            int(clamp(base[0] * f + tp * 22, 0, 255)),
            int(clamp(base[1] * f + tp * 4, 0, 255)),
            int(clamp(base[2] * f - tp * 22, 0, 255)),
        )

    def effective_mood(self):
        if self.t < self.react_until and self.react_mood:
            return self.react_mood
        return self.auto_mood if self.autopilot else self.manual_mood

    def react(self, mood, duration):
        self.react_mood = mood
        self.react_until = self.t + duration

    def notify_typing(self):
        self.key_times.append(self.t)
        self.last_key_at = self.t
        self.last_interact = self.t

    def status_text(self):
        mins = self.current_minutes()
        h = int(mins // 60) % 24
        m = int(mins % 60)
        phase = self.circadian(mins)[2]
        mood_name = self.moods[self.effective_mood()].label.split(" · ")[0]
        fm = int(self.focus_time // 60)
        fs = int(self.focus_time % 60)
        return f"{h:02d}:{m:02d} · {phase} · 状态 {mood_name} · 专注 {fm}:{fs:02d}"

    def update(self, dt):
        self.t += dt
        if self.time_mode == "fast":
            self.manual_minutes = (self.manual_minutes + 240 * dt) % 1440
        mins = self.current_minutes()
        wake, warm, _ = self.circadian(mins)
        self.circ_wake = lerp(self.circ_wake, wake, 1 - math.pow(0.05, dt))
        self.circ_warm = lerp(self.circ_warm, warm, 1 - math.pow(0.05, dt))

        self.key_times = [k for k in self.key_times if self.t - k < 1.5]
        self.typing_rate = lerp(self.typing_rate, len(self.key_times), 1 - math.pow(0.02, dt))
        typing_now = self.t - self.last_key_at < 1.0
        derived = clamp(self.pointer_speed / 28, 0, 1) * 0.6 + clamp(self.typing_rate / 9, 0, 1) * 0.5
        self.busy_level = lerp(self.busy_level, max(self.busy_manual, derived), 1 - math.pow(0.1, dt))
        self.pointer_speed *= math.pow(0.05, dt)

        idle_for = self.t - self.last_interact
        wake_bias = (self.circ_wake - 0.5) * 0.12
        self.energy = clamp(self.energy + dt * ((0.22 if idle_for < 2 else -0.03) + wake_bias), 0, 1)
        if typing_now or idle_for < 1.5:
            self.focus_time += dt
        else:
            self.focus_time = max(0, self.focus_time - dt * 1.5)
        if self.focus_time > 75 and self.t - self.last_rest_at > 40 and self.t >= self.react_until:
            self.last_rest_at = self.t
            self.resting_until = self.t + 8
            self.react("calm", 8)
            self.focus_time = 0

        self.look_timer -= dt
        if self.look_timer <= 0:
            self.look_timer = 1.2 + random.random() * 3.2
            a = random.random() * math.tau
            r = 0 if random.random() < 0.4 else 2 + random.random() * 3.5
            self.look_target = [math.cos(a) * r, math.sin(a) * r * 0.7]

        self.wander_timer -= dt
        if self.wander_timer <= 0:
            self.wander_timer = 5 + random.random() * 7
            awake = self.energy > 0.4 and self.circ_wake > 0.4
            rad = 35 if awake else 9
            a = random.random() * math.tau
            self.wander = [math.cos(a) * rad * random.random(), math.sin(a) * rad * 0.5 * random.random()]

        if self.autopilot:
            d_mouse = math.hypot(self.mouse[0] - self.pos[0], self.mouse[1] - self.pos[1]) if self.mouse[2] else 9999
            if self.t < self.resting_until:
                self.auto_mood = "calm"
            elif typing_now and self.typing_rate > 5:
                self.auto_mood = "excited"
            elif typing_now:
                self.auto_mood = "happy"
            elif self.busy_level > 0.6:
                self.auto_mood = "busy"
            elif d_mouse < 100:
                self.auto_mood = "curious"
            elif self.circ_wake < 0.3 or idle_for > 14 or self.energy < 0.25:
                self.auto_mood = "sleepy"
            else:
                self.auto_mood = "idle"
            self.perk_timer -= dt
            if self.perk_timer <= 0:
                self.perk_timer = 9 + random.random() * 9
                if self.auto_mood == "idle" and self.t >= self.react_until:
                    self.react("curious" if random.random() < 0.5 else "playful", 1.4)

        mood_key = self.effective_mood()
        if mood_key != self.shown_mood:
            self.shown_mood = mood_key
            if self.moods[mood_key].fx == "burst":
                self.bursts = [[i / 10 * math.tau, 0.0, 1.0] for i in range(10)]
            if mood_key in {"happy", "excited"}:
                self.sfx_chime()
        self.target_key = mood_key
        target = self.moods[mood_key]

        k = 1 - math.pow(0.001, dt)
        s = self.st
        s["scale"] = lerp(s["scale"], target.scale, k)
        s["squash"] = lerp(s["squash"], target.squash, k)
        s["wobble"] = lerp(s["wobble"], target.wobble, k)
        s["glow"] = lerp(s["glow"], target.glow, k)
        s["breathe"] = lerp(s["breathe"], target.breathe, k)
        s["lift"] = lerp(s["lift"], target.lift, k)
        s["eye_gap"] = lerp(s["eye_gap"], target.eye_gap, k)
        s["tilt"] = lerp(s["tilt"], 0.16 if target.tilt else 0.0, k)
        s["core_size"] = lerp(s["core_size"], target.core_size, k)
        s["core_pulse"] = lerp(s["core_pulse"], target.core_pulse, k)
        mc = self.mood_color()
        s["hue"][0] = lerp(s["hue"][0], mc[0], k)
        s["hue"][1] = lerp(s["hue"][1], mc[1], k)
        s["hue"][2] = lerp(s["hue"][2], mc[2], k)

        self.physics(dt, target)
        self.update_particles(dt, target)
        self.blink_timer -= dt
        if self.blink_timer <= 0:
            self.blink = 1.0
            self.blink_timer = 2.4 + random.random() * 2.5
        if self.blink > 0:
            self.blink = max(0, self.blink - dt * 7)

    def physics(self, dt, target):
        hx = 180 + self.wander[0]
        hy = 180 + self.st["lift"] + self.wander[1]
        if target.bounce:
            hy += math.sin(self.t * 5) * -8 * target.bounce
        if target.sag:
            hy += 6 + math.sin(self.t * 0.7) * 3.5
        if target.sway:
            hx += math.sin(self.t * 0.9) * 10
        spring = 110
        damp = 10
        self.vel[0] += ((hx - self.pos[0]) * spring - self.vel[0] * damp) * dt
        self.vel[1] += ((hy - self.pos[1]) * spring - self.vel[1] * damp) * dt
        self.vel[0] = clamp(self.vel[0], -1500, 1500)
        self.vel[1] = clamp(self.vel[1], -1500, 1500)
        self.pos[0] += self.vel[0] * dt
        self.pos[1] += self.vel[1] * dt

    def update_particles(self, dt, target):
        self.stroke_accum = max(0, self.stroke_accum - dt * 120)
        for r in self.ripples[:]:
            r[0] += dt * 130
            r[1] -= dt * 0.9
            if r[1] <= 0:
                self.ripples.remove(r)
        for b in self.bursts[:]:
            b[1] += dt * 210
            b[2] -= dt * 1.6
            if b[2] <= 0:
                self.bursts.remove(b)
        if target.fx == "sparkle":
            self.spark_timer -= dt
            if self.spark_timer <= 0:
                self.spark_timer = 0.18
                self.sparkles.append([self.pos[0] + (random.random() - 0.5) * self.current_radius * 1.6, self.pos[1] - self.current_radius * 0.6, 0, -30 - random.random() * 20, 1, 1.2 + random.random() * 1.8, False])
        if target.fx == "zzz":
            self.zzz_timer -= dt
            if self.zzz_timer <= 0:
                self.zzz_timer = 0.9
                self.sparkles.append([self.pos[0] + self.current_radius * 0.5, self.pos[1] - self.current_radius * 0.4, 7, -13, 1, 2.6, True])
        for sp in self.sparkles[:]:
            sp[0] += sp[2] * dt
            sp[1] += sp[3] * dt
            sp[4] -= dt * (0.6 if sp[6] else 1.1)
            if sp[6]:
                sp[5] += dt * 3
            if sp[4] <= 0:
                self.sparkles.remove(sp)

    def play_tone(self, frequency, duration):
        if not self.sound_on:
            return

        def worker():
            try:
                winsound.Beep(int(frequency), int(duration))
            except RuntimeError:
                winsound.MessageBeep()

        threading.Thread(target=worker, daemon=True).start()

    def sfx_drop(self):
        self.play_tone(520, 110)
        self.play_tone(780, 90)

    def sfx_stroke(self):
        self.play_tone(330, 120)

    def sfx_chime(self):
        self.play_tone(660, 80)
        self.play_tone(880, 90)
        self.play_tone(1175, 100)

    def sfx_breath(self, rising):
        self.play_tone(300 if rising else 240, 140)


class PetWindow(QWidget):
    def __init__(self, model: PetModel, key_queue=None):
        super().__init__()
        self.model = model
        self.key_queue = key_queue
        self.panel = None
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
        self.update()
        if self.panel and self.panel.isVisible():
            self.panel.refresh()

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

    def to_canvas(self, pos):
        return pos.x() - self.stage.x(), pos.y() - self.stage.y()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.open_panel()
            return
        if event.button() != Qt.MouseButton.LeftButton:
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
        if self.dragging_window:
            self.model.pointer_moved += mv
            if self.model.pointer_moved > 7:
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
            self.open_panel()
            return
        if event.button() == Qt.MouseButton.LeftButton and self.dragging_window:
            if self.model.pointer_moved <= 7 and self.model.t - self.model.pointer_down_at < 0.3:
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

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.draw_pet(p)

    def draw_pet(self, p):
        m = self.model
        mood = m.moods[m.target_key]
        col = tuple(int(v) for v in m.st["hue"])
        sx = self.stage.x()
        sy = self.stage.y()
        render_glow = m.st["glow"] * (0.55 + 0.55 * m.circ_wake)
        breath = math.sin(m.t * m.st["breathe"] * 1.6) * 0.05 + 1
        breath_guide = 1.0
        breath_phase = 0.0
        if mood.breathing:
            breath_phase = math.sin(m.t * 0.7)
            breath_guide = 1 + breath_phase * 0.12
        m.current_radius = 60 * m.st["scale"] * breath_guide
        base_r = m.current_radius * breath
        jit = (0.5 + m.busy_level * 0.8) if mood.jitter else 0
        cx = sx + m.pos[0] + ((random.random() - 0.5) * 4.5 * jit if jit else 0)
        cy = sy + m.pos[1] + ((random.random() - 0.5) * 4.5 * jit if jit else 0)
        qcol = QColor(*col)

        self.radial(p, QPointF(cx, cy), base_r * 2.2, qcol, int(72 * render_glow))
        if mood.breathing:
            p.setPen(QPen(QColor(*col, 86), 2))
            r = base_r * (1.5 + breath_phase * 0.5)
            p.drawEllipse(QPointF(cx, cy), r, r)
            if breath_phase > 0.985 and not m.breath_high:
                m.breath_high = True
                m.sfx_breath(True)
            elif breath_phase < -0.985 and m.breath_high:
                m.breath_high = False
                m.sfx_breath(False)
        self.draw_ripples(p, cx, cy, qcol)
        self.draw_bursts(p, cx, cy, base_r, qcol)

        gx, gy = self.gaze(cx - sx, cy - sy, mood)
        m.st["gx"] = lerp(m.st["gx"], gx, 0.25)
        m.st["gy"] = lerp(m.st["gy"], gy, 0.25)
        path = self.body_path(cx, cy, base_r, mood)
        grad = QRadialGradient(QPointF(cx - base_r * 0.25, cy - base_r * 0.35), base_r * 1.35)
        grad.setColorAt(0, QColor(*color_mix(col, (255, 255, 255), 0.24), 236))
        grad.setColorAt(0.62, QColor(*col, 150))
        grad.setColorAt(1, QColor(*color_mix(col, (0, 0, 0), 0.38), 105))
        p.setBrush(grad)
        p.setPen(QPen(QColor(*col, int(90 * render_glow)), 3))
        p.drawPath(path)
        p.save()
        p.setClipPath(path)
        lum_x = cx
        lum_y = cy + base_r * 0.05
        if mood.core_gaze and m.mouse[2]:
            lum_x += m.st["gx"] * 0.6
            lum_y += m.st["gy"] * 0.6
        if mood.core_drift:
            lum_x += math.sin(m.t * 1.1) * base_r * 0.12
        self.radial(p, QPointF(lum_x, lum_y), base_r * (1.05 + 0.25 * m.st["core_size"]), QColor(255, 255, 255), int((18 + max(0, m.st["core_size"] - 0.8) * 94) * render_glow))
        p.restore()
        self.draw_eyes(p, mood, cx - m.st["eye_gap"] / 4 + m.st["gx"], cx + m.st["eye_gap"] / 4 + m.st["gx"], cy - 4 + m.st["gy"], qcol)
        self.draw_sparkles(p, sx, sy, cx, cy, base_r, qcol, mood)

    def body_path(self, cx, cy, base_r, mood):
        m = self.model
        sx_scale = m.st["squash"]
        sy_scale = 2 - m.st["squash"]
        tilt = m.st["tilt"]
        if mood.lean and m.mouse[2]:
            tilt += (m.mouse[0] - (cx - self.stage.x())) / 360 * 0.5
        if mood.sway:
            tilt += math.sin(m.t * 1.6) * 0.1
        cos_t = math.cos(tilt)
        sin_t = math.sin(tilt)
        points = []
        for i in range(64):
            ang = i / 64 * math.tau
            noise = math.sin(ang * 3 + m.t * 1.4) * m.st["wobble"] + math.sin(ang * 5 - m.t) * m.st["wobble"] * 0.5 + math.sin(ang * 2 + m.t * 0.6) * m.st["wobble"] * 0.7
            rr = base_r * (1 + noise)
            x = math.cos(ang) * rr * sx_scale
            y = math.sin(ang) * rr * (sy_scale * 0.5 + 0.5)
            points.append(QPointF(cx + x * cos_t - y * sin_t, cy + x * sin_t + y * cos_t))
        path = QPainterPath()
        path.addPolygon(QPolygonF(points))
        path.closeSubpath()
        return path

    def gaze(self, cx, cy, mood):
        m = self.model
        if m.mouse[2]:
            dx = m.mouse[0] - cx
            dy = m.mouse[1] - cy
            d = math.hypot(dx, dy) or 1
            amount = min(d / 150, 1) * (8 if mood.lean else 4.5)
            return dx / d * amount, dy / d * amount
        return m.look_target[0], m.look_target[1]

    def radial(self, p, center, radius, color, alpha):
        if alpha <= 0:
            return
        grad = QRadialGradient(center, radius)
        grad.setColorAt(0, QColor(color.red(), color.green(), color.blue(), clamp(alpha, 0, 255)))
        grad.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawEllipse(center, radius, radius)

    def draw_ripples(self, p, cx, cy, col):
        for r, a in self.model.ripples:
            p.setPen(QPen(QColor(col.red(), col.green(), col.blue(), int(clamp(a, 0, 1) * 160)), 1.8))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), r, r)

    def draw_bursts(self, p, cx, cy, base_r, col):
        for ang, length, a in self.model.bursts:
            length = min(length, 30)
            p.setPen(QPen(QColor(col.red(), col.green(), col.blue(), int(clamp(a, 0, 1) * 190)), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(cx + math.cos(ang) * base_r * 1.05, cy + math.sin(ang) * base_r * 1.05), QPointF(cx + math.cos(ang) * (base_r * 1.05 + length), cy + math.sin(ang) * (base_r * 1.05 + length)))

    def draw_eyes(self, p, mood, lx, rx, ey, col):
        blink = 1 - self.model.blink
        if mood.eye_style == "arc":
            self.arc_eye(p, lx, ey)
            self.arc_eye(p, rx, ey)
        elif mood.eye_style == "lines":
            self.line_eye(p, lx, ey, 8)
            self.line_eye(p, rx, ey, 8)
        elif mood.eye_style == "squint":
            self.glow_dot(p, lx, ey, 3, 4 * blink, col)
            self.line_eye(p, rx, ey - 1, 7.5)
        else:
            size = {"dots": (3.5, 6.5), "wide": (6.5, 7), "huge": (9, 9)}.get(mood.eye_style, (3.5, 6.5))
            self.glow_dot(p, lx, ey, size[0], size[1] * blink, col)
            self.glow_dot(p, rx, ey, size[0], size[1] * blink, col)

    def glow_dot(self, p, x, y, rx, ry, col):
        self.radial(p, QPointF(x, y), max(rx, ry) * 2.2, col, 120)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 245))
        p.drawEllipse(QPointF(x, y), max(rx, 0.8), max(ry, 0.7))

    def arc_eye(self, p, x, y):
        p.setPen(QPen(QColor(255, 255, 255, 245), 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        path = QPainterPath()
        for i in range(18):
            a = math.radians(205 + 130 * i / 17)
            point = QPointF(x + math.cos(a) * 5.5, y + 2 + math.sin(a) * 5.5)
            if i == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)
        p.drawPath(path)

    def line_eye(self, p, x, y, w):
        p.setPen(QPen(QColor(255, 255, 255, 245), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(x - w / 2, y), QPointF(x + w / 2, y))

    def draw_sparkles(self, p, sx, sy, cx, cy, base_r, col, mood):
        p.setPen(Qt.PenStyle.NoPen)
        for x, y, vx, vy, a, size, grow in self.model.sparkles:
            p.setBrush(QColor(col.red(), col.green(), col.blue(), int(clamp(a, 0, 1) * 220)))
            p.drawEllipse(QPointF(sx + x, sy + y), size, size)
        if mood.fx == "think":
            for i in range(3):
                a = self.model.t * 1.5 + i * 2.1
                p.setBrush(QColor(col.red(), col.green(), col.blue(), 150 - i * 28))
                p.drawEllipse(QPointF(cx + math.cos(a) * base_r * 1.5, cy - base_r + math.sin(a) * 5 - i * 3), max(2.2 - i * 0.4, 0.5), max(2.2 - i * 0.4, 0.5))


class CloseButton(QPushButton):
    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self.setFixedSize(34, 34)
        self.setText("")
        self.setFlat(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("关闭")

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        theme = self.model.themes[self.model.theme_key]
        base = theme.base
        accent = theme.accent
        if self.isDown():
            fill = color_mix(accent, (18, 22, 32), 0.35)
            border = color_mix(accent, (255, 255, 255), 0.45)
            mark = (255, 255, 255)
        elif self.underMouse():
            fill = color_mix(accent, (34, 40, 56), 0.28)
            border = color_mix(accent, (255, 255, 255), 0.62)
            mark = color_mix(accent, (255, 255, 255), 0.82)
        else:
            fill = color_mix(base, (24, 28, 38), 0.72)
            border = color_mix(accent, (110, 126, 166), 0.42)
            mark = color_mix(accent, (255, 255, 255), 0.65)

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(4, 4, self.width() - 8, self.height() - 8)
        p.setPen(QPen(QColor(*border), 1.4))
        p.setBrush(QColor(*fill))
        p.drawEllipse(rect)
        p.setPen(QPen(QColor(*mark), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(13, 13), QPointF(21, 21))
        p.drawLine(QPointF(21, 13), QPointF(13, 21))


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
        self.talk.setPlaceholderText("在这里打字，宠物会感知你的节奏")
        self.talk.textChanged.connect(self.model.notify_typing)
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
        hint = QLabel("左键拖动宠物移动 · 点一下是戳 · 身上来回划是抚摸 · 右键宠物打开控制台")
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
            self.model.manual_minutes = value
            self.model.time_mode = "manual"
            self.model.save_settings()
            self.refresh()

    def set_time_mode(self, mode):
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


class AppKeyFilter(QWidget):
    def __init__(self, model):
        super().__init__()
        self.model = model

    def eventFilter(self, obj, event):
        if event.type().name in {"KeyPress", "ShortcutOverride"}:
            self.model.notify_typing()
        return False


def run_qt(self_test=False, smoke_test=False):
    app = QApplication(sys.argv)
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
        QTimer.singleShot(1000, app.quit)
    if self_test:
        for _ in range(6):
            model.update(1 / 30)
        print(f"self-test ok: qt=True moods={len(model.moods)} themes={len(model.themes)}")
        return 0
    return app.exec()


def main():
    sys.exit(run_qt("--self-test" in sys.argv, "--smoke-test" in sys.argv))


if __name__ == "__main__":
    main()
