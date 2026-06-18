from ..qt import QColor, QPainter, QPen, QPointF, QPushButton, QRectF, Qt
from ..utils import color_mix


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


class WindowControlButton(QPushButton):
    def __init__(self, model, kind, parent=None):
        super().__init__(parent)
        self.model = model
        self.kind = kind
        self.setFixedSize(46, 34)
        self.setText("")
        self.setFlat(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        tips = {
            "minimize": "最小化",
            "maximize": "最大化 / 还原",
            "close": "关闭",
        }
        self.setToolTip(tips.get(kind, "窗口控制"))

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
        if self.kind == "close" and self.underMouse():
            fill = (196, 43, 43) if not self.isDown() else (146, 28, 28)
            mark = (255, 255, 255)
            border = fill
        elif self.isDown():
            fill = color_mix(accent, (18, 22, 32), 0.42)
            border = color_mix(accent, (255, 255, 255), 0.38)
            mark = (255, 255, 255)
        elif self.underMouse():
            fill = color_mix(accent, (34, 40, 56), 0.34)
            border = color_mix(accent, (255, 255, 255), 0.54)
            mark = color_mix(accent, (255, 255, 255), 0.86)
        else:
            fill = color_mix(base, (24, 28, 38), 0.78)
            border = color_mix(accent, (110, 126, 166), 0.38)
            mark = color_mix(accent, (255, 255, 255), 0.70)

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(2, 2, self.width() - 4, self.height() - 4)
        p.setPen(QPen(QColor(*border), 1.0))
        p.setBrush(QColor(*fill))
        p.drawRoundedRect(rect, 8, 8)

        pen = QPen(QColor(*mark), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        cx = self.width() / 2
        cy = self.height() / 2
        if self.kind == "minimize":
            p.drawLine(QPointF(cx - 8, cy + 5), QPointF(cx + 8, cy + 5))
        elif self.kind == "maximize":
            if self.window().isMaximized():
                p.drawRoundedRect(QRectF(cx - 5, cy - 8, 11, 11), 1.5, 1.5)
                p.drawRoundedRect(QRectF(cx - 8, cy - 4, 11, 11), 1.5, 1.5)
            else:
                p.drawRoundedRect(QRectF(cx - 7, cy - 7, 14, 14), 1.5, 1.5)
        elif self.kind == "close":
            p.drawLine(QPointF(cx - 7, cy - 7), QPointF(cx + 7, cy + 7))
            p.drawLine(QPointF(cx + 7, cy - 7), QPointF(cx - 7, cy + 7))


class AgentSendButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(38, 38)
        self.setText("")
        self.setFlat(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("发送 · Enter")

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        if not self.isEnabled():
            fill = QColor(61, 125, 255, 108)
            mark = QColor(255, 255, 255, 145)
        elif self.isDown():
            fill = QColor(47, 101, 220)
            mark = QColor(255, 255, 255)
        elif self.underMouse():
            fill = QColor(83, 143, 255)
            mark = QColor(255, 255, 255)
        else:
            fill = QColor(61, 125, 255)
            mark = QColor(255, 255, 255)

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(2, 2, self.width() - 4, self.height() - 4)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(fill)
        p.drawEllipse(rect)

        pen = QPen(mark, 2.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        cx = self.width() / 2
        cy = self.height() / 2
        p.drawLine(QPointF(cx, cy + 9), QPointF(cx, cy - 8))
        p.drawLine(QPointF(cx, cy - 8), QPointF(cx - 6, cy - 2))
        p.drawLine(QPointF(cx, cy - 8), QPointF(cx + 6, cy - 2))
