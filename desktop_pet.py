import ctypes
import math
import random
import sys
import threading
import time
import winsound
from ctypes import wintypes


user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32
comctl32 = ctypes.windll.comctl32

LRESULT = ctypes.c_ssize_t
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, WPARAM, LPARAM)
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, WPARAM, LPARAM)
HANDLE = wintypes.HANDLE

WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_CHILD = 0x40000000
WS_OVERLAPPEDWINDOW = 0x00CF0000
WS_EX_LAYERED = 0x00080000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_CLIENTEDGE = 0x00000200
WS_TABSTOP = 0x00010000
WS_VSCROLL = 0x00200000
ES_MULTILINE = 0x0004
ES_AUTOVSCROLL = 0x0040
BS_PUSHBUTTON = 0x00000000
SS_LEFT = 0x00000000
SW_SHOW = 5
SW_HIDE = 0
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2

WM_CREATE = 0x0001
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_COMMAND = 0x0111
WM_TIMER = 0x0113
WM_HSCROLL = 0x0114
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MOUSELEAVE = 0x02A3
WM_NCDESTROY = 0x0082
BN_CLICKED = 0
EN_CHANGE = 0x0300

WM_USER = 0x0400
TBM_GETPOS = WM_USER
TBM_SETPOS = WM_USER + 5
TBM_SETRANGE = WM_USER + 6
TBM_SETTICFREQ = WM_USER + 20
TBS_AUTOTICKS = 0x0001

WH_KEYBOARD_LL = 13
HC_ACTION = 0

ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0
AC_SRC_ALPHA = 1
DIB_RGB_COLORS = 0
BI_RGB = 0

IDC_ARROW = 32512
IDC_SIZEALL = 32646

ID_AUTO = 1000
ID_MOOD_BASE = 1010
ID_THEME_BASE = 1100
ID_SOUND = 1200
ID_REAL = 1201
ID_FAST = 1202
ID_TOPMOST = 1203
ID_HIDE = 1204
ID_QUIT = 1205
ID_TALK = 1300
ID_TIME = 1400
ID_BUSY = 1401


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_byte),
        ("BlendFlags", ctypes.c_byte),
        ("SourceConstantAlpha", ctypes.c_byte),
        ("AlphaFormat", ctypes.c_byte),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class RGBQUAD(ctypes.Structure):
    _fields_ = [
        ("rgbBlue", ctypes.c_byte),
        ("rgbGreen", ctypes.c_byte),
        ("rgbRed", ctypes.c_byte),
        ("rgbReserved", ctypes.c_byte),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", RGBQUAD * 1)]


class WNDCLASS(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", HANDLE),
        ("hCursor", HANDLE),
        ("hbrBackground", HANDLE),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", WPARAM),
        ("lParam", LPARAM),
        ("time", wintypes.DWORD),
        ("pt", POINT),
    ]


class TRACKMOUSEEVENT(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("hwndTrack", wintypes.HWND),
        ("dwHoverTime", wintypes.DWORD),
    ]


user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM, LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASS)]
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    HANDLE,
    HANDLE,
    HANDLE,
    HANDLE,
]
user32.CreateWindowExW.restype = wintypes.HWND
user32.SetWindowLongPtrW.restype = LRESULT
user32.GetWindowLongPtrW.restype = LRESULT
user32.SendMessageW.argtypes = [HANDLE, wintypes.UINT, WPARAM, LPARAM]
user32.SendMessageW.restype = LRESULT
user32.GetDC.argtypes = [HANDLE]
user32.GetDC.restype = HANDLE
user32.SetTimer.argtypes = [HANDLE, WPARAM, wintypes.UINT, HANDLE]
user32.SetTimer.restype = WPARAM
user32.SetWindowPos.argtypes = [HANDLE, HANDLE, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.GetWindowRect.argtypes = [HANDLE, ctypes.POINTER(wintypes.RECT)]
user32.UpdateLayeredWindow.argtypes = [
    HANDLE,
    HANDLE,
    ctypes.POINTER(POINT),
    ctypes.POINTER(SIZE),
    HANDLE,
    ctypes.POINTER(POINT),
    wintypes.DWORD,
    ctypes.POINTER(BLENDFUNCTION),
    wintypes.DWORD,
]
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, HANDLE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = HANDLE
user32.CallNextHookEx.argtypes = [HANDLE, ctypes.c_int, WPARAM, LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = [HANDLE]
gdi32.CreateCompatibleDC.argtypes = [HANDLE]
gdi32.CreateDIBSection.restype = HANDLE
gdi32.CreateDIBSection.argtypes = [HANDLE, ctypes.POINTER(BITMAPINFO), wintypes.UINT, ctypes.POINTER(ctypes.c_void_p), HANDLE, wintypes.DWORD]
gdi32.CreateCompatibleDC.restype = HANDLE
gdi32.SelectObject.restype = HANDLE
gdi32.SelectObject.argtypes = [HANDLE, HANDLE]
gdi32.GetStockObject.argtypes = [ctypes.c_int]
gdi32.GetStockObject.restype = HANDLE
kernel32.GetModuleHandleW.restype = wintypes.HMODULE


def loword(value):
    return int(value) & 0xFFFF


def hiword(value):
    return (int(value) >> 16) & 0xFFFF


def signed_loword(value):
    n = loword(value)
    return n - 0x10000 if n & 0x8000 else n


def signed_hiword(value):
    n = hiword(value)
    return n - 0x10000 if n & 0x8000 else n


def clamp(value, minimum, maximum):
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


def lerp(a, b, k):
    return a + (b - a) * k


def mix_color(a, b, amount):
    amount = clamp(amount, 0.0, 1.0)
    return (
        int(a[0] + (b[0] - a[0]) * amount),
        int(a[1] + (b[1] - a[1]) * amount),
        int(a[2] + (b[2] - a[2]) * amount),
    )


class Mood:
    def __init__(
        self,
        label,
        scale,
        squash,
        wobble,
        glow,
        breathe,
        lift,
        eye_gap,
        tone,
        temp,
        eye_style,
        core_size,
        core_pulse,
        **flags,
    ):
        self.label = label
        self.scale = scale
        self.squash = squash
        self.wobble = wobble
        self.glow = glow
        self.breathe = breathe
        self.lift = lift
        self.eye_gap = eye_gap
        self.tone = tone
        self.temp = temp
        self.eye_style = eye_style
        self.core_size = core_size
        self.core_pulse = core_pulse
        self.fx = flags.get("fx", "")
        self.bounce = flags.get("bounce", 0.0)
        self.tilt = flags.get("tilt", False)
        self.lean = flags.get("lean", False)
        self.sway = flags.get("sway", False)
        self.jitter = flags.get("jitter", False)
        self.core_gaze = flags.get("core_gaze", False)
        self.core_drift = flags.get("core_drift", False)
        self.breathing = flags.get("breathing", False)
        self.sag = flags.get("sag", False)


class DesktopPet:
    width = 380
    height = 396
    canvas_x = 10
    canvas_y = 18
    canvas_w = 360
    canvas_h = 360
    home_x = 180.0
    home_y = 180.0

    def __init__(self, self_test=False, smoke_test=False):
        self.self_test = self_test
        self.smoke_test = smoke_test
        self.hinst = kernel32.GetModuleHandleW(None)
        self.pet_wndproc = WNDPROC(self._pet_wndproc)
        self.console_wndproc = WNDPROC(self._console_wndproc)
        self.hwnd = None
        self.console_hwnd = None
        self.hook = None
        self.hook_proc = None

        self.themes = {
            "moonlight": ("月光蓝", (160, 185, 255), (159, 180, 255)),
            "mint": ("薄荷雾", (140, 205, 182), (143, 214, 189)),
            "haze": ("烟紫", (176, 150, 214), (182, 160, 224)),
            "ink": ("墨水蓝", (122, 152, 212), (127, 160, 216)),
            "warmgray": ("月白暖灰", (214, 210, 196), (214, 210, 196)),
            "ember": ("炽橙", (232, 150, 108), (230, 150, 114)),
            "seafoam": ("深海青", (110, 196, 200), (116, 205, 209)),
            "rose": ("灰玫瑰", (224, 158, 168), (224, 158, 168)),
        }
        self.theme_keys = list(self.themes.keys())
        self.theme_key = "moonlight"

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
        self.autopilot = True
        self.manual_mood = "idle"
        self.auto_mood = "idle"
        self.shown_mood = None
        self.react_mood = None
        self.react_until = 0.0
        self.target = self.moods["idle"]

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
        self.pos = [self.home_x, self.home_y]
        self.vel = [0.0, 0.0]
        self.current_radius = 60.0
        self.pressing = False
        self.dragging = False
        self.pointer_down_at = 0.0
        self.pointer_moved = 0.0
        self.last_pointer = [self.home_x, self.home_y]
        self.last_screen = [0, 0]
        self.mouse = [self.home_x, self.home_y - 100, False]
        self.energy = 0.7
        self.last_interact = -99.0
        self.stroke_accum = 0.0
        self.look_target = [0.0, 0.0]
        self.look_timer = 2.0
        self.perk_timer = 10.0
        self.wander_timer = 6.0
        self.wander = [0.0, 0.0]
        self.ripples = []
        self.sparkles = []
        self.bursts = []
        self.t = 0.0
        self.blink_timer = 2.0
        self.blink = 0.0
        self.spark_timer = 0.0
        self.zzz_timer = 0.0
        self.key_times = []
        self.last_key_at = -99.0
        self.typing_rate = 0.0
        self.busy_manual = 0.0
        self.pointer_speed = 0.0
        self.busy_level = 0.0
        self.focus_time = 0.0
        self.last_rest_at = -999.0
        self.resting_until = 0.0
        self.time_mode = "real"
        self.manual_minutes = 720.0
        self.fast_speed = 240.0
        self.circ_wake = 1.0
        self.circ_warm = 0.0
        self.sound_on = False
        self.topmost = True
        self.last = time.perf_counter()
        self.breath_high = False
        self.bits = None
        self.pixels = None
        self.hdc_screen = None
        self.hdc_mem = None
        self.hbitmap = None
        self.old_bitmap = None
        self.controls = {}

    def run(self):
        if self.self_test:
            self._create_dib_only()
            for _ in range(5):
                self.update(1 / 30)
                self.render()
            nonzero = sum(1 for p in self.pixels if p)
            print(f"self-test ok: nonzero_pixels={nonzero}, moods={len(self.moods)}, themes={len(self.themes)}")
            return

        self.register_classes()
        self.create_pet_window()
        self.create_dib()
        self.install_keyboard_hook()
        user32.SetTimer(self.hwnd, 1, 33, None)
        self.render()
        user32.ShowWindow(self.hwnd, SW_SHOW)
        if self.smoke_test:
            self.show_console()
            user32.SetTimer(self.hwnd, 2, 900, None)

        msg = MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def register_classes(self):
        cursor = user32.LoadCursorW(None, IDC_ARROW)
        wc = WNDCLASS()
        wc.lpfnWndProc = self.pet_wndproc
        wc.hInstance = self.hinst
        wc.hCursor = cursor
        wc.lpszClassName = "PythonDesktopLightPet"
        if not user32.RegisterClassW(ctypes.byref(wc)):
            pass

        cwc = WNDCLASS()
        cwc.lpfnWndProc = self.console_wndproc
        cwc.hInstance = self.hinst
        cwc.hCursor = cursor
        cwc.hbrBackground = gdi32.GetStockObject(0)
        cwc.lpszClassName = "PythonDesktopLightPetConsole"
        if not user32.RegisterClassW(ctypes.byref(cwc)):
            pass

    def create_pet_window(self):
        work_w = user32.GetSystemMetrics(0)
        work_h = user32.GetSystemMetrics(1)
        x = max(20, work_w - self.width - 58)
        y = max(20, work_h - self.height - 70)
        exstyle = WS_EX_LAYERED | WS_EX_TOOLWINDOW | (WS_EX_TOPMOST if self.topmost else 0)
        self.hwnd = user32.CreateWindowExW(
            exstyle,
            "PythonDesktopLightPet",
            "桌面宠物",
            WS_POPUP | WS_VISIBLE,
            x,
            y,
            self.width,
            self.height,
            None,
            None,
            self.hinst,
            None,
        )
        if not self.hwnd:
            raise ctypes.WinError()

    def create_dib(self):
        self.hdc_screen = user32.GetDC(None)
        self.hdc_mem = gdi32.CreateCompatibleDC(self.hdc_screen)
        self._create_dib_core()
        self.old_bitmap = gdi32.SelectObject(self.hdc_mem, self.hbitmap)

    def _create_dib_only(self):
        self._create_dib_core()

    def _create_dib_core(self):
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = self.width
        bmi.bmiHeader.biHeight = -self.height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB
        bits = ctypes.c_void_p()
        self.hbitmap = gdi32.CreateDIBSection(None, ctypes.byref(bmi), DIB_RGB_COLORS, ctypes.byref(bits), None, 0)
        if not self.hbitmap or not bits.value:
            raise ctypes.WinError()
        self.bits = bits
        arr_type = ctypes.c_uint32 * (self.width * self.height)
        self.pixels = arr_type.from_address(bits.value)

    def install_keyboard_hook(self):
        def hook_proc(n_code, w_param, l_param):
            if n_code == HC_ACTION and w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
                self.notify_typing()
            return user32.CallNextHookEx(self.hook, n_code, w_param, l_param)

        self.hook_proc = HOOKPROC(hook_proc)
        self.hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self.hook_proc, self.hinst, 0)

    def uninstall_keyboard_hook(self):
        if self.hook:
            user32.UnhookWindowsHookEx(self.hook)
            self.hook = None

    def _pet_wndproc(self, hwnd, msg, w_param, l_param):
        if msg == WM_TIMER:
            if int(w_param) == 2:
                user32.DestroyWindow(hwnd)
                return 0
            now = time.perf_counter()
            dt = min(now - self.last, 0.05)
            self.last = now
            self.update(dt)
            self.render()
            return 0
        if msg == WM_MOUSEMOVE:
            self.on_mouse_move(signed_loword(l_param), signed_hiword(l_param))
            return 0
        if msg == WM_LBUTTONDOWN:
            self.on_left_down(signed_loword(l_param), signed_hiword(l_param))
            return 0
        if msg == WM_LBUTTONUP:
            self.on_left_up(signed_loword(l_param), signed_hiword(l_param))
            return 0
        if msg in (WM_RBUTTONDOWN, WM_RBUTTONUP):
            self.show_console()
            return 0
        if msg == WM_MOUSELEAVE:
            if not self.pressing:
                self.mouse[2] = False
            return 0
        if msg == WM_KEYDOWN:
            self.notify_typing()
            return 0
        if msg == WM_DESTROY:
            self.uninstall_keyboard_hook()
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, w_param, l_param)

    def _console_wndproc(self, hwnd, msg, w_param, l_param):
        if msg == WM_CREATE:
            self.build_console_controls(hwnd)
            return 0
        if msg == WM_COMMAND:
            cid = loword(w_param)
            code = hiword(w_param)
            if code == BN_CLICKED:
                self.handle_button(cid)
            elif cid == ID_TALK and code == EN_CHANGE:
                self.notify_typing()
            return 0
        if msg == WM_HSCROLL:
            source = wintypes.HWND(l_param).value
            if source == self.controls.get(ID_TIME):
                value = user32.SendMessageW(source, TBM_GETPOS, 0, 0)
                self.manual_minutes = float(value)
                self.time_mode = "manual"
                self.update_console()
            elif source == self.controls.get(ID_BUSY):
                value = user32.SendMessageW(source, TBM_GETPOS, 0, 0)
                self.busy_manual = value / 100.0
                self.update_console()
            return 0
        if msg == WM_CLOSE:
            user32.ShowWindow(hwnd, SW_HIDE)
            return 0
        if msg == WM_NCDESTROY:
            if hwnd == self.console_hwnd:
                self.console_hwnd = None
            return 0
        return user32.DefWindowProcW(hwnd, msg, w_param, l_param)

    def show_console(self):
        if not self.console_hwnd:
            x = self.get_window_rect()[2] + 12
            y = self.get_window_rect()[1] + 18
            screen_w = user32.GetSystemMetrics(0)
            screen_h = user32.GetSystemMetrics(1)
            if x + 560 > screen_w:
                x = max(10, self.get_window_rect()[0] - 560 - 12)
            if y + 620 > screen_h:
                y = max(10, screen_h - 630)
            self.console_hwnd = user32.CreateWindowExW(
                WS_EX_TOPMOST | WS_EX_APPWINDOW,
                "PythonDesktopLightPetConsole",
                "宠物控制台",
                WS_OVERLAPPEDWINDOW | WS_VISIBLE,
                x,
                y,
                560,
                620,
                None,
                None,
                self.hinst,
                None,
            )
        user32.ShowWindow(self.console_hwnd, SW_SHOW)
        user32.SetForegroundWindow(self.console_hwnd)
        self.update_console()

    def build_console_controls(self, hwnd):
        comctl32.InitCommonControls()
        y = 14
        self.add_static(hwnd, "宠物控制台", 16, y, 500, 26)
        y += 30
        self.controls["status"] = self.add_static(hwnd, "", 16, y, 510, 22)
        y += 34
        self.add_static(hwnd, "打字感知", 16, y, 120, 20)
        y += 22
        self.controls[ID_TALK] = self.add_control(
            hwnd,
            "EDIT",
            "",
            WS_CHILD | WS_VISIBLE | WS_TABSTOP | ES_MULTILINE | ES_AUTOVSCROLL | WS_VSCROLL,
            WS_EX_CLIENTEDGE,
            16,
            y,
            510,
            64,
            ID_TALK,
        )
        y += 78
        self.add_static(hwnd, "神态 Mood", 16, y, 160, 20)
        y += 24
        x = 16
        self.controls[ID_AUTO] = self.add_button(hwnd, "自动", x, y, ID_AUTO)
        x += 68
        for i, key in enumerate(self.manual_moods):
            if x > 455:
                x = 16
                y += 34
            cid = ID_MOOD_BASE + i
            label = self.moods[key].label.split(" · ")[0]
            self.controls[cid] = self.add_button(hwnd, label, x, y, cid)
            x += 74
        y += 46
        self.add_static(hwnd, "配色 Palette", 16, y, 160, 20)
        y += 24
        x = 16
        for i, key in enumerate(self.theme_keys):
            if x > 455:
                x = 16
                y += 34
            cid = ID_THEME_BASE + i
            self.controls[cid] = self.add_button(hwnd, self.themes[key][0], x, y, cid, width=86)
            x += 92
        y += 48
        self.controls["time_label"] = self.add_static(hwnd, "", 16, y, 510, 22)
        y += 22
        self.controls[ID_TIME] = self.add_control(hwnd, "msctls_trackbar32", "", WS_CHILD | WS_VISIBLE | TBS_AUTOTICKS, 0, 16, y, 510, 38, ID_TIME)
        user32.SendMessageW(self.controls[ID_TIME], TBM_SETRANGE, 1, (1440 << 16) | 0)
        user32.SendMessageW(self.controls[ID_TIME], TBM_SETTICFREQ, 120, 0)
        y += 46
        self.controls["busy_label"] = self.add_static(hwnd, "", 16, y, 510, 22)
        y += 22
        self.controls[ID_BUSY] = self.add_control(hwnd, "msctls_trackbar32", "", WS_CHILD | WS_VISIBLE | TBS_AUTOTICKS, 0, 16, y, 510, 38, ID_BUSY)
        user32.SendMessageW(self.controls[ID_BUSY], TBM_SETRANGE, 1, (100 << 16) | 0)
        user32.SendMessageW(self.controls[ID_BUSY], TBM_SETTICFREQ, 10, 0)
        y += 52
        self.controls[ID_SOUND] = self.add_button(hwnd, "静音中", 16, y, ID_SOUND, width=82)
        self.controls[ID_REAL] = self.add_button(hwnd, "真实时间", 106, y, ID_REAL, width=92)
        self.controls[ID_FAST] = self.add_button(hwnd, "加速一天", 206, y, ID_FAST, width=92)
        self.controls[ID_TOPMOST] = self.add_button(hwnd, "取消置顶", 306, y, ID_TOPMOST, width=92)
        self.controls[ID_HIDE] = self.add_button(hwnd, "隐藏", 406, y, ID_HIDE, width=60)
        self.controls[ID_QUIT] = self.add_button(hwnd, "关闭宠物", 16, y + 42, ID_QUIT, width=92)
        self.add_static(hwnd, "左键拖动宠物移动 · 点一下是戳 · 身上来回划是抚摸 · 右键宠物打开控制台", 116, y + 46, 410, 38)

    def add_control(self, parent, cls, text, style, exstyle, x, y, w, h, cid):
        hwnd = user32.CreateWindowExW(exstyle, cls, text, style, x, y, w, h, parent, cid, self.hinst, None)
        font = gdi32.GetStockObject(17)
        user32.SendMessageW(hwnd, 0x0030, font, True)
        return hwnd

    def add_static(self, parent, text, x, y, w, h):
        hwnd = user32.CreateWindowExW(0, "STATIC", text, WS_CHILD | WS_VISIBLE | SS_LEFT, x, y, w, h, parent, 0, self.hinst, None)
        font = gdi32.GetStockObject(17)
        user32.SendMessageW(hwnd, 0x0030, font, True)
        return hwnd

    def add_button(self, parent, text, x, y, cid, width=66):
        return self.add_control(parent, "BUTTON", text, WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_PUSHBUTTON, 0, x, y, width, 28, cid)

    def handle_button(self, cid):
        if cid == ID_AUTO:
            self.autopilot = True
        elif ID_MOOD_BASE <= cid < ID_MOOD_BASE + len(self.manual_moods):
            self.autopilot = False
            self.manual_mood = self.manual_moods[cid - ID_MOOD_BASE]
            self.last_interact = self.t
        elif ID_THEME_BASE <= cid < ID_THEME_BASE + len(self.theme_keys):
            self.theme_key = self.theme_keys[cid - ID_THEME_BASE]
        elif cid == ID_SOUND:
            self.sound_on = not self.sound_on
            if self.sound_on:
                self.sfx_chime()
        elif cid == ID_REAL:
            self.time_mode = "real"
        elif cid == ID_FAST:
            self.time_mode = "fast" if self.time_mode != "fast" else "manual"
        elif cid == ID_TOPMOST:
            self.topmost = not self.topmost
            user32.SetWindowPos(self.hwnd, HWND_TOPMOST if self.topmost else HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
            if self.console_hwnd:
                user32.SetWindowPos(self.console_hwnd, HWND_TOPMOST if self.topmost else HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
        elif cid == ID_HIDE:
            if self.console_hwnd:
                user32.ShowWindow(self.console_hwnd, SW_HIDE)
        elif cid == ID_QUIT:
            user32.DestroyWindow(self.hwnd)
        self.update_console()

    def update_console(self):
        if not self.console_hwnd:
            return
        self.set_text("status", self.status_text())
        mode = "跟随真实" if self.time_mode == "real" else ("加速演示" if self.time_mode == "fast" else "手动")
        self.set_text("time_label", f"时间 / 昼夜：{mode}")
        self.set_text("busy_label", f"系统繁忙度：{round(self.busy_manual * 100)}%")
        slider_mins = int(self.current_minutes() if self.time_mode == "real" else self.manual_minutes)
        user32.SendMessageW(self.controls[ID_TIME], TBM_SETPOS, 1, int(clamp(slider_mins, 0, 1440)))
        user32.SendMessageW(self.controls[ID_BUSY], TBM_SETPOS, 1, int(clamp(self.busy_manual * 100, 0, 100)))
        self.set_text(ID_SOUND, "有声" if self.sound_on else "静音中")
        self.set_text(ID_TOPMOST, "取消置顶" if self.topmost else "保持置顶")
        self.set_text(ID_REAL, ("● " if self.time_mode == "real" else "○ ") + "真实时间")
        self.set_text(ID_FAST, ("● " if self.time_mode == "fast" else "○ ") + "加速一天")
        self.set_text(ID_AUTO, ("● " if self.autopilot else "○ ") + "自动")
        for i, key in enumerate(self.manual_moods):
            active = (not self.autopilot and self.manual_mood == key)
            self.set_text(ID_MOOD_BASE + i, ("● " if active else "○ ") + self.moods[key].label.split(" · ")[0])
        for i, key in enumerate(self.theme_keys):
            self.set_text(ID_THEME_BASE + i, ("✓ " if self.theme_key == key else "") + self.themes[key][0])

    def set_text(self, key, text):
        hwnd = self.controls.get(key)
        if hwnd:
            user32.SetWindowTextW(hwnd, text)

    def get_window_rect(self):
        rect = wintypes.RECT()
        user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
        return rect.left, rect.top, rect.right, rect.bottom

    def on_left_down(self, x, y):
        user32.SetFocus(self.hwnd)
        px, py = self.to_canvas(x, y)
        d = math.hypot(px - self.pos[0], py - self.pos[1])
        if d < self.current_radius * 1.15:
            self.pressing = True
            self.dragging = False
            self.pointer_down_at = self.t
            self.pointer_moved = 0.0
            self.last_pointer = [px, py]
            pt = POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            self.last_screen = [pt.x, pt.y]
            self.last_interact = self.t
            user32.SetCapture(self.hwnd)
            user32.SetCursor(user32.LoadCursorW(None, IDC_SIZEALL))

    def on_mouse_move(self, x, y):
        self.track_mouse_leave()
        px, py = self.to_canvas(x, y)
        mv = math.hypot(px - self.last_pointer[0], py - self.last_pointer[1])
        self.pointer_speed = self.pointer_speed * 0.8 + mv * 0.2
        self.mouse = [px, py, 0 <= px <= self.canvas_w and 0 <= py <= self.canvas_h]

        if self.pressing:
            self.pointer_moved += mv
            if self.pointer_moved > 7:
                self.dragging = True
            if self.dragging:
                pt = POINT()
                user32.GetCursorPos(ctypes.byref(pt))
                dx = pt.x - self.last_screen[0]
                dy = pt.y - self.last_screen[1]
                left, top, _, _ = self.get_window_rect()
                user32.SetWindowPos(self.hwnd, None, left + dx, top + dy, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)
                self.last_screen = [pt.x, pt.y]
        else:
            d = math.hypot(px - self.pos[0], py - self.pos[1])
            if d < self.current_radius:
                self.stroke_accum += mv
                self.last_interact = self.t
                if self.stroke_accum > 75:
                    self.react("happy", 1.4)
                    self.energy = min(1.0, self.energy + 0.3)
                    self.stroke_accum = 0
                    self.sfx_stroke()
        self.last_pointer = [px, py]

    def on_left_up(self, x, y):
        if self.pressing and not self.dragging and (self.t - self.pointer_down_at) < 0.3:
            self.react("surprised", 0.9)
            self.ripples.append([25.0, 0.6])
            self.vel[1] -= 210
            self.last_interact = self.t
            self.sfx_drop()
        self.pressing = False
        self.dragging = False
        user32.ReleaseCapture()
        user32.SetCursor(user32.LoadCursorW(None, IDC_ARROW))

    def track_mouse_leave(self):
        tme = TRACKMOUSEEVENT()
        tme.cbSize = ctypes.sizeof(TRACKMOUSEEVENT)
        tme.dwFlags = 0x00000002
        tme.hwndTrack = self.hwnd
        tme.dwHoverTime = 0
        user32.TrackMouseEvent(ctypes.byref(tme))

    def to_canvas(self, x, y):
        return x - self.canvas_x, y - self.canvas_y

    def notify_typing(self):
        self.key_times.append(self.t)
        self.last_key_at = self.t
        self.last_interact = self.t

    def update(self, dt):
        self.t += dt
        if self.time_mode == "fast":
            self.manual_minutes = (self.manual_minutes + self.fast_speed * dt) % 1440
        mins = self.current_minutes()
        circ = self.circadian(mins)
        self.circ_wake = lerp(self.circ_wake, circ[0], 1 - math.pow(0.05, dt))
        self.circ_warm = lerp(self.circ_warm, circ[1], 1 - math.pow(0.05, dt))

        self.key_times = [k for k in self.key_times if self.t - k < 1.5]
        self.typing_rate = lerp(self.typing_rate, len(self.key_times), 1 - math.pow(0.02, dt))
        typing_now = (self.t - self.last_key_at) < 1.0
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
        if self.focus_time > 75 and (self.t - self.last_rest_at) > 40 and self.t >= self.react_until:
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
            self.on_mood_changed(mood_key)
        self.target = self.moods[mood_key]
        k = 1 - math.pow(0.001, dt)
        s = self.st
        s["scale"] = lerp(s["scale"], self.target.scale, k)
        s["squash"] = lerp(s["squash"], self.target.squash, k)
        s["wobble"] = lerp(s["wobble"], self.target.wobble, k)
        s["glow"] = lerp(s["glow"], self.target.glow, k)
        s["breathe"] = lerp(s["breathe"], self.target.breathe, k)
        s["lift"] = lerp(s["lift"], self.target.lift, k)
        s["eye_gap"] = lerp(s["eye_gap"], self.target.eye_gap, k)
        s["tilt"] = lerp(s["tilt"], 0.16 if self.target.tilt else 0.0, k)
        s["core_size"] = lerp(s["core_size"], self.target.core_size, k)
        s["core_pulse"] = lerp(s["core_pulse"], self.target.core_pulse, k)
        mc = self.mood_color()
        s["hue"][0] = lerp(s["hue"][0], mc[0], k)
        s["hue"][1] = lerp(s["hue"][1], mc[1], k)
        s["hue"][2] = lerp(s["hue"][2], mc[2], k)

        self.physics(dt)
        self.update_particles(dt)
        self.blink_timer -= dt
        if self.blink_timer <= 0:
            self.blink = 1.0
            self.blink_timer = 2.4 + random.random() * 2.5
        if self.blink > 0:
            self.blink = max(0.0, self.blink - dt * 7)

    def physics(self, dt):
        hx = self.home_x + self.wander[0]
        hy = self.home_y + self.st["lift"] + self.wander[1]
        if self.target.bounce:
            hy += math.sin(self.t * 5) * -8 * self.target.bounce
        if self.target.sag:
            hy += 6 + math.sin(self.t * 0.7) * 3.5
        if self.target.sway:
            hx += math.sin(self.t * 0.9) * 10
        spring = 110
        damp = 10
        self.vel[0] += ((hx - self.pos[0]) * spring - self.vel[0] * damp) * dt
        self.vel[1] += ((hy - self.pos[1]) * spring - self.vel[1] * damp) * dt
        self.vel[0] = clamp(self.vel[0], -1500, 1500)
        self.vel[1] = clamp(self.vel[1], -1500, 1500)
        self.pos[0] += self.vel[0] * dt
        self.pos[1] += self.vel[1] * dt

    def update_particles(self, dt):
        self.stroke_accum = max(0.0, self.stroke_accum - dt * 120)
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
        if self.target.fx == "sparkle":
            self.spark_timer -= dt
            if self.spark_timer <= 0:
                self.spark_timer = 0.18
                self.sparkles.append([self.pos[0] + (random.random() - 0.5) * self.current_radius * 1.6, self.pos[1] - self.current_radius * 0.6, 0, -30 - random.random() * 20, 1, 1.2 + random.random() * 1.8, False])
        if self.target.fx == "zzz":
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

    def render(self):
        ctypes.memset(self.bits, 0, self.width * self.height * 4)
        mood = self.target
        color = self.st["hue"]
        col = (int(color[0]), int(color[1]), int(color[2]))
        render_glow = self.st["glow"] * (0.55 + 0.55 * self.circ_wake)
        breath = math.sin(self.t * self.st["breathe"] * 1.6) * 0.05 + 1
        breath_guide = 1.0
        breath_phase = 0.0
        if mood.breathing:
            breath_phase = math.sin(self.t * 0.7)
            breath_guide = 1 + breath_phase * 0.12
        self.current_radius = 60 * self.st["scale"] * breath_guide
        base_r = self.current_radius * breath
        jit = (0.5 + self.busy_level * 0.8) if mood.jitter else 0
        jx = (random.random() - 0.5) * 4.5 * jit if jit else 0
        jy = (random.random() - 0.5) * 4.5 * jit if jit else 0
        cx = self.canvas_x + self.pos[0] + jx
        cy = self.canvas_y + self.pos[1] + jy

        self.draw_radial(cx, cy, base_r * 2.1, col, int(70 * render_glow))
        if mood.breathing:
            guide_r = base_r * (1.5 + breath_phase * 0.5)
            self.draw_ring(cx, cy, guide_r, col, 72)
            if breath_phase > 0.985 and not self.breath_high:
                self.breath_high = True
                self.sfx_breath(True)
            elif breath_phase < -0.985 and self.breath_high:
                self.breath_high = False
                self.sfx_breath(False)

        self.draw_ripples(cx, cy, col)
        self.draw_bursts(cx, cy, base_r, col)

        gx, gy = self.compute_gaze(cx - self.canvas_x, cy - self.canvas_y, mood)
        self.st["gx"] = lerp(self.st["gx"], gx, 0.25)
        self.st["gy"] = lerp(self.st["gy"], gy, 0.25)
        self.draw_blob(cx, cy, base_r, mood, col, render_glow)

        lum_x = cx
        lum_y = cy + base_r * 0.05
        if mood.core_gaze and self.mouse[2]:
            lum_x += self.st["gx"] * 0.6
            lum_y += self.st["gy"] * 0.6
        if mood.core_drift:
            lum_x += math.sin(self.t * 1.1) * base_r * 0.12
        core_alpha = int((15 + max(0, self.st["core_size"] - 0.8) * 90) * render_glow)
        self.draw_radial(lum_x, lum_y, base_r * (1.05 + 0.25 * self.st["core_size"]), (255, 255, 255), core_alpha)

        ey = cy - 4 + self.st["gy"]
        lx = cx - self.st["eye_gap"] / 4 + self.st["gx"]
        rx = cx + self.st["eye_gap"] / 4 + self.st["gx"]
        self.draw_eyes(mood, lx, rx, ey, col)
        self.draw_sparkles(cx, cy, base_r, mood, col)

        if not self.self_test:
            self.update_layered_window()

    def compute_gaze(self, cx, cy, mood):
        if self.mouse[2]:
            dx = self.mouse[0] - cx
            dy = self.mouse[1] - cy
            d = math.hypot(dx, dy) or 1
            amt = min(d / 150, 1) * (8 if mood.lean else 4.5)
            return dx / d * amt, dy / d * amt
        return self.look_target[0], self.look_target[1]

    def draw_blob(self, cx, cy, base_r, mood, col, render_glow):
        sx = self.st["squash"]
        sy = 2 - self.st["squash"]
        tilt = self.st["tilt"]
        if mood.lean and self.mouse[2]:
            tilt += (self.mouse[0] - (cx - self.canvas_x)) / self.canvas_w * 0.5
        if mood.sway:
            tilt += math.sin(self.t * 1.6) * 0.1
        cos_t = math.cos(-tilt)
        sin_t = math.sin(-tilt)
        rx = base_r * max(sx, 0.2) * 1.28
        ry = base_r * max(sy * 0.5 + 0.5, 0.2) * 1.28
        min_x = max(0, int(cx - rx - 3))
        max_x = min(self.width - 1, int(cx + rx + 3))
        min_y = max(0, int(cy - ry - 3))
        max_y = min(self.height - 1, int(cy + ry + 3))
        sxr = base_r * sx
        syr = base_r * (sy * 0.5 + 0.5)
        for y in range(min_y, max_y + 1):
            dy = y - cy
            row = y * self.width
            for x in range(min_x, max_x + 1):
                dx = x - cx
                lx = dx * cos_t - dy * sin_t
                ly = dx * sin_t + dy * cos_t
                angle = math.atan2(ly, lx)
                noise = (
                    math.sin(angle * 3 + self.t * 1.4) * self.st["wobble"]
                    + math.sin(angle * 5 - self.t) * self.st["wobble"] * 0.5
                    + math.sin(angle * 2 + self.t * 0.6) * self.st["wobble"] * 0.7
                )
                dist = math.sqrt((lx / sxr) ** 2 + (ly / syr) ** 2)
                edge = 1 + noise
                if dist <= edge:
                    q = clamp(1 - dist / max(edge, 0.01), 0, 1)
                    alpha = int(112 + q * 122)
                    light_d = math.hypot(x - (cx - base_r * 0.25), y - (cy - base_r * 0.35)) / (base_r * 1.25)
                    light = clamp(1 - light_d, 0, 1) * 0.25
                    shade = clamp((dist - 0.45) * 0.35, 0, 0.25)
                    rgb = mix_color(col, (255, 255, 255), light)
                    rgb = mix_color(rgb, (0, 0, 0), shade)
                    self.blend_pixel_index(row + x, rgb[0], rgb[1], rgb[2], alpha)
        self.draw_ring(cx, cy, base_r * 1.03, col, int(70 * render_glow))

    def draw_radial(self, cx, cy, radius, color, alpha):
        if alpha <= 0 or radius <= 0:
            return
        r2 = radius * radius
        min_x = max(0, int(cx - radius))
        max_x = min(self.width - 1, int(cx + radius))
        min_y = max(0, int(cy - radius))
        max_y = min(self.height - 1, int(cy + radius))
        for y in range(min_y, max_y + 1):
            dy = y - cy
            row = y * self.width
            for x in range(min_x, max_x + 1):
                dx = x - cx
                d2 = dx * dx + dy * dy
                if d2 <= r2:
                    q = 1 - d2 / r2
                    a = int(alpha * q * q)
                    if a:
                        self.blend_pixel_index(row + x, color[0], color[1], color[2], a)

    def draw_disc(self, cx, cy, radius, color, alpha):
        r2 = radius * radius
        min_x = max(0, int(cx - radius))
        max_x = min(self.width - 1, int(cx + radius))
        min_y = max(0, int(cy - radius))
        max_y = min(self.height - 1, int(cy + radius))
        for y in range(min_y, max_y + 1):
            dy = y - cy
            row = y * self.width
            for x in range(min_x, max_x + 1):
                dx = x - cx
                if dx * dx + dy * dy <= r2:
                    self.blend_pixel_index(row + x, color[0], color[1], color[2], alpha)

    def draw_ellipse(self, cx, cy, rx, ry, color, alpha):
        if ry <= 0:
            return
        min_x = max(0, int(cx - rx))
        max_x = min(self.width - 1, int(cx + rx))
        min_y = max(0, int(cy - ry))
        max_y = min(self.height - 1, int(cy + ry))
        for y in range(min_y, max_y + 1):
            ny = (y - cy) / ry
            row = y * self.width
            for x in range(min_x, max_x + 1):
                nx = (x - cx) / rx
                if nx * nx + ny * ny <= 1:
                    self.blend_pixel_index(row + x, color[0], color[1], color[2], alpha)

    def draw_line(self, x1, y1, x2, y2, color, alpha, width=2.0):
        steps = int(max(abs(x2 - x1), abs(y2 - y1), 1))
        for i in range(steps + 1):
            f = i / steps
            x = x1 + (x2 - x1) * f
            y = y1 + (y2 - y1) * f
            self.draw_disc(x, y, width, color, alpha)

    def draw_ring(self, cx, cy, radius, color, alpha):
        steps = max(36, int(radius * 0.7))
        last = None
        for i in range(steps + 1):
            a = i / steps * math.tau
            p = (cx + math.cos(a) * radius, cy + math.sin(a) * radius)
            if last:
                self.draw_line(last[0], last[1], p[0], p[1], color, alpha, 1.1)
            last = p

    def draw_ripples(self, cx, cy, col):
        for radius, a in self.ripples:
            self.draw_ring(cx, cy, radius, col, int(clamp(a, 0, 1) * 150))

    def draw_bursts(self, cx, cy, base_r, col):
        for ang, length, a in self.bursts:
            length = min(length, 30)
            x1 = cx + math.cos(ang) * base_r * 1.05
            y1 = cy + math.sin(ang) * base_r * 1.05
            x2 = cx + math.cos(ang) * (base_r * 1.05 + length)
            y2 = cy + math.sin(ang) * (base_r * 1.05 + length)
            self.draw_line(x1, y1, x2, y2, col, int(clamp(a, 0, 1) * 190), 1.7)

    def draw_eyes(self, mood, lx, rx, ey, col):
        blink_mul = 1 - self.blink
        if mood.eye_style == "dots":
            self.glow_dot(lx, ey, 3.5, 6.5 * blink_mul, col)
            self.glow_dot(rx, ey, 3.5, 6.5 * blink_mul, col)
        elif mood.eye_style == "arc":
            self.arc_eye(lx, ey, 5.5)
            self.arc_eye(rx, ey, 5.5)
        elif mood.eye_style == "wide":
            self.glow_dot(lx, ey, 6 * blink_mul + 1, 7 * blink_mul, col)
            self.glow_dot(rx, ey, 6 * blink_mul + 1, 7 * blink_mul, col)
        elif mood.eye_style == "huge":
            self.glow_dot(lx, ey, 8 * blink_mul + 1, 9 * blink_mul, col)
            self.glow_dot(rx, ey, 8 * blink_mul + 1, 9 * blink_mul, col)
        elif mood.eye_style == "lines":
            self.draw_line(lx - 4, ey, lx + 4, ey, (255, 255, 255), 245, 1.7)
            self.draw_line(rx - 4, ey, rx + 4, ey, (255, 255, 255), 245, 1.7)
        elif mood.eye_style == "squint":
            self.glow_dot(lx, ey, 3, 4 * blink_mul, col)
            self.draw_line(rx - 4, ey - 1, rx + 4, ey - 1, (255, 255, 255), 245, 1.7)

    def glow_dot(self, x, y, rx, ry, col):
        self.draw_radial(x, y, max(rx, ry) * 2.2, col, 120)
        self.draw_ellipse(x, y, max(rx, 0.8), max(ry, 0.7), (255, 255, 255), 245)

    def arc_eye(self, x, y, r):
        last = None
        for i in range(18):
            a = math.radians(205 + 130 * i / 17)
            p = (x + math.cos(a) * r, y + 2 + math.sin(a) * r)
            if last:
                self.draw_line(last[0], last[1], p[0], p[1], (255, 255, 255), 245, 1.7)
            last = p

    def draw_sparkles(self, cx, cy, base_r, mood, col):
        for x, y, vx, vy, a, size, grow in self.sparkles:
            self.draw_disc(self.canvas_x + x, self.canvas_y + y, max(size, 0.5), col, int(clamp(a, 0, 1) * 220))
        if mood.fx == "think":
            for i in range(3):
                a = self.t * 1.5 + i * 2.1
                ox = cx + math.cos(a) * base_r * 1.5
                oy = cy - base_r + math.sin(a) * 5 - i * 3
                self.draw_disc(ox, oy, max(2.2 - i * 0.4, 0.5), col, 150 - i * 28)

    def blend_pixel_index(self, idx, r, g, b, a):
        if a <= 0:
            return
        if a > 255:
            a = 255
        sr = (int(r) * a + 127) // 255
        sg = (int(g) * a + 127) // 255
        sb = (int(b) * a + 127) // 255
        dst = self.pixels[idx]
        da = (dst >> 24) & 255
        dr = (dst >> 16) & 255
        dg = (dst >> 8) & 255
        db = dst & 255
        inv = 255 - a
        oa = a + (da * inv + 127) // 255
        or_ = sr + (dr * inv + 127) // 255
        og = sg + (dg * inv + 127) // 255
        ob = sb + (db * inv + 127) // 255
        self.pixels[idx] = (oa << 24) | (or_ << 16) | (og << 8) | ob

    def update_layered_window(self):
        pt_dst = POINT()
        rect = self.get_window_rect()
        pt_dst.x = rect[0]
        pt_dst.y = rect[1]
        size = SIZE(self.width, self.height)
        pt_src = POINT(0, 0)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        user32.UpdateLayeredWindow(
            self.hwnd,
            self.hdc_screen,
            ctypes.byref(pt_dst),
            ctypes.byref(size),
            self.hdc_mem,
            ctypes.byref(pt_src),
            0,
            ctypes.byref(blend),
            ULW_ALPHA,
        )

    def current_minutes(self):
        if self.time_mode == "real":
            now = time.localtime()
            return now.tm_hour * 60 + now.tm_min + now.tm_sec / 60
        return self.manual_minutes

    def circadian(self, mins):
        h = mins / 60.0
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
        for i in range(len(frames) - 1):
            if frames[i][0] <= h <= frames[i + 1][0]:
                f = (h - frames[i][0]) / (frames[i + 1][0] - frames[i][0])
                wake = lerp(frames[i][1], frames[i + 1][1], f)
                warm = lerp(frames[i][2], frames[i + 1][2], f)
                break
        phase = "深夜" if h < 5 else "清晨" if h < 8 else "上午" if h < 11 else "正午" if h < 14 else "午后" if h < 17 else "黄昏" if h < 20 else "夜晚" if h < 23 else "深夜"
        return wake, warm, phase

    def mood_color(self):
        base = self.themes[self.theme_key][1]
        f = 1 + self.target.tone
        tp = self.target.temp + self.circ_warm * 0.6
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

    def on_mood_changed(self, mood_key):
        mood = self.moods[mood_key]
        if mood.fx == "burst":
            self.bursts = [[i / 10 * math.tau, 0.0, 1.0] for i in range(10)]
        if mood_key in ("happy", "excited"):
            self.sfx_chime()

    def status_text(self):
        mins = self.current_minutes()
        h = int(mins // 60) % 24
        m = int(mins % 60)
        phase = self.circadian(mins)[2]
        mood_name = self.moods[self.effective_mood()].label.split(" · ")[0]
        focus_m = int(self.focus_time // 60)
        focus_s = int(self.focus_time % 60)
        return f"{h:02d}:{m:02d} · {phase} · 状态 {mood_name} · 专注 {focus_m}:{focus_s:02d}"

    def play_tone(self, freq, dur):
        if not self.sound_on:
            return

        def worker():
            try:
                winsound.Beep(int(freq), int(dur))
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


def main():
    self_test = "--self-test" in sys.argv
    smoke_test = "--smoke-test" in sys.argv
    DesktopPet(self_test=self_test, smoke_test=smoke_test).run()


if __name__ == "__main__":
    main()
