# -*- coding: utf-8 -*-
"""
ui_cyber_widgets.py — Graphics layer of CyberObsidian Core 5.9 ("Architectural Obsidian" style).
Monochrome graphite surfaces, one restrained indigo accent, event-driven painting (no idle timers).
Public class names, __init__ signatures, methods and signals are kept for mod_*.py compatibility.
"""

import os
import sys
import subprocess
import psutil
from PySide6.QtCore import (
    Qt, QTimer, QRectF, QPoint, QPointF, Signal, QPropertyAnimation, QVariantAnimation, QEasingCurve
)
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QLinearGradient, QFont, QPainterPath, QPixmap, QIcon
)
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QFrame,
    QLineEdit, QCheckBox, QFileDialog, QMessageBox, QGraphicsOpacityEffect
)
from core_engine import is_admin, elevate_to_admin, get_base_dir, OutputDirectoryManager, CREATE_NO_WINDOW

# --- Palette (legacy names kept: mod_*.py import them) ---
COLOR_BG_DEEP = "#0A0C10"
COLOR_PANEL = "#0E1117"
COLOR_CARD = "#131720"
COLOR_CARD_ALT = "#171C26"
COLOR_BORDER = "#1E2430"
COLOR_INPUT = "#0D1016"
COLOR_INPUT_BORDER = "#222834"
COLOR_ACCENT = "#5E6AD2"
COLOR_ACCENT_HOVER = "#6E7AE2"
COLOR_TEXT_MAIN = "#EAEEF6"
COLOR_TEXT_DIM = "#8A94A6"
COLOR_TEXT_MUTED = "#566074"
COLOR_EMERALD = "#10B981"
COLOR_AMBER = "#F59E0B"
COLOR_CRIMSON = "#EF4444"
COLOR_CYAN = COLOR_ACCENT        # legacy alias: former neon cyan is now the indigo accent
COLOR_PURPLE = COLOR_TEXT_DIM    # legacy alias: former neon purple is now neutral secondary


def draw_obsidian_crystal(p: QPainter, rect: QRectF):
    """Faceted obsidian crystal: four graphite/indigo facets, thin outline, soft highlight."""
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()

    def pt(nx, ny):
        return QPointF(x + nx * w, y + ny * h)

    top, ul, ur = pt(0.50, 0.04), pt(0.14, 0.36), pt(0.86, 0.36)
    bot, core = pt(0.50, 0.96), pt(0.50, 0.44)

    def facet(points, brush):
        path = QPainterPath(points[0])
        for q in points[1:]:
            path.lineTo(q)
        path.closeSubpath()
        p.fillPath(path, brush)

    lower_right = QLinearGradient(core, bot)
    lower_right.setColorAt(0.0, QColor("#4F5BD5"))
    lower_right.setColorAt(1.0, QColor("#2A3190"))
    facet([top, ul, core], QBrush(QColor("#2A3142")))
    facet([top, core, ur], QBrush(QColor("#3B4560")))
    facet([ul, core, bot], QBrush(QColor("#151A24")))
    facet([core, ur, bot], QBrush(lower_right))

    stroke = max(0.8, w / 32.0)
    inner = QColor(COLOR_TEXT_MAIN)
    inner.setAlpha(40)
    p.setPen(QPen(inner, stroke * 0.7))
    p.drawLine(ul, core)
    p.drawLine(core, ur)
    p.drawLine(core, bot)

    outline = QPainterPath(top)
    for q in (ur, bot, ul):
        outline.lineTo(q)
    outline.closeSubpath()
    edge = QColor("#8A94A6")
    edge.setAlpha(150)
    pen = QPen(edge, stroke)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawPath(outline)

    glint = QColor("#FFFFFF")
    glint.setAlpha(110)
    p.setPen(QPen(glint, stroke, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(pt(0.50, 0.10), pt(0.32, 0.33))


def create_cyber_app_icon() -> QIcon:
    """Multi-size app icon (16..256px) painted in memory; also picks up cyber_obsidian.ico if present."""
    icon = QIcon()
    ico_file = os.path.join(get_base_dir(), "cyber_obsidian.ico")
    if os.path.isfile(ico_file):
        icon.addFile(ico_file)

    for sz in (16, 24, 32, 48, 64, 128, 256):
        pix = QPixmap(sz, sz)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        pad = max(1.0, sz / 16.0)
        rad = sz / 5.0
        p.setPen(QPen(QColor(COLOR_BORDER), max(1.0, sz / 48.0)))
        p.setBrush(QBrush(QColor(COLOR_PANEL)))
        p.drawRoundedRect(QRectF(pad, pad, sz - pad * 2, sz - pad * 2), rad, rad)
        m = sz * 0.2
        draw_obsidian_crystal(p, QRectF(m, m * 0.9, sz - m * 2, sz - m * 1.8))
        p.end()
        icon.addPixmap(pix)
    return icon


CYBER_OBSIDIAN_QSS = f"""
QWidget {{
    background-color: {COLOR_BG_DEEP};
    color: {COLOR_TEXT_MAIN};
    font-family: "Inter", "Segoe UI", sans-serif;
    font-size: 13px;
}}

QDialog, QMessageBox {{
    background-color: {COLOR_PANEL};
}}

QToolTip {{
    background-color: {COLOR_CARD_ALT};
    color: {COLOR_TEXT_MAIN};
    border: 1px solid {COLOR_INPUT_BORDER};
    padding: 6px 8px;
    border-radius: 6px;
}}

QFrame#CyberCard {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
}}

QFrame#CyberCard:hover {{
    background-color: {COLOR_CARD_ALT};
}}

QFrame#SideBar {{
    background-color: {COLOR_PANEL};
    border-right: 1px solid {COLOR_BORDER};
}}

QTabWidget::pane {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
    top: -1px;
    padding: 8px;
}}

QTabBar {{
    background-color: transparent;
}}

QTabBar::tab {{
    background-color: transparent;
    color: {COLOR_TEXT_DIM};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 8px 14px;
    margin-right: 2px;
    font-weight: 500;
    font-size: 12px;
}}

QTabBar::tab:hover {{
    color: {COLOR_TEXT_MAIN};
}}

QTabBar::tab:selected {{
    color: {COLOR_TEXT_MAIN};
    border-bottom: 2px solid {COLOR_ACCENT};
    font-weight: 600;
}}

QLabel {{
    background: transparent;
}}

QLabel#SectionTitle {{
    color: {COLOR_TEXT_MAIN};
    font-size: 13px;
    font-weight: 600;
    background: transparent;
}}

QLabel#SubLabel {{
    color: {COLOR_TEXT_DIM};
    font-size: 12px;
    background: transparent;
}}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
    background-color: {COLOR_INPUT};
    border: 1px solid {COLOR_INPUT_BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    color: {COLOR_TEXT_MAIN};
    selection-background-color: {COLOR_ACCENT};
    selection-color: #FFFFFF;
}}

QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {{
    border: 1px solid #2C3342;
}}

QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
    background-color: {COLOR_BG_DEEP};
    border: 1px solid #181C25;
    color: {COLOR_TEXT_MUTED};
}}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {COLOR_ACCENT};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
    background: transparent;
}}

QComboBox QAbstractItemView {{
    background-color: {COLOR_CARD_ALT};
    color: {COLOR_TEXT_MAIN};
    border: 1px solid {COLOR_INPUT_BORDER};
    selection-background-color: #232A3A;
    selection-color: {COLOR_TEXT_MAIN};
    outline: 0;
}}

QPushButton {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_INPUT_BORDER};
    border-radius: 6px;
    padding: 7px 14px;
    color: {COLOR_TEXT_MAIN};
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: #1D2330;
    border: 1px solid #2E3546;
}}

QPushButton:pressed {{
    background-color: {COLOR_CARD};
}}

QPushButton:disabled {{
    color: {COLOR_TEXT_MUTED};
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
}}

QPushButton#WindowCtrlBtn, QPushButton#WindowCloseBtn {{
    padding: 0px;
    font-size: 13px;
    border-radius: 6px;
    background-color: transparent;
    border: none;
    color: {COLOR_TEXT_DIM};
}}

QPushButton#WindowCtrlBtn:hover {{
    background-color: #1D2330;
    color: {COLOR_TEXT_MAIN};
}}

QPushButton#WindowCloseBtn:hover {{
    background-color: {COLOR_CRIMSON};
    color: #FFFFFF;
}}

QPushButton#CyanActionBtn {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4F5BD5, stop:1 #3B44B0);
    border: 1px solid #6570DA;
    color: #FFFFFF;
    font-weight: 600;
}}

QPushButton#CyanActionBtn:hover {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {COLOR_ACCENT_HOVER}, stop:1 #4650BE);
}}

QPushButton#PurpleActionBtn {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_INPUT_BORDER};
    color: {COLOR_TEXT_MAIN};
    font-weight: 500;
}}

QPushButton#PurpleActionBtn:hover {{
    border: 1px solid {COLOR_ACCENT};
    background-color: #1D2330;
}}

QPushButton#EmeraldActionBtn {{
    background-color: #0F1F1B;
    border: 1px solid #1C4A3C;
    color: {COLOR_EMERALD};
    font-weight: 600;
}}

QPushButton#EmeraldActionBtn:hover {{
    background-color: #12302A;
    border: 1px solid {COLOR_EMERALD};
}}

QPushButton#DangerBtn {{
    background-color: #221416;
    border: 1px solid #4A2226;
    color: {COLOR_CRIMSON};
    font-weight: 500;
}}

QPushButton#DangerBtn:hover {{
    background-color: {COLOR_CRIMSON};
    border: 1px solid {COLOR_CRIMSON};
    color: #FFFFFF;
}}

QPushButton#NavTabBtn {{
    text-align: left;
    padding: 9px 12px;
    border-radius: 7px;
    border: 1px solid transparent;
    background-color: transparent;
    color: {COLOR_TEXT_DIM};
    font-size: 13px;
    font-weight: 500;
}}

QPushButton#NavTabBtn:hover {{
    background-color: #151A23;
    color: {COLOR_TEXT_MAIN};
}}

QPushButton#NavTabBtn[active="true"] {{
    background-color: #1A1F2B;
    border: 1px solid {COLOR_BORDER};
    color: {COLOR_TEXT_MAIN};
    font-weight: 600;
}}

QTableWidget, QTreeWidget, QListWidget {{
    background-color: {COLOR_INPUT};
    alternate-background-color: #10141B;
    border: 1px solid {COLOR_INPUT_BORDER};
    border-radius: 6px;
    gridline-color: #181D27;
    color: {COLOR_TEXT_MAIN};
}}

QTableWidget::item:selected, QTreeWidget::item:selected, QListWidget::item:selected {{
    background-color: #20263A;
    color: {COLOR_TEXT_MAIN};
}}

QHeaderView {{
    background-color: {COLOR_PANEL};
}}

QHeaderView::section {{
    background-color: {COLOR_PANEL};
    color: {COLOR_TEXT_DIM};
    border: none;
    border-bottom: 1px solid {COLOR_INPUT_BORDER};
    border-right: 1px solid #181D27;
    padding: 6px 8px;
    font-weight: 600;
}}

QTableCornerButton::section {{
    background-color: {COLOR_PANEL};
    border: 1px solid #181D27;
}}

QCheckBox {{
    spacing: 8px;
    background: transparent;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #2C3342;
    background-color: {COLOR_INPUT};
}}

QCheckBox::indicator:hover {{
    border: 1px solid {COLOR_ACCENT};
}}

QCheckBox::indicator:checked {{
    background-color: {COLOR_ACCENT};
    border: 1px solid {COLOR_ACCENT_HOVER};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background: #232A37;
    min-height: 24px;
    border-radius: 4px;
    margin: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background: #323A4A;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 0px;
}}

QScrollBar::handle:horizontal {{
    background: #232A37;
    min-width: 24px;
    border-radius: 4px;
    margin: 2px;
}}

QScrollBar::handle:horizontal:hover {{
    background: #323A4A;
}}

QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0px;
    height: 0px;
}}
"""


class HoloCard(QFrame):
    """Clean card: 10px radius, 1px border, accent edge fades in on hover (OutCubic, 180 ms)."""
    def __init__(self, accent_hex: str = COLOR_CYAN, parent=None):
        super().__init__(parent)
        self.setObjectName("CyberCard")
        self.accent_color = QColor(COLOR_ACCENT)
        self._hover = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_hover_value)

    def _on_hover_value(self, v):
        self._hover = float(v)
        self.update()

    def _animate_hover(self, target: float):
        self._anim.stop()
        self._anim.setStartValue(self._hover)
        self._anim.setEndValue(target)
        self._anim.start()

    def enterEvent(self, event):
        self._animate_hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_hover(0.0)
        super().leaveEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._hover <= 0.01:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)

        border = QColor(self.accent_color)
        border.setAlpha(int(70 * self._hover))
        painter.setPen(QPen(border, 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, 10, 10)

        w = self.width()
        grad = QLinearGradient(0, 0, w, 0)
        edge = QColor(COLOR_ACCENT_HOVER)
        edge.setAlpha(0)
        grad.setColorAt(0.0, edge)
        edge.setAlpha(int(200 * self._hover))
        grad.setColorAt(0.5, edge)
        edge.setAlpha(0)
        grad.setColorAt(1.0, edge)
        painter.setPen(QPen(QBrush(grad), 1))
        painter.drawLine(QPointF(12, 0.5), QPointF(w - 12, 0.5))


class CyberEmblemWidget(QWidget):
    """Brand mark: faceted obsidian crystal."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(24, 26)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        draw_obsidian_crystal(painter, QRectF(1, 1, self.width() - 2, self.height() - 2))


class CyberWaveformHUD(QWidget):
    """Core status chip: state dot + active task count. Repaints only on change."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(124, 26)
        self._active_tasks = 0

    def set_active_tasks(self, count: int):
        if count != self._active_tasks:
            self._active_tasks = count
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        painter.setPen(QPen(QColor(COLOR_BORDER), 1))
        painter.setBrush(QBrush(QColor(COLOR_INPUT)))
        painter.drawRoundedRect(rect, 13, 13)

        busy = self._active_tasks > 0
        dot = QColor(COLOR_ACCENT if busy else COLOR_EMERALD)
        halo = QColor(dot)
        halo.setAlpha(50)
        cy = self.height() / 2.0
        painter.setPen(Qt.NoPen)
        painter.setBrush(halo)
        painter.drawEllipse(QPointF(13, cy), 5.5, 5.5)
        painter.setBrush(dot)
        painter.drawEllipse(QPointF(13, cy), 3, 3)

        painter.setPen(QColor(COLOR_TEXT_DIM))
        painter.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
        text = f"Core busy · {self._active_tasks}" if busy else "Core idle"
        painter.drawText(QRectF(24, 0, self.width() - 28, self.height()), Qt.AlignLeft | Qt.AlignVCenter, text)


class CyberGaugeWidget(QWidget):
    """Ring gauge (CPU / RAM / GPU): thin 2.5px arc, smoothly interpolated value."""
    def __init__(self, label: str, accent_hex: str, parent=None):
        super().__init__(parent)
        self.label = label
        self.accent_color = QColor(accent_hex)
        self.value_pct = 0.0
        self._shown = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(600)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim_value)
        self.setFixedSize(84, 28)

    def _on_anim_value(self, v):
        self._shown = float(v)
        self.update()

    def set_value(self, pct: float):
        self.value_pct = max(0.0, min(100.0, pct))
        self._anim.stop()
        self._anim.setStartValue(self._shown)
        self._anim.setEndValue(self.value_pct)
        self._anim.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        arc_rect = QRectF(4, 4, 20, 20)
        painter.setPen(QPen(QColor("#1C222D"), 2.5))
        painter.drawArc(arc_rect, 0, 360 * 16)

        if self._shown >= 92:
            col = QColor(COLOR_CRIMSON)
        elif self._shown >= 80:
            col = QColor(COLOR_AMBER)
        else:
            col = self.accent_color
        pen = QPen(col, 2.5)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawArc(arc_rect, 90 * 16, int(-360 * 16 * (self._shown / 100.0)))

        painter.setPen(QColor(COLOR_TEXT_MUTED))
        painter.setFont(QFont("Segoe UI", 7, QFont.DemiBold))
        painter.drawText(QRectF(30, 2, 54, 12), Qt.AlignLeft | Qt.AlignVCenter, self.label)
        painter.setPen(QColor(COLOR_TEXT_MAIN))
        painter.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        painter.drawText(QRectF(30, 13, 54, 14), Qt.AlignLeft | Qt.AlignVCenter, f"{self._shown:.0f}%")


class NeonProgressBar(QWidget):
    """Slim progress bar with status line. Repaints only on progress change."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(24)
        self._progress = 0.0
        self._status_text = "Система готова к выполнению задач"

    def set_progress(self, pct: float, status_text: str = ""):
        self._progress = max(0.0, min(100.0, pct))
        if status_text:
            self._status_text = status_text
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        bg_rect = QRectF(0.5, 0.5, w - 1, h - 1)
        painter.setPen(QPen(QColor(COLOR_BORDER), 1))
        painter.setBrush(QBrush(QColor(COLOR_INPUT)))
        painter.drawRoundedRect(bg_rect, 6, 6)

        if self._progress > 0:
            fill_w = max(6.0, (w - 4) * (self._progress / 100.0))
            done = self._progress >= 99.9
            grad = QLinearGradient(0, 0, fill_w, 0)
            grad.setColorAt(0.0, QColor("#1E5E4A" if done else "#2B3390"))
            grad.setColorAt(1.0, QColor(COLOR_EMERALD if done else COLOR_ACCENT))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(QRectF(2, 2, fill_w, h - 4), 4, 4)

        painter.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
        painter.setPen(QColor(COLOR_TEXT_MAIN))
        text_rect = bg_rect.adjusted(10, 0, -10, 0)
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter,
                         painter.fontMetrics().elidedText(self._status_text, Qt.ElideRight, int(text_rect.width()) - 60))
        painter.setPen(QColor(COLOR_TEXT_DIM))
        painter.drawText(text_rect, Qt.AlignRight | Qt.AlignVCenter, f"{self._progress:.1f}%")


class OutputDirectoryBar(HoloCard):
    """Output routing bar."""
    def __init__(self, parent=None):
        super().__init__(accent_hex=COLOR_PURPLE, parent=parent)
        self.setFixedHeight(46)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 4, 14, 4)
        lay.setSpacing(10)

        lbl_tag = QLabel("Папка сохранения")
        lbl_tag.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-weight: 600; font-size: 12px;")
        lay.addWidget(lbl_tag)

        self.chk_custom = QCheckBox("Сохранять все результаты в выбранную папку (иначе — рядом с исходным файлом):")
        self.chk_custom.setChecked(OutputDirectoryManager.use_custom_dir)
        self.chk_custom.toggled.connect(self._on_mode_toggled)
        lay.addWidget(self.chk_custom)

        self.ed_dir = QLineEdit(OutputDirectoryManager.custom_dir_path)
        self.ed_dir.setEnabled(OutputDirectoryManager.use_custom_dir)
        self.ed_dir.textChanged.connect(self._on_path_changed)
        lay.addWidget(self.ed_dir, 1)

        self.btn_browse = QPushButton("Выбрать папку…")
        self.btn_browse.setCursor(Qt.PointingHandCursor)
        self.btn_browse.clicked.connect(self._browse_dir)
        lay.addWidget(self.btn_browse)

        self.btn_open = QPushButton("Открыть папку")
        self.btn_open.setCursor(Qt.PointingHandCursor)
        self.btn_open.clicked.connect(self._open_current_dir)
        lay.addWidget(self.btn_open)

    def _on_mode_toggled(self, checked: bool):
        OutputDirectoryManager.use_custom_dir = checked
        self.ed_dir.setEnabled(checked)

    def _on_path_changed(self, text: str):
        OutputDirectoryManager.custom_dir_path = text.strip()

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Выберите единую папку для сохранения результатов", self.ed_dir.text())
        if d:
            self.ed_dir.setText(d)
            self.chk_custom.setChecked(True)

    def _open_current_dir(self):
        target = OutputDirectoryManager.resolve_output_dir()
        os.makedirs(target, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(target)


class DropZoneBanner(HoloCard):
    """Drag-and-drop hub."""
    files_dropped = Signal(list)
    paste_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(accent_hex=COLOR_CYAN, parent=parent)
        self.setAcceptDrops(True)
        self.setFixedHeight(50)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 4, 16, 4)

        self.lbl_icon = QLabel("Drop zone")
        self.lbl_icon.setStyleSheet(f"color: {COLOR_TEXT_MAIN}; font-weight: 600; font-size: 13px;")

        self.lbl_hint = QLabel(
            "Перетащите видео, аудио, PDF, фото, документы или архивы сюда  ·  Ctrl+V — вставка ссылки или файла"
        )
        self.lbl_hint.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 12px;")

        self.btn_paste = QPushButton("Вставить из буфера  Ctrl+V")
        self.btn_paste.setCursor(Qt.PointingHandCursor)
        self.btn_paste.clicked.connect(self.paste_requested.emit)

        layout.addWidget(self.lbl_icon)
        layout.addSpacing(8)
        layout.addWidget(self.lbl_hint, 1)
        layout.addWidget(self.btn_paste)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = []
        if event.mimeData().hasUrls():
            for u in event.mimeData().urls():
                local = u.toLocalFile()
                paths.append(local if local else u.toString())
        elif event.mimeData().hasText():
            paths.append(event.mimeData().text().strip())
        if paths:
            self.files_dropped.emit(paths)


class FramelessTitleBar(QWidget):
    """Custom titlebar: brand block, ADMIN/USER mode badge, core status, gauges, window controls."""
    bootstrap_requested = Signal()

    def __init__(self, parent_window: QWidget):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self._drag_pos = QPoint()
        self.setFixedHeight(48)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("TitleBar")
        self.setStyleSheet(
            f"QWidget#TitleBar {{ background-color: {COLOR_PANEL}; border-bottom: 1px solid {COLOR_BORDER}; }}"
            f"QWidget#TitleBar QLabel, QWidget#TitleBar > QWidget {{ background: transparent; }}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 8, 0)
        layout.setSpacing(10)

        self.emblem = CyberEmblemWidget()
        layout.addWidget(self.emblem)

        self.lbl_logo = QLabel("CyberObsidian")
        self.lbl_logo.setStyleSheet(f"color: {COLOR_TEXT_MAIN}; font-weight: 700; font-size: 14px;")
        layout.addWidget(self.lbl_logo)

        self.lbl_version = QLabel("Core 5.9")
        self.lbl_version.setStyleSheet(
            f"color: {COLOR_TEXT_DIM}; background-color: #1A1F2B; border: 1px solid {COLOR_INPUT_BORDER};"
            f" border-radius: 5px; padding: 1px 6px; font-size: 11px; font-weight: 600;"
        )
        layout.addWidget(self.lbl_version)
        layout.addSpacing(6)

        admin_active = is_admin()
        badge_text = "Admin" if admin_active else "User mode · включить Admin"
        badge_color = COLOR_EMERALD if admin_active else COLOR_AMBER
        self.btn_mode = QPushButton(badge_text)
        self.btn_mode.setCursor(Qt.PointingHandCursor)
        self.btn_mode.setToolTip(
            "Нажмите, чтобы узнать разницу между режимами или перезапустить программу с правами Администратора."
        )
        self.btn_mode.setStyleSheet(f"""
            QPushButton {{
                color: {badge_color};
                background-color: transparent;
                border: 1px solid {COLOR_INPUT_BORDER};
                border-radius: 13px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #1A1F2B;
                border: 1px solid {badge_color};
            }}
        """)
        self.btn_mode.clicked.connect(self._on_mode_badge_clicked)
        layout.addWidget(self.btn_mode)

        self.waveform = CyberWaveformHUD()
        layout.addWidget(self.waveform)

        layout.addStretch(1)

        self.gauge_cpu = CyberGaugeWidget("CPU", COLOR_ACCENT)
        self.gauge_ram = CyberGaugeWidget("RAM", COLOR_ACCENT)
        self.gauge_gpu = CyberGaugeWidget("GPU", COLOR_ACCENT)
        layout.addWidget(self.gauge_cpu)
        layout.addWidget(self.gauge_ram)
        layout.addWidget(self.gauge_gpu)

        self.btn_tools = QPushButton("CLI утилиты и портативность")
        self.btn_tools.setObjectName("PurpleActionBtn")
        self.btn_tools.setCursor(Qt.PointingHandCursor)
        self.btn_tools.clicked.connect(self.bootstrap_requested.emit)
        layout.addWidget(self.btn_tools)

        self.btn_min = QPushButton("—")
        self.btn_max = QPushButton("▢")
        self.btn_close = QPushButton("✕")
        for b in (self.btn_min, self.btn_max):
            b.setObjectName("WindowCtrlBtn")
            b.setFixedSize(34, 28)
            b.setCursor(Qt.PointingHandCursor)
        self.btn_close.setObjectName("WindowCloseBtn")
        self.btn_close.setFixedSize(34, 28)
        self.btn_close.setCursor(Qt.PointingHandCursor)

        self.btn_min.clicked.connect(self.parent_window.showMinimized)
        self.btn_max.clicked.connect(self._toggle_maximize)
        self.btn_close.clicked.connect(self.parent_window.close)

        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_max)
        layout.addWidget(self.btn_close)

        self._telemetry_timer = QTimer(self)
        self._telemetry_timer.timeout.connect(self._update_telemetry)
        self._telemetry_timer.start(1500)
        self._gpu_tick = 0
        self._cached_gpu = 0.0
        self._update_telemetry()

    def _on_mode_badge_clicked(self):
        if is_admin():
            QMessageBox.information(
                self,
                "Режим Администратора активен",
                "Вы работаете в режиме [ADMIN MODE: ACTIVE].\n\n"
                "Что это дает:\n"
                "• Дочерним процессам рендера (FFmpeg, Real-ESRGAN) автоматически назначается повышенный приоритет Windows (HIGH_PRIORITY_CLASS).\n"
                "• Пакетный менеджер может устанавливать утилиты без лишних запросов UAC."
            )
        else:
            ans = QMessageBox.question(
                self,
                "Переключение в ADMIN MODE",
                "Сейчас программа запущена в обычном режиме пользователя [USER MODE].\n\n"
                "В режиме Администратора [ADMIN MODE]:\n"
                "1. Процессам рендера видео назначается высокий приоритет CPU (HIGH_PRIORITY_CLASS).\n"
                "2. Установка системных CLI-утилит проходит быстрее и без ошибок доступа.\n\n"
                "Перезапустить программу с правами Администратора прямо сейчас?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if ans == QMessageBox.Yes:
                elevate_to_admin()

    def _toggle_maximize(self):
        if self.parent_window.isMaximized():
            self.parent_window.showNormal()
        else:
            self.parent_window.showMaximized()

    def _update_telemetry(self):
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            self.gauge_cpu.set_value(cpu)
            self.gauge_ram.set_value(ram)

            self._gpu_tick = (self._gpu_tick + 1) % 3
            if self._gpu_tick == 1:
                try:
                    proc = subprocess.run(
                        ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                        capture_output=True,
                        text=True,
                        timeout=0.4,
                        creationflags=CREATE_NO_WINDOW,
                    )
                    if proc.returncode == 0 and proc.stdout.strip():
                        self._cached_gpu = float(proc.stdout.strip().splitlines()[0])
                except Exception:
                    self._cached_gpu = min(100.0, cpu * 0.6)
            self.gauge_gpu.set_value(self._cached_gpu)
        except Exception:
            pass

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.parent_window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and not self.parent_window.isMaximized():
            self.parent_window.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._toggle_maximize()


def animate_widget_fade_in(widget: QWidget, duration_ms: int = 180):
    """Fade page in, then drop the opacity effect so tables render without offscreen compositing."""
    eff = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(eff)
    anim = QPropertyAnimation(eff, b"opacity", widget)
    anim.setDuration(duration_ms)
    anim.setStartValue(0.25)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.finished.connect(lambda: widget.setGraphicsEffect(None) if widget.graphicsEffect() is eff else None)
    anim.start(QPropertyAnimation.DeleteWhenStopped)
