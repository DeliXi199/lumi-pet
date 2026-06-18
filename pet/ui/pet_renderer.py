import math
import random
import time

from ..qt import QColor, QFont, QPainterPath, QPen, QPointF, QPolygonF, QRadialGradient, QRectF, Qt
from ..utils import clamp, lerp


class PetRendererMixin:
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

        glow = QRadialGradient(QPointF(cx, cy), base_r * 2.6)
        glow.setColorAt(0, QColor(*col, int(76 * render_glow)))
        glow.setColorAt(0.4, QColor(*col, int(26 * render_glow)))
        glow.setColorAt(1, QColor(*col, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QPointF(cx, cy), base_r * 2.6, base_r * 2.6)
        if mood.breathing:
            breath_alpha = int(46 + 30 * (breath_phase * 0.5 + 0.5))
            p.setPen(QPen(QColor(*col, breath_alpha), 1.0))
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
        gaze_k = 1 - math.pow(0.001, m.frame_dt)
        m.st["gx"] = lerp(m.st["gx"], gx, gaze_k)
        m.st["gy"] = lerp(m.st["gy"], gy, gaze_k)
        path = self.body_path(cx, cy, base_r, mood)
        grad = QRadialGradient(QPointF(cx - base_r * 0.3, cy - base_r * 0.4), base_r * 1.3)
        grad.setColorAt(0, QColor(*col, 235))
        grad.setColorAt(0.6, QColor(*col, 128))
        grad.setColorAt(1, QColor(int(col[0] * 0.5), int(col[1] * 0.5), int(col[2] * 0.7), 82))
        p.setBrush(grad)
        p.setPen(Qt.PenStyle.NoPen)
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
        lum_pulse = math.sin(m.t * m.st["breathe"] * 2.4) * m.st["core_pulse"] + 1
        lum_r = base_r * (1.05 + 0.25 * m.st["core_size"]) * lum_pulse
        lum_alpha = int((13 + max(0, m.st["core_size"] - 0.8) * 82) * render_glow)
        lum_grad = QRadialGradient(QPointF(lum_x, lum_y), lum_r)
        lum_grad.setColorAt(0, QColor(255, 255, 255, clamp(lum_alpha, 0, 255)))
        lum_grad.setColorAt(0.5, QColor(*col, clamp(int(lum_alpha * 0.5), 0, 255)))
        lum_grad.setColorAt(1, QColor(*col, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(lum_grad)
        p.drawEllipse(QPointF(lum_x, lum_y), lum_r, lum_r)
        p.restore()
        self.draw_eyes(p, mood, cx - m.st["eye_gap"] / 2 + m.st["gx"], cx + m.st["eye_gap"] / 2 + m.st["gx"], cy - 4 + m.st["gy"], qcol)
        self.draw_sparkles(p, sx, sy, cx, cy, base_r, qcol, mood)
        self.draw_extra_fx(p, cx, cy, base_r, qcol, mood)

    def draw_option_menu(self, p):
        if not self.option_menu_open:
            return
        m = self.model
        col = tuple(int(v) for v in m.st["hue"])
        qcol = QColor(*col)

        for i, (label, icon, _mood, _message) in enumerate(self.option_items):
            raw = clamp((m.t - self.option_menu_started - i * 0.028) / 0.34, 0, 1)
            ease = 1 - math.pow(1 - raw, 3)
            c = self.option_item_pos(i, progress=ease)
            hover = i == self.option_hover
            opacity = ease
            orb_r = 24 * (1.1 if hover else 1.0) * (0.3 + 0.7 * ease)
            orb_float = -2.0 if hover else math.sin(m.t * 2.1 + i * 0.72) * 6.0
            orb_c = QPointF(c.x(), c.y() + orb_float)
            glow_alpha = int((72 if hover else 42) * opacity)
            self.radial(p, orb_c, orb_r * (2.25 if hover else 1.85), qcol, glow_alpha)
            p.save()
            p.setOpacity(opacity)
            orb_grad = QRadialGradient(QPointF(orb_c.x() - orb_r * 0.24, orb_c.y() - orb_r * 0.34), orb_r * 1.45)
            orb_grad.setColorAt(0, QColor(255, 255, 255, 58 if not hover else 92))
            orb_grad.setColorAt(0.56, QColor(*col, 38 if not hover else 82))
            orb_grad.setColorAt(1, QColor(*col, 12 if not hover else 26))
            p.setBrush(orb_grad)
            p.setPen(QPen(QColor(*col, 78 if not hover else 185), 1.2))
            p.drawEllipse(orb_c, orb_r, orb_r)
            p.setPen(QColor(246, 248, 255, 235))
            icon_font = QFont("Segoe UI Emoji")
            icon_font.setPixelSize(21)
            p.setFont(icon_font)
            p.drawText(QRectF(orb_c.x() - orb_r, orb_c.y() - orb_r - 1, orb_r * 2, orb_r * 2), Qt.AlignmentFlag.AlignCenter, icon)
            p.setPen(QColor(226, 233, 248, 235 if hover else 178))
            label_font = QFont("Microsoft YaHei UI")
            label_font.setPixelSize(11)
            p.setFont(label_font)
            p.drawText(QRectF(c.x() - 32, c.y() + 31, 64, 16), Qt.AlignmentFlag.AlignCenter, label)
            p.restore()

    def draw_bubble(self, p):
        if not self.bubble_text:
            return
        m = self.model
        if m.t >= self.bubble_until:
            return
        fade = clamp(min((m.t - self.bubble_started) * 5, (self.bubble_until - m.t) * 4, 1), 0, 1)
        if fade <= 0:
            return
        col = tuple(int(v) for v in m.st["hue"])
        center = self.pet_center()
        wobble = math.sin(m.t * 2.0) * 3.0
        p.save()
        p.setOpacity(fade)
        text_font = QFont("Microsoft YaHei UI")
        text_font.setWeight(QFont.Weight.Medium)
        text_font.setPixelSize(13)
        text_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.45)
        p.setFont(text_font)
        metrics = p.fontMetrics()
        pad_x = 17
        pad_y = 11
        letter_spacing = 0.45
        line_height = 21
        lines = self.wrap_bubble_text(metrics, self.bubble_text, 198 - pad_x * 2, letter_spacing)
        raw_w = max((self.text_width(metrics, line, letter_spacing) for line in lines), default=0)
        w = min(198, max(66, raw_w + pad_x * 2))
        h = max(44, pad_y * 2 + line_height * len(lines))
        x = clamp(center.x() + 38, 8, self.width() - w - 8)
        y = clamp(center.y() - 70 - h + wobble, 8, self.height() - h - 30)
        rect = QRectF(x, y, w, h)
        age = max(0, m.t - self.bubble_started)
        if age < 0.30:
            pop = 0.5 + (1.05 - 0.5) * (age / 0.30)
        elif age < 0.50:
            pop = 1.05 - 0.05 * ((age - 0.30) / 0.20)
        else:
            pop = 1.0
        origin = QPointF(rect.left() + rect.width() * 0.18, rect.bottom())
        p.translate(origin)
        p.rotate(-1.4)
        p.scale(pop, pop)
        p.translate(-origin)
        self.radial(p, rect.center(), min(max(w, h) * 0.46, 92), QColor(*col), 38)
        path = QPainterPath()
        path.moveTo(x + w * 0.15, y + h * 0.04)
        path.cubicTo(x + w * 0.35, y - h * 0.04, x + w * 0.79, y - h * 0.03, x + w * 0.94, y + h * 0.22)
        path.cubicTo(x + w * 1.05, y + h * 0.42, x + w * 0.96, y + h * 0.86, x + w * 0.66, y + h * 0.97)
        path.cubicTo(x + w * 0.36, y + h * 1.07, x + w * 0.08, y + h * 0.91, x + w * 0.02, y + h * 0.62)
        path.cubicTo(x - w * 0.03, y + h * 0.36, x + w * 0.02, y + h * 0.12, x + w * 0.15, y + h * 0.04)
        bubble_grad = QRadialGradient(QPointF(x + w * 0.30, y + h * 0.16), max(w, h) * 1.05)
        bubble_grad.setColorAt(0, QColor(255, 255, 255, 62))
        bubble_grad.setColorAt(0.38, QColor(*col, 76))
        bubble_grad.setColorAt(0.74, QColor(*col, 32))
        bubble_grad.setColorAt(1, QColor(*col, 14))
        p.setPen(QPen(QColor(*col, 118), 1.1))
        p.setBrush(bubble_grad)
        p.drawPath(path)
        tail_x = rect.left() + rect.width() * 0.14
        small_tail_x = rect.left() + rect.width() * 0.04
        p.setPen(Qt.PenStyle.NoPen)
        tail_grad = QRadialGradient(QPointF(tail_x - 2, rect.bottom() + 4), 13)
        tail_grad.setColorAt(0, QColor(255, 255, 255, 70))
        tail_grad.setColorAt(0.58, QColor(*col, 78))
        tail_grad.setColorAt(1, QColor(*col, 24))
        p.setBrush(tail_grad)
        p.drawEllipse(QPointF(tail_x, rect.bottom() + 4.5), 6.5, 6.5)
        p.setBrush(QColor(*col, 58))
        p.drawEllipse(QPointF(small_tail_x, rect.bottom() + 20.5), 3.5, 3.5)
        self.draw_bubble_text(
            p,
            rect.adjusted(pad_x, pad_y, -pad_x, -pad_y),
            lines,
            metrics,
            line_height,
            letter_spacing,
            QColor(*col, 170),
            QColor(238, 242, 255, 245),
        )
        p.restore()

    @staticmethod
    def text_width(metrics, text, letter_spacing=0.0):
        if not text:
            return 0.0
        return sum(metrics.horizontalAdvance(ch) for ch in text) + max(0, len(text) - 1) * letter_spacing

    def wrap_bubble_text(self, metrics, text, max_width, letter_spacing):
        lines = []
        current = ""
        for ch in text:
            candidate = current + ch
            if current and self.text_width(metrics, candidate, letter_spacing) > max_width:
                lines.append(current)
                current = ch.lstrip()
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines or [""]

    def draw_spaced_line(self, p, text, x, baseline, metrics, letter_spacing):
        cursor = x
        for ch in text:
            p.drawText(QPointF(cursor, baseline), ch)
            cursor += metrics.horizontalAdvance(ch) + letter_spacing

    def draw_bubble_text(self, p, rect, lines, metrics, line_height, letter_spacing, glow_color, text_color):
        total_h = line_height * len(lines)
        top = rect.top() + (rect.height() - total_h) / 2
        ascent_offset = (line_height - metrics.height()) / 2 + metrics.ascent()
        for i, line in enumerate(lines):
            line_w = self.text_width(metrics, line, letter_spacing)
            x = rect.left() + (rect.width() - line_w) / 2
            baseline = top + i * line_height + ascent_offset
            p.setPen(glow_color)
            for dx, dy in ((0, 0), (-0.6, 0), (0.6, 0), (0, -0.6), (0, 0.6)):
                self.draw_spaced_line(p, line, x + dx, baseline + dy, metrics, letter_spacing)
            p.setPen(text_color)
            self.draw_spaced_line(p, line, x, baseline, metrics, letter_spacing)

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
        speed = math.hypot(m.vel[0], m.vel[1])
        stretch = min(speed * 0.002, 0.38)
        v_ang = math.atan2(m.vel[1], m.vel[0]) if speed > 0.001 else 0.0
        cos_v = math.cos(v_ang)
        sin_v = math.sin(v_ang)
        points = []
        for i in range(65):
            ang = i / 64 * math.tau
            noise = math.sin(ang * 3 + m.t * 1.4) * m.st["wobble"] + math.sin(ang * 5 - m.t) * m.st["wobble"] * 0.5 + math.sin(ang * 2 + m.t * 0.6) * m.st["wobble"] * 0.7
            rr = max(base_r * (1 + noise), 1)
            x = math.cos(ang) * rr * sx_scale
            y = math.sin(ang) * rr * (sy_scale * 0.5 + 0.5)
            tx = x * cos_t - y * sin_t
            ty = x * sin_t + y * cos_t
            vx = tx * cos_v + ty * sin_v
            vy = -tx * sin_v + ty * cos_v
            vx *= 1 + stretch
            vy /= 1 + stretch
            points.append(QPointF(cx + vx * cos_v - vy * sin_v, cy + vx * sin_v + vy * cos_v))
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
            p.setPen(QPen(QColor(col.red(), col.green(), col.blue(), int(clamp(a, 0, 1) * 255)), 1.25))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), r, r)

    def draw_bursts(self, p, cx, cy, base_r, col):
        for ang, length, a in self.model.bursts:
            length = min(length, 30)
            p.setPen(QPen(QColor(col.red(), col.green(), col.blue(), int(clamp(a, 0, 1) * 255)), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
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
        elif mood.eye_style == "focus":
            self.glow_dot(p, lx, ey + 1, 2.5, 4 * blink, col)
            self.glow_dot(p, rx, ey + 1, 2.5, 4 * blink, col)
            p.setPen(QPen(QColor(255, 255, 255, 245), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(lx - 4.5, ey - 6), QPointF(lx + 3.5, ey - 3.5))
            p.drawLine(QPointF(rx + 4.5, ey - 6), QPointF(rx - 3.5, ey - 3.5))
        elif mood.eye_style == "read":
            self.read_eye(p, lx, ey - 1.5)
            self.read_eye(p, rx, ey - 1.5)
        elif mood.eye_style == "star":
            size = 4.25 * (0.62 + 0.38 * blink)
            self.star_eye(p, lx, ey, size, col)
            self.star_eye(p, rx, ey, size, col)
        else:
            size = {
                "dots": (3.5, 6.5 * blink),
                "wide": (6 * blink + 0.5, 7 * blink),
                "huge": (8 * blink + 1, 9 * blink),
            }.get(mood.eye_style, (3.5, 6.5 * blink))
            self.glow_dot(p, lx, ey, size[0], size[1], col)
            self.glow_dot(p, rx, ey, size[0], size[1], col)

    def glow_dot(self, p, x, y, rx, ry, col):
        radius = max(rx, ry, 0.5) * 1.4
        grad = QRadialGradient(QPointF(x, y), radius)
        grad.setColorAt(0, QColor(255, 255, 255, 250))
        grad.setColorAt(0.5, QColor(col.red(), col.green(), col.blue(), 230))
        grad.setColorAt(1, QColor(col.red(), col.green(), col.blue(), 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawEllipse(QPointF(x, y), max(rx, 0.5), max(ry, 0.0))

    def arc_eye(self, p, x, y):
        p.setPen(QPen(QColor(255, 255, 255, 245), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        path = QPainterPath()
        for i in range(18):
            a = math.pi * (1.12 + 0.76 * i / 17)
            point = QPointF(x + math.cos(a) * 5.5, y + 2 + math.sin(a) * 5.5)
            if i == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)
        p.drawPath(path)

    def line_eye(self, p, x, y, w):
        p.setPen(QPen(QColor(255, 255, 255, 245), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(x - w / 2, y), QPointF(x + w / 2, y))

    def read_eye(self, p, x, y):
        p.setPen(QPen(QColor(255, 255, 255, 245), 2.25, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        path = QPainterPath()
        for i in range(16):
            a = math.pi * (0.15 + 0.7 * i / 15)
            point = QPointF(x + math.cos(a) * 5, y + math.sin(a) * 5)
            if i == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)
        p.drawPath(path)

    def star_eye(self, p, x, y, r, col):
        radius = r * 1.7
        grad = QRadialGradient(QPointF(x, y), radius)
        grad.setColorAt(0, QColor(255, 255, 255, 250))
        grad.setColorAt(0.5, QColor(col.red(), col.green(), col.blue(), 217))
        grad.setColorAt(1, QColor(col.red(), col.green(), col.blue(), 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawEllipse(QPointF(x, y), radius, radius)
        p.setPen(QPen(QColor(255, 255, 255, 245), 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(x - r, y), QPointF(x + r, y))
        p.drawLine(QPointF(x, y - r), QPointF(x, y + r))
        p.drawLine(QPointF(x - r * 0.6, y - r * 0.6), QPointF(x + r * 0.6, y + r * 0.6))
        p.drawLine(QPointF(x - r * 0.6, y + r * 0.6), QPointF(x + r * 0.6, y - r * 0.6))

    def draw_sparkles(self, p, sx, sy, cx, cy, base_r, col, mood):
        p.setPen(Qt.PenStyle.NoPen)
        for x, y, vx, vy, a, size, grow in self.model.sparkles:
            p.setBrush(QColor(col.red(), col.green(), col.blue(), int(clamp(a, 0, 1) * 220)))
            p.drawEllipse(QPointF(sx + x, sy + y), size, size)
        if mood.fx == "think":
            for i in range(3):
                a = self.model.t * 1.5 + i * 2.1
                alpha = int((0.6 - i * 0.14) * 255)
                size = max(2 - i * 0.4, 0.5)
                p.setBrush(QColor(col.red(), col.green(), col.blue(), alpha))
                p.drawEllipse(QPointF(cx + math.cos(a) * base_r * 1.5, cy - base_r + math.sin(a) * 5 - i * 2.5), size, size)

    def draw_extra_fx(self, p, cx, cy, base_r, col, mood):
        if mood.fx == "orbit":
            p.setPen(QPen(QColor(col.red(), col.green(), col.blue(), 31), 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), base_r * 1.34, base_r * 1.34 * 0.66)
            p.setPen(Qt.PenStyle.NoPen)
            for i in range(4):
                a = self.model.t * 1.4 + i / 4 * math.tau
                ox = cx + math.cos(a) * base_r * 1.34
                oy = cy + math.sin(a) * base_r * 1.34 * 0.66
                self.radial(p, QPointF(ox, oy), 4, col, 150)
                p.setBrush(QColor(col.red(), col.green(), col.blue(), 216))
                p.drawEllipse(QPointF(ox, oy), 1.5, 1.5)
        elif mood.fx == "wave":
            p.setPen(QPen(QColor(col.red(), col.green(), col.blue(), 110), 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for i in range(3):
                phase = (self.model.t * 1.3 + i * 0.5) % 1.5
                wr = base_r * (1.05 + phase * 0.55)
                alpha = int(max(0, 1 - phase / 1.5) * 128)
                p.setPen(QPen(QColor(col.red(), col.green(), col.blue(), alpha), 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                rect = QRectF(cx + base_r * 0.15 - wr, cy - wr, wr * 2, wr * 2)
                p.drawArc(rect, int(-0.3 * 180 * 16), int(0.6 * 180 * 16))
        elif mood.fx == "steam":
            p.setPen(QPen(QColor(col.red(), col.green(), col.blue(), 46), 1.1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for i, bx in enumerate((cx - 7.5, cx + 7.5)):
                path = QPainterPath()
                for j in range(13):
                    f = j / 12
                    yy = cy - base_r * 0.75 - f * 24
                    xx = bx + math.sin(f * 6 + self.model.t * 2 + i * 1.7) * 3.5 * f
                    if j == 0:
                        path.moveTo(QPointF(xx, yy))
                    else:
                        path.lineTo(QPointF(xx, yy))
                p.drawPath(path)
        elif mood.fx == "quest":
            pulse = 1 + math.sin(self.model.t * 3) * 0.09
            qx = cx + base_r * 0.98
            qy = cy - base_r * 0.96 + math.sin(self.model.t * 3) * 2.5
            p.save()
            p.translate(qx, qy)
            p.rotate(math.degrees(0.18 + math.sin(self.model.t * 1.8) * 0.1))
            p.scale(pulse, pulse)
            p.setFont(QFont("Microsoft YaHei UI", 27, QFont.Weight.Bold))
            self.radial(p, QPointF(0, 0), 11, col, 130)
            p.setPen(QColor(col.red(), col.green(), col.blue(), 242))
            p.drawText(QRectF(-18, -20, 36, 36), Qt.AlignmentFlag.AlignCenter, "?")
            p.restore()
