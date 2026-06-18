import json
import math
import random
import threading
import time
import winsound
from dataclasses import dataclass, field

from .config import SETTINGS_FILE
from .utils import clamp, lerp


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
    mouse: list[float | bool] = field(default_factory=lambda: [180.0, 80.0, False])
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
    focus_threshold: float = 75.0
    resting_until: float = 0.0
    time_mode: str = "real"
    manual_minutes: float = 720.0
    fast_speed: float = 240.0
    circ_wake: float = 1.0
    circ_warm: float = 0.0
    sound_on: bool = False
    breath_high: bool = False
    menu_open: bool = False
    menu_lean: list[float] = field(default_factory=lambda: [0.0, 0.0])
    pointer_down_at: float = 0.0
    pointer_moved: float = 0.0
    last_pointer: list[float] = field(default_factory=lambda: [180.0, 180.0])
    frame_dt: float = 1 / 60

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
            "idle": Mood("待机 · idle", 1.00, 1.00, 0.06, 1.0, 0.9, 0, 23, 0, 0, "dots", 1.0, 0.12),
            "happy": Mood("开心 · happy", 1.13, 0.86, 0.12, 1.7, 2.3, -11, 27, 0.22, 0.5, "arc", 1.3, 0.30, fx="sparkle", bounce=1),
            "excited": Mood("兴奋 · excited", 1.18, 0.82, 0.16, 2.0, 3.4, -13, 28, 0.30, 0.4, "wide", 1.45, 0.40, fx="sparkle", bounce=1.5),
            "curious": Mood("好奇 · curious", 1.06, 0.96, 0.07, 1.3, 1.3, -5, 20, 0.12, 0.15, "wide", 1.05, 0.16, tilt=True, lean=True, core_gaze=True),
            "playful": Mood("调皮 · playful", 1.10, 0.90, 0.13, 1.5, 2.0, -7, 25, 0.18, 0.25, "arc", 1.2, 0.26, sway=True, bounce=1),
            "busy": Mood("紧绷 · busy", 0.97, 1.04, 0.05, 1.05, 2.8, -1, 19, -0.06, -0.3, "squint", 0.85, 0.34, jitter=True, core_drift=True),
            "thinking": Mood("思考 · thinking", 1.0, 1.0, 0.05, 0.95, 0.8, -2, 22, -0.04, -0.2, "squint", 0.9, 0.10, fx="think", core_drift=True),
            "calm": Mood("安宁 · breathe", 1.08, 0.95, 0.03, 1.25, 0.5, -3, 24, 0.05, 0.1, "lines", 1.15, 0.05, breathing=True),
            "sleepy": Mood("困倦 · sleepy", 0.88, 1.24, 0.025, 0.4, 0.35, 19, 25, -0.34, -0.5, "lines", 0.65, 0.07, fx="zzz", sag=True, sway=True),
            "surprised": Mood("惊讶 · surprised", 1.26, 0.74, 0.20, 2.1, 3.2, -17, 30, 0.34, 0.35, "huge", 1.6, 0.42, fx="burst", jitter=True),
            "await": Mood("在听 · ?", 1.06, 0.93, 0.08, 1.55, 1.9, -5, 25, 0.14, 0.12, "wide", 1.15, 0.24, fx="quest", tilt=True, lean=True, core_gaze=True),
            "ask": Mood("这个? · pick", 1.07, 0.92, 0.09, 1.60, 2.0, -6, 23, 0.16, 0.15, "wide", 1.15, 0.24, fx="quest", tilt=True, lean=True, sway=True, core_gaze=True),
            "config": Mood("设置 · tuning", 1.0, 1.0, 0.05, 1.25, 1.2, -2, 19, 0.04, -0.10, "squint", 1.0, 0.16, fx="orbit", core_drift=True),
            "work": Mood("工作 · focus", 0.99, 1.02, 0.05, 1.15, 1.6, -2, 20, 0.02, -0.15, "focus", 1.0, 0.18, lean=True, core_drift=True),
            "study": Mood("学习 · study", 1.02, 0.99, 0.05, 1.10, 1.0, -1, 21, 0.0, -0.05, "read", 0.95, 0.12, fx="think", core_gaze=True),
            "chat": Mood("倾听 · chat", 1.08, 0.92, 0.10, 1.50, 2.2, -6, 25, 0.18, 0.20, "wide", 1.20, 0.26, fx="wave", tilt=True, lean=True, core_gaze=True),
            "rest": Mood("休憩 · rest", 1.05, 1.02, 0.03, 1.05, 0.5, 3, 24, -0.05, 0.15, "lines", 1.0, 0.05, fx="steam", breathing=True, sway=True),
            "play": Mood("玩耍 · play", 1.14, 0.85, 0.15, 1.80, 2.6, -10, 27, 0.26, 0.35, "star", 1.35, 0.34, fx="sparkle", bounce=1.4, sway=True),
        }
        self.manual_moods = ["idle", "happy", "excited", "curious", "playful", "busy", "thinking", "calm", "sleepy", "surprised"]
        self.st = {
            "scale": 1.0,
            "squash": 1.0,
            "wobble": 0.06,
            "glow": 1.0,
            "breathe": 0.9,
            "lift": 0.0,
            "eye_gap": 23.0,
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
        if self.menu_open:
            return "await"
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
        self.frame_dt = dt
        self.t += dt
        if self.time_mode == "fast":
            self.manual_minutes = (self.manual_minutes + self.fast_speed * dt) % 1440
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
        if self.focus_time > self.focus_threshold and self.t - self.last_rest_at > 40 and self.t >= self.react_until:
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

        self.wander = [0.0, 0.0]

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
        if self.menu_open:
            hx = 180 + self.menu_lean[0]
            hy = 180 + self.st["lift"] + self.menu_lean[1]
        else:
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
                self.sparkles.append([self.pos[0] + (random.random() - 0.5) * self.current_radius * 1.6, self.pos[1] - self.current_radius * 0.6, 0, -30 - random.random() * 20, 1, 1.0 + random.random() * 1.5, False])
        if target.fx == "zzz":
            self.zzz_timer -= dt
            if self.zzz_timer <= 0:
                self.zzz_timer = 0.9
                self.sparkles.append([self.pos[0] + self.current_radius * 0.5, self.pos[1] - self.current_radius * 0.4, 7, -13, 1, 2.0, True])
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
