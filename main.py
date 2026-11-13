# -*- coding: utf-8 -*-
"""
main.py — Главный контроллер окна CYBER-OBSIDIAN MEDIA & DOCUMENT CORE v5.9.
Добавлено:
- Умная авто-подстройка размера окна под разрешение и масштаб монитора пользователя при старте
- Изменение размера безрамочного окна мышкой за любой край и любой угол (8-way Edge Resize) + QSizeGrip
"""

import os
import re
import sys
import ctypes
from typing import Dict

from PySide6.QtCore import Qt, QRect, QRectF, QPoint, QPointF, QSize, QThread
from PySide6.QtGui import (
    QKeySequence, QShortcut, QFont, QColor, QCursor, QIcon, QPainter, QPainterPath, QPen, QPixmap
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QFrame, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QPlainTextEdit, QDialog,
    QCheckBox, QFileDialog, QMessageBox, QSizeGrip, QComboBox, QTabBar
)

from core_engine import (
    BatchProcessEngine, TaskSpec, AutoBootstrapperThread,
    get_tools_status, verify_tool_works, TOOL_REGISTRY, get_bin_dir,
    bundle_portable_distribution
)
from ui_cyber_widgets import (
    CYBER_OBSIDIAN_QSS, FramelessTitleBar, NeonProgressBar,
    DropZoneBanner, OutputDirectoryBar, HoloCard, create_cyber_app_icon,
    animate_widget_fade_in, COLOR_CYAN, COLOR_EMERALD, COLOR_AMBER, COLOR_CRIMSON,
    COLOR_TEXT_DIM, COLOR_INPUT
)
from mod_studio import MediaStudioModule
from mod_downloader import UltimateDownloaderModule
from mod_converter import UniversalConverterModule
from mod_ai_lab import LocalAILabModule

# Decorative emoji to strip from module UI text (listed set + pictograph / misc-symbol blocks).
_EMOJI_RE = re.compile(
    "[⚡🎬🚀🔄🧠📋📂🔍🎧✨🎯🟢⚙↗\u2600-\u26FF\U0001F300-\U0001FAFF\uFE0F\u200D]"
)


def _clean_text(text: str) -> str:
    return re.sub(r"\s{2,}", " ", _EMOJI_RE.sub("", text)).strip()


def sanitize_ui_emojis(root_widget: QWidget):
    """Strip decorative emoji from buttons, labels, checkboxes, combo items and tab titles under root."""
    for w in [root_widget] + root_widget.findChildren(QWidget):
        if isinstance(w, (QPushButton, QLabel, QCheckBox)):
            text = w.text()
            clean = _clean_text(text) if text else ""
            if clean and clean != text:  # never blank icon-only buttons
                w.setText(clean)
        elif isinstance(w, QComboBox):
            for i in range(w.count()):
                clean = _clean_text(w.itemText(i))
                if clean:
                    w.setItemText(i, clean)
        elif isinstance(w, QTabBar):
            for i in range(w.count()):
                clean = _clean_text(w.tabText(i))
                if clean:
                    w.setTabText(i, clean)


def make_line_icon(kind: str, color: str = COLOR_TEXT_DIM, size: int = 18) -> QIcon:
    """Minimal 1.5px stroke icons drawn with QPainter."""
    pix = QPixmap(size * 2, size * 2)  # 2x for HiDPI crispness
    pix.setDevicePixelRatio(2.0)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    s = float(size)
    if kind == "studio":  # film frame + play
        p.drawRoundedRect(QRectF(2.5, 4, s - 5, s - 8), 2.5, 2.5)
        tri = QPainterPath(QPointF(s * 0.42, s * 0.36))
        tri.lineTo(QPointF(s * 0.64, s * 0.5))
        tri.lineTo(QPointF(s * 0.42, s * 0.64))
        tri.closeSubpath()
        p.drawPath(tri)
    elif kind == "download":  # arrow into tray
        p.drawLine(QPointF(s / 2, 3), QPointF(s / 2, s * 0.62))
        p.drawPolyline([QPointF(s * 0.3, s * 0.44), QPointF(s / 2, s * 0.64), QPointF(s * 0.7, s * 0.44)])
        p.drawPolyline([QPointF(3, s * 0.68), QPointF(3, s - 3), QPointF(s - 3, s - 3), QPointF(s - 3, s * 0.68)])
    elif kind == "convert":  # two opposite arrows
        p.drawLine(QPointF(3, s * 0.35), QPointF(s - 4, s * 0.35))
        p.drawPolyline([QPointF(s * 0.66, s * 0.18), QPointF(s - 4, s * 0.35), QPointF(s * 0.66, s * 0.52)])
        p.drawLine(QPointF(s - 3, s * 0.68), QPointF(4, s * 0.68))
        p.drawPolyline([QPointF(s * 0.34, s * 0.51), QPointF(4, s * 0.68), QPointF(s * 0.34, s * 0.85)])
    elif kind == "ai":  # chip with pins
        p.drawRoundedRect(QRectF(s * 0.27, s * 0.27, s * 0.46, s * 0.46), 2, 2)
        p.drawRect(QRectF(s * 0.42, s * 0.42, s * 0.16, s * 0.16))
        for t in (0.4, 0.6):
            p.drawLine(QPointF(s * t, 2.5), QPointF(s * t, s * 0.27))
            p.drawLine(QPointF(s * t, s * 0.73), QPointF(s * t, s - 2.5))
            p.drawLine(QPointF(2.5, s * t), QPointF(s * 0.27, s * t))
            p.drawLine(QPointF(s * 0.73, s * t), QPointF(s - 2.5, s * t))
    elif kind == "queue":  # list rows with bullets
        for y in (0.28, 0.5, 0.72):
            p.drawPoint(QPointF(4, s * y))
            p.drawLine(QPointF(7.5, s * y), QPointF(s - 3, s * y))
    elif kind == "terminal":  # prompt chevron + cursor line
        p.drawRoundedRect(QRectF(2.5, 3.5, s - 5, s - 7), 2.5, 2.5)
        p.drawPolyline([QPointF(s * 0.3, s * 0.4), QPointF(s * 0.44, s * 0.52), QPointF(s * 0.3, s * 0.64)])
        p.drawLine(QPointF(s * 0.52, s * 0.66), QPointF(s * 0.7, s * 0.66))
    elif kind == "tools":  # sliders
        for y, kx in ((0.3, 0.65), (0.7, 0.35)):
            p.drawLine(QPointF(3, s * y), QPointF(s - 3, s * y))
            p.setBrush(QColor("#0E1117"))
            p.drawEllipse(QPointF(s * kx, s * y), 2.4, 2.4)
            p.setBrush(Qt.NoBrush)
    p.end()
    return QIcon(pix)


class BootstrapperDialog(QDialog):
    """Менеджер CLI-утилит v5.9 с адаптивным размером окна."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Автономный Менеджер CLI-Утилит и Самодиагностика v5.9")
        self.resize(960, 580)
        self.setMinimumSize(720, 440)
        self.setStyleSheet(CYBER_OBSIDIAN_QSS)
        self.worker: AutoBootstrapperThread = None
        self.checkboxes: Dict[str, QCheckBox] = {}

        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        lbl = QLabel("⚙ МЕНЕДЖЕР УТИЛИТ, ДИАГНОСТИКА DLL И ПОРТАТИВНАЯ СБОРКА")
        lbl.setObjectName("SectionTitle")
        lay.addWidget(lbl)

        hint = QLabel(
            "💡 Конвертация PDF, DOCX, изображений, очистка EXIF и архивы УЖЕ РАБОТАЮТ ИЗ КОРОБКИ через встроенное ядро Python!\n"
            "Нажмите «🩺 Проверить работу утилит (Self-Test)», чтобы убедиться, что все установленные .exe запускаются без ошибок DLL."
        )
        hint.setObjectName("SubLabel")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        sel_row = QHBoxLayout()
        btn_fast = QPushButton("⚡ Выбрать только быстрые портативные")
        btn_fast.clicked.connect(self._select_fast_portable)
        btn_all = QPushButton("☑ Выбрать все недостающие")
        btn_all.clicked.connect(self._select_all_missing)
        btn_none = QPushButton("☐ Снять выделение")
        btn_none.clicked.connect(self._select_none)
        btn_test = QPushButton("🩺 Проверить работу утилит (Self-Test)")
        btn_test.setObjectName("PurpleActionBtn")
        btn_test.clicked.connect(self._run_self_test)

        sel_row.addWidget(btn_fast)
        sel_row.addWidget(btn_all)
        sel_row.addWidget(btn_none)
        sel_row.addWidget(btn_test)
        lay.addLayout(sel_row)

        self.tbl = QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels([
            "Выбор", "Утилита", "Размер / Тип пакета", "Статус / Тест", "Путь или встроенное ядро"
        ])
        self.tbl.setWordWrap(False)
        self.tbl.setTextElideMode(Qt.ElideMiddle)

        header = self.tbl.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.tbl.setColumnWidth(0, 64)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        self.tbl.setAlternatingRowColors(True)
        lay.addWidget(self.tbl, 1)

        self.prog = NeonProgressBar()
        lay.addWidget(self.prog)

        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(120)
        lay.addWidget(self.log_box)

        btns = QHBoxLayout()
        self.btn_install = QPushButton("🚀 Установить отмеченные утилиты")
        self.btn_install.setObjectName("CyanActionBtn")
        self.btn_install.setMinimumHeight(38)
        self.btn_install.clicked.connect(self._start_bootstrap)

        self.btn_stop = QPushButton("⏹ Остановить")
        self.btn_stop.setObjectName("DangerBtn")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_bootstrap)

        btn_bundle = QPushButton("📦 Упаковать Portable ZIP (для раздачи)")
        btn_bundle.setObjectName("EmeraldActionBtn")
        btn_bundle.clicked.connect(self._export_portable_zip)

        btn_open_bin = QPushButton("📂 Папка ./bin")
        btn_open_bin.clicked.connect(lambda: os.startfile(get_bin_dir()) if sys.platform == "win32" else None)

        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.accept)

        btns.addWidget(self.btn_install, 2)
        btns.addWidget(self.btn_stop)
        btns.addWidget(btn_bundle, 2)
        btns.addWidget(btn_open_bin)
        btns.addWidget(btn_close)
        lay.addLayout(btns)

        self._refresh_table(get_tools_status())

    def _refresh_table(self, status_map: dict):
        self.tbl.setRowCount(0)
        self.checkboxes.clear()

        for key, (found, path_str) in status_map.items():
            info = TOOL_REGISTRY.get(key, {})
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)

            chk_w = QWidget()
            chk_w.setStyleSheet("background: transparent;")
            chk_l = QHBoxLayout(chk_w)
            chk_l.setContentsMargins(0, 0, 0, 0)
            chk_l.setAlignment(Qt.AlignCenter)
            chk = QCheckBox()
            is_fast = info.get("fast_portable") == "true"
            chk.setChecked(not found and is_fast)
            chk.setEnabled(not found)
            chk_l.addWidget(chk)
            self.checkboxes[key] = chk
            self.tbl.setCellWidget(r, 0, chk_w)

            self.tbl.setItem(r, 1, QTableWidgetItem(info.get("name", key)))
            self.tbl.setItem(r, 2, QTableWidgetItem(info.get("size_hint", "")))

            if found:
                st_item = QTableWidgetItem("✔ УСТАНОВЛЕН")
                st_item.setForeground(QColor(COLOR_EMERALD))
            elif info.get("builtin_fallback") == "true":
                st_item = QTableWidgetItem("⚡ ЯДРО PYTHON")
                st_item.setForeground(QColor(COLOR_CYAN))
            else:
                st_item = QTableWidgetItem("✖ НЕ НАЙДЕН")
                st_item.setForeground(QColor(COLOR_AMBER))

            self.tbl.setItem(r, 3, st_item)

            path_item = QTableWidgetItem(path_str)
            path_item.setToolTip(path_str)
            self.tbl.setItem(r, 4, path_item)

    def _run_self_test(self):
        self.log_box.appendPlainText("\n=== [SELF-TEST] ПРОВЕРКА РАБОТОСПОСОБНОСТИ УТИЛИТ ===")
        status_map = get_tools_status()
        for row, (key, (found, path_str)) in enumerate(status_map.items()):
            name = TOOL_REGISTRY[key]["name"]
            if not found:
                continue
            ok, msg = verify_tool_works(key)
            st_item = QTableWidgetItem("✔ ПРОВЕРЕН (OK)" if ok else "⚠ ОШИБКА ЗАПУСКА")
            st_item.setForeground(QColor(COLOR_EMERALD if ok else COLOR_CRIMSON))
            self.tbl.setItem(row, 3, st_item)
            self.log_box.appendPlainText(f"  [{'OK' if ok else 'ERR'}] {name}: {msg} ({path_str})")
            QApplication.processEvents()
        self.prog.set_progress(100.0, "Самодиагностика утилит завершена")

    def _select_fast_portable(self):
        for k, chk in self.checkboxes.items():
            if chk.isEnabled():
                chk.setChecked(TOOL_REGISTRY.get(k, {}).get("fast_portable") == "true")

    def _select_all_missing(self):
        for chk in self.checkboxes.values():
            if chk.isEnabled():
                chk.setChecked(True)

    def _select_none(self):
        for chk in self.checkboxes.values():
            chk.setChecked(False)

    def _start_bootstrap(self):
        selected = [k for k, chk in self.checkboxes.items() if chk.isChecked() and chk.isEnabled()]
        if not selected:
            QMessageBox.information(self, "Менеджер утилит", "Отметьте галочками хотя бы одну утилиту для установки!")
            return

        self.btn_install.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.worker = AutoBootstrapperThread(target_keys=selected)
        self.worker.progress_signal.connect(self.prog.set_progress)
        self.worker.log_signal.connect(self.log_box.appendPlainText)
        self.worker.finished_signal.connect(self._on_done)
        self.worker.start()

    def _stop_bootstrap(self):
        if self.worker:
            self.worker.request_abort()
            self.log_box.appendPlainText("[USER] Принудительная остановка текущего установщика...")

    def _on_done(self, status_map: dict):
        self.btn_install.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._refresh_table(status_map)

    def _export_portable_zip(self):
        p, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить готовый к раздаче Portable ZIP",
            os.path.join(os.path.expanduser("~"), "Desktop", "CyberObsidianCore_Portable.zip"),
            "ZIP Archive (*.zip)",
        )
        if not p:
            return
        self.log_box.appendPlainText("[BUNDLE] Упаковка программы и папки ./bin в единый портативный архив...")
        QApplication.processEvents()
        ok, msg = bundle_portable_distribution(p)
        if ok:
            QMessageBox.information(self, "Портативный дистрибутив готов", msg)
        else:
            QMessageBox.critical(self, "Ошибка упаковки", msg)


class CyberObsidianMainWindow(QMainWindow):
    """
    Главное безрамочное окно комбайна v5.9 с поддержкой изменения размеров за любой край и угол
    (8-направленный ресайз мышкой + QSizeGrip + авто-вписывание в экран монитора).
    """
    RESIZE_MARGIN = 7

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CYBER-OBSIDIAN MEDIA & DOCUMENT CORE v5.9")
        self.setMinimumSize(940, 580)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowMinMaxButtonsHint)
        self.setStyleSheet(CYBER_OBSIDIAN_QSS)
        self.setMouseTracking(True)

        # Состояние для изменения размера окна за края
        self._resizing = False
        self._resize_edges = Qt.Edges()
        self._resize_start_pos = QPoint()
        self._resize_start_geom = QRect()

        self.engine = BatchProcessEngine(max_concurrent=2)
        self.task_rows: Dict[str, int] = {}

        self._build_layout()
        self._connect_engine_signals()
        self._fit_to_user_screen()

        self.shortcut_paste = QShortcut(QKeySequence("Ctrl+V"), self)
        self.shortcut_paste.activated.connect(self._handle_clipboard_paste)

    def _fit_to_user_screen(self):
        """
        Автоматически определяет размер и масштаб монитора пользователя (например, 1366x768 или 1920x1080 @ 125%)
        и подбирает комфортный размер окна, чтобы оно никогда не вылезало за пределы экрана!
        """
        screen = QApplication.primaryScreen()
        if not screen:
            self.resize(1280, 800)
            return

        avail = screen.availableGeometry()
        target_w = min(1400, int(avail.width() * 0.90))
        target_h = min(880, int(avail.height() * 0.90))
        target_w = max(self.minimumWidth(), target_w)
        target_h = max(self.minimumHeight(), target_h)

        self.resize(target_w, target_h)
        # Центрируем окно ровно по центру монитора
        x = avail.x() + (avail.width() - target_w) // 2
        y = avail.y() + (avail.height() - target_h) // 2
        self.move(max(avail.x(), x), max(avail.y(), y))

    def _build_layout(self):
        central = QWidget()
        central.setMouseTracking(True)
        self.setCentralWidget(central)
        main_vbox = QVBoxLayout(central)
        # Отступ 4px по периметру, чтобы мышкой было удобно хвататься за любой край окна
        main_vbox.setContentsMargins(4, 4, 4, 4)
        main_vbox.setSpacing(0)

        self.titlebar = FramelessTitleBar(self)
        self.titlebar.bootstrap_requested.connect(self._open_bootstrapper)
        main_vbox.addWidget(self.titlebar)

        body_hbox = QHBoxLayout()
        body_hbox.setContentsMargins(0, 0, 0, 0)
        body_hbox.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("SideBar")
        sidebar.setFixedWidth(255)
        sb_lay = QVBoxLayout(sidebar)
        sb_lay.setContentsMargins(10, 12, 10, 12)
        sb_lay.setSpacing(6)

        lbl_nav = QLabel("⚡ НАВИГАЦИЯ ЯДРА v5.9")
        lbl_nav.setObjectName("SectionTitle")
        sb_lay.addWidget(lbl_nav)

        self.nav_buttons = []
        nav_items = [
            ("🎬  1. Видео и Аудио Студия", 0),
            ("🚀  2. Загрузчик yt-dlp / Aria2c", 1),
            ("🔄  3. Конвертер «Всё во Всё»", 2),
            ("🧠  4. Локальная ИИ-Лаборатория", 3),
            ("📋  5. Пакетная Очередь Задач", 4),
        ]
        for text, idx in nav_items:
            btn = QPushButton(text)
            btn.setObjectName("NavTabBtn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, i=idx: self.switch_module(i))
            sb_lay.addWidget(btn)
            self.nav_buttons.append(btn)

        sb_lay.addStretch(1)

        info_card = HoloCard(accent_hex=COLOR_EMERALD)
        info_lay = QVBoxLayout(info_card)
        info_lay.setContentsMargins(10, 8, 10, 8)
        lbl_oob = QLabel("🟢 ВСТРОЕННОЕ ЯДРО АКТИВНО")
        lbl_oob.setStyleSheet(f"color: {COLOR_EMERALD}; font-weight: 800; font-size: 11px;")
        lbl_oob_sub = QLabel("PDF, DOCX, фото, .ICO, EXIF и ZIP работают мгновенно из коробки.")
        lbl_oob_sub.setObjectName("SubLabel")
        lbl_oob_sub.setWordWrap(True)
        info_lay.addWidget(lbl_oob)
        info_lay.addWidget(lbl_oob_sub)
        sb_lay.addWidget(info_card)

        self.btn_toggle_hud = QPushButton("💻 Терминал Live CLI HUD [▲]")
        self.btn_toggle_hud.setObjectName("PurpleActionBtn")
        self.btn_toggle_hud.clicked.connect(self._toggle_cli_hud)
        sb_lay.addWidget(self.btn_toggle_hud)

        body_hbox.addWidget(sidebar)

        work_col = QVBoxLayout()
        work_col.setContentsMargins(8, 6, 8, 4)
        work_col.setSpacing(6)

        self.drop_banner = DropZoneBanner()
        self.drop_banner.files_dropped.connect(self._route_dropped_items)
        self.drop_banner.paste_requested.connect(self._handle_clipboard_paste)
        work_col.addWidget(self.drop_banner)

        self.output_bar = OutputDirectoryBar()
        work_col.addWidget(self.output_bar)

        self.stack = QStackedWidget()
        self.mod_studio = MediaStudioModule(self.engine)
        self.mod_downloader = UltimateDownloaderModule(self.engine)
        self.mod_converter = UniversalConverterModule(self.engine)
        self.mod_ai = LocalAILabModule(self.engine)
        self.mod_queue = self._build_batch_queue_page()

        self.stack.addWidget(self.mod_studio)
        self.stack.addWidget(self.mod_downloader)
        self.stack.addWidget(self.mod_converter)
        self.stack.addWidget(self.mod_ai)
        self.stack.addWidget(self.mod_queue)
        work_col.addWidget(self.stack, 1)

        # Нижняя строка: прогресс-бар + уголок захвата размера окна QSizeGrip
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(0, 0, 0, 0)
        bottom_bar.setSpacing(6)
        self.global_progress = NeonProgressBar()
        bottom_bar.addWidget(self.global_progress, 1)

        self.size_grip = QSizeGrip(self)
        self.size_grip.setFixedSize(18, 18)
        self.size_grip.setToolTip("Потяните за угол или за любой край окна, чтобы изменить размер")
        bottom_bar.addWidget(self.size_grip, 0, Qt.AlignBottom | Qt.AlignRight)
        work_col.addLayout(bottom_bar)

        self.hud_frame = self._build_cli_hud_drawer()
        work_col.addWidget(self.hud_frame)

        body_hbox.addLayout(work_col, 1)
        main_vbox.addLayout(body_hbox, 1)

        self.switch_module(0)

    # --- МЕХАНИЗМ ИЗМЕНЕНИЯ РАЗМЕРА ОКНА ЗА ЛЮБОЙ КРАЙ И УГОЛ (8 НАПРАВЛЕНИЙ) ---
    def _detect_resize_edges(self, pos: QPoint) -> Qt.Edges:
        edges = Qt.Edges()
        m = self.RESIZE_MARGIN
        w, h = self.width(), self.height()

        if pos.x() <= m:
            edges |= Qt.LeftEdge
        elif pos.x() >= w - m:
            edges |= Qt.RightEdge

        if pos.y() <= m:
            edges |= Qt.TopEdge
        elif pos.y() >= h - m:
            edges |= Qt.BottomEdge

        return edges

    def _update_cursor_for_edges(self, edges: Qt.Edges):
        if edges == (Qt.LeftEdge | Qt.TopEdge) or edges == (Qt.RightEdge | Qt.BottomEdge):
            self.setCursor(Qt.SizeFDiagCursor)
        elif edges == (Qt.RightEdge | Qt.TopEdge) or edges == (Qt.LeftEdge | Qt.BottomEdge):
            self.setCursor(Qt.SizeBDiagCursor)
        elif edges & (Qt.LeftEdge | Qt.RightEdge):
            self.setCursor(Qt.SizeHorCursor)
        elif edges & (Qt.TopEdge | Qt.BottomEdge):
            self.setCursor(Qt.SizeVerCursor)
        else:
            self.unsetCursor()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.isMaximized():
            edges = self._detect_resize_edges(event.position().toPoint())
            if edges:
                # Используем нативный системный ресайз окна Qt6/Windows (плавный 120 FPS без рывков!)
                win_handle = self.windowHandle()
                if win_handle and win_handle.startSystemResize(edges):
                    event.accept()
                    return
                self._resizing = True
                self._resize_edges = edges
                self._resize_start_pos = event.globalPosition().toPoint()
                self._resize_start_geom = self.geometry()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.isMaximized():
            self.unsetCursor()
            super().mouseMoveEvent(event)
            return

        if self._resizing:
            delta = event.globalPosition().toPoint() - self._resize_start_pos
            g = QRect(self._resize_start_geom)
            min_w, min_h = self.minimumWidth(), self.minimumHeight()

            if self._resize_edges & Qt.LeftEdge:
                new_left = g.left() + delta.x()
                if g.right() - new_left >= min_w:
                    g.setLeft(new_left)
            elif self._resize_edges & Qt.RightEdge:
                g.setWidth(max(min_w, g.width() + delta.x()))

            if self._resize_edges & Qt.TopEdge:
                new_top = g.top() + delta.y()
                if g.bottom() - new_top >= min_h:
                    g.setTop(new_top)
            elif self._resize_edges & Qt.BottomEdge:
                g.setHeight(max(min_h, g.height() + delta.y()))

            self.setGeometry(g)
            event.accept()
            return

        edges = self._detect_resize_edges(event.position().toPoint())
        self._update_cursor_for_edges(edges)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._resizing:
            self._resizing = False
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _build_batch_queue_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 6, 6, 6)
        card = HoloCard(accent_hex=COLOR_CYAN)
        c_lay = QVBoxLayout(card)

        lbl = QLabel("📋 ДИСПЕТЧЕР ПАКЕТНОЙ ОЧЕРЕДИ ЗАДАЧ (ПАРАЛЛЕЛЬНОЕ ВЫПОЛНЕНИЕ)")
        lbl.setObjectName("SectionTitle")
        c_lay.addWidget(lbl)

        self.tbl_queue = QTableWidget(0, 6)
        self.tbl_queue.setHorizontalHeaderLabels([
            "ID", "Модуль", "Задача и Выходной файл", "Прогресс / Телеметрия", "Статус", "Управление"
        ])
        self.tbl_queue.setWordWrap(False)
        self.tbl_queue.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_queue.setAlternatingRowColors(True)
        c_lay.addWidget(self.tbl_queue, 1)

        lay.addWidget(card)
        return w

    def _build_cli_hud_drawer(self) -> QFrame:
        frame = HoloCard(accent_hex=COLOR_CYAN)
        frame.setFixedHeight(185)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(10, 6, 10, 6)

        top = QHBoxLayout()
        lbl = QLabel("⚡ LIVE CLI HUD // ГЕНЕРИРУЕМАЯ КОМАНДА И ПОТОК КОНСОЛИ В РЕАЛЬНОМ ВРЕМЕНИ")
        lbl.setStyleSheet(f"color: {COLOR_CYAN}; font-weight: 800; font-family: Consolas;")
        top.addWidget(lbl)
        top.addStretch(1)

        btn_copy_cmd = QPushButton("📋 Скопировать команду")
        btn_copy_cmd.clicked.connect(lambda: QApplication.clipboard().setText(self.ed_cmd_preview.toPlainText()))
        btn_clear_log = QPushButton("🗑 Очистить консоль")
        btn_clear_log.clicked.connect(lambda: self.txt_cli_stream.clear())
        top.addWidget(btn_copy_cmd)
        top.addWidget(btn_clear_log)
        lay.addLayout(top)

        self.ed_cmd_preview = QPlainTextEdit()
        self.ed_cmd_preview.setReadOnly(True)
        self.ed_cmd_preview.setMaximumHeight(36)
        self.ed_cmd_preview.setFont(QFont("Consolas", 10))
        self.ed_cmd_preview.setStyleSheet(f"color: {COLOR_EMERALD}; background-color: #05070B;")
        self.ed_cmd_preview.setPlainText("$ Ожидание запуска задачи...")
        lay.addWidget(self.ed_cmd_preview)

        self.txt_cli_stream = QPlainTextEdit()
        self.txt_cli_stream.setReadOnly(True)
        self.txt_cli_stream.setFont(QFont("Consolas", 9))
        self.txt_cli_stream.setStyleSheet("color: #B0C4DE; background-color: #05070B;")
        lay.addWidget(self.txt_cli_stream, 1)

        frame.setVisible(False)
        return frame

    def _toggle_cli_hud(self):
        vis = not self.hud_frame.isVisible()
        self.hud_frame.setVisible(vis)
        self.btn_toggle_hud.setText("💻 Терминал Live CLI HUD [▼]" if vis else "💻 Терминал Live CLI HUD [▲]")

    def switch_module(self, index: int):
        self.stack.setCurrentIndex(index)
        animate_widget_fade_in(self.stack.currentWidget())
        for i, btn in enumerate(self.nav_buttons):
            btn.setProperty("active", "true" if i == index else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _handle_clipboard_paste(self):
        text = QApplication.clipboard().text().strip()
        if text:
            self._route_dropped_items([text])

    def _route_dropped_items(self, items: list):
        first = items[0].strip().strip('"')
        if first.startswith(("http://", "https://", "www.")):
            self.switch_module(1)
            self.mod_downloader.set_url_and_analyze(first)
            return

        if not os.path.exists(first):
            return

        ext = os.path.splitext(first)[1].lower()
        if ext in (".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"):
            self.switch_module(0)
            self.mod_studio.load_file(first)
        else:
            self.switch_module(2)
            for path in items:
                if os.path.exists(path):
                    self.mod_converter.load_external_file(path)

    def _open_bootstrapper(self):
        dlg = BootstrapperDialog(self)
        dlg.exec()

    def _connect_engine_signals(self):
        self.engine.task_added.connect(self._on_task_added)
        self.engine.task_started.connect(self._on_task_started)
        self.engine.task_progress.connect(self._on_task_progress)
        self.engine.task_log.connect(self._on_task_log)
        self.engine.task_finished.connect(self._on_task_finished)
        self.engine.active_count_changed.connect(self.titlebar.waveform.set_active_tasks)

    def _on_task_added(self, spec: TaskSpec):
        row = self.tbl_queue.rowCount()
        self.tbl_queue.insertRow(row)
        self.task_rows[spec.task_id] = row

        self.tbl_queue.setItem(row, 0, QTableWidgetItem(spec.task_id))
        self.tbl_queue.setItem(row, 1, QTableWidgetItem(spec.module_name))
        self.tbl_queue.setItem(row, 2, QTableWidgetItem(spec.title))
        self.tbl_queue.setItem(row, 3, QTableWidgetItem("0.0% | В очереди"))
        self.tbl_queue.setItem(row, 4, QTableWidgetItem("⏳ ОЖИДАНИЕ"))

        ctrl_w = QWidget()
        ctrl_l = QHBoxLayout(ctrl_w)
        ctrl_l.setContentsMargins(2, 2, 2, 2)
        ctrl_l.setSpacing(4)

        btn_pause = QPushButton("⏸")
        btn_pause.setToolTip("Пауза потока (Suspend)")
        btn_pause.clicked.connect(lambda _, tid=spec.task_id: self.engine.pause_task(tid))

        btn_resume = QPushButton("▶")
        btn_resume.setToolTip("Возобновить поток (Resume)")
        btn_resume.clicked.connect(lambda _, tid=spec.task_id: self.engine.resume_task(tid))

        btn_open = QPushButton("📂")
        btn_open.setToolTip("Открыть папку результата")
        btn_open.clicked.connect(
            lambda _, p=spec.output_path: os.startfile(p if os.path.isdir(p) else os.path.dirname(p))
            if sys.platform == "win32" and p and os.path.exists(p if os.path.isdir(p) else os.path.dirname(p))
            else None
        )

        btn_kill = QPushButton("✕")
        btn_kill.setObjectName("DangerBtn")
        btn_kill.setToolTip("Мгновенно убить дерево процессов")
        btn_kill.clicked.connect(lambda _, tid=spec.task_id: self.engine.cancel_task(tid))

        ctrl_l.addWidget(btn_pause)
        ctrl_l.addWidget(btn_resume)
        ctrl_l.addWidget(btn_open)
        ctrl_l.addWidget(btn_kill)
        self.tbl_queue.setCellWidget(row, 5, ctrl_w)

        self.global_progress.set_progress(1.0, f"ДОБАВЛЕНО В ОЧЕРЕДЬ: {spec.title}")

    def _on_task_started(self, task_id: str, cmd_str: str):
        self.ed_cmd_preview.setPlainText(f"$ {cmd_str}")
        row = self.task_rows.get(task_id)
        if row is not None:
            self.tbl_queue.setItem(row, 4, QTableWidgetItem("⚡ ВЫПОЛНЯЕТСЯ"))

    def _on_task_progress(self, task_id: str, pct: float, metrics: str):
        self.global_progress.set_progress(pct, f"[{task_id}] {metrics}")
        row = self.task_rows.get(task_id)
        if row is not None:
            self.tbl_queue.setItem(row, 3, QTableWidgetItem(f"{pct:5.1f}% | {metrics}"))

    def _on_task_log(self, task_id: str, line: str):
        self.txt_cli_stream.appendPlainText(f"[{task_id}] {line}")

    def _on_task_finished(self, task_id: str, success: bool, msg: str, out_path: str):
        row = self.task_rows.get(task_id)
        if row is not None:
            status_str = "✔ ГОТОВО" if success else "✖ ОШИБКА"
            item = QTableWidgetItem(status_str)
            item.setForeground(QColor(COLOR_EMERALD if success else "#FF2A6D"))
            self.tbl_queue.setItem(row, 4, item)
            self.tbl_queue.setItem(row, 3, QTableWidgetItem(msg[:90]))

        if success:
            self.global_progress.set_progress(100.0, f"✔ ВЫПОЛНЕНО: {os.path.basename(out_path)}")
        else:
            self.global_progress.set_progress(0.0, f"✖ ОШИБКА [{task_id}]: {msg[:65]}")

    def closeEvent(self, event):
        self.engine.queue.clear()
        for worker in list(self.engine.active_workers.values()):
            worker.kill_process_tree()
        for worker in self.engine.findChildren(QThread):
            if worker.isRunning():
                worker.wait(3000)
        pw = getattr(self.mod_downloader, "probe_worker", None)
        if pw and pw.isRunning():
            pw.wait(3000)
        super().closeEvent(event)


def main():
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("CyberObsidian.Core.v5.9")
        except Exception:
            pass

    get_bin_dir()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("CyberObsidianCore")

    app_icon = create_cyber_app_icon()
    app.setWindowIcon(app_icon)

    win = CyberObsidianMainWindow()
    win.setWindowIcon(app_icon)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()