"""
mod_downloader.py — Модуль 2: Ультимативный Загрузчик (yt-dlp + Aria2c + SponsorBlock) v5.9.
"""

import os
import json
import time
import uuid
import shutil
import psutil
import webbrowser
import urllib.request
import subprocess
from typing import Dict, Any, List, Optional, Tuple

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
    QDialog, QPlainTextEdit, QApplication
)

from core_engine import (
    BatchProcessEngine, TaskSpec, OutputDirectoryManager,
    resolve_tool, get_bin_dir, CREATE_NO_WINDOW
)
from ui_cyber_widgets import (
    CYBER_OBSIDIAN_QSS, HoloCard, COLOR_CYAN, COLOR_EMERALD, COLOR_PURPLE, COLOR_AMBER
)

BROWSER_PROFILES: List[Tuple[str, str, str, str]] = [
    ("Не использовать (Публичный доступ)", "none", "", ""),
    ("📄 Готовый кэш / файл cookies.txt (100% обход v20 и 18+)", "file", "", ""),
    ("🦊 Mozilla Firefox (Не имеет блокировки v20)", "firefox", "", "firefox.exe"),
    ("🟢 Google Chrome", "chrome", r"%LOCALAPPDATA%\Google\Chrome\User Data", "chrome.exe"),
    ("🔵 Microsoft Edge", "edge", r"%LOCALAPPDATA%\Microsoft\Edge\User Data", "msedge.exe"),
    ("🎮 Opera GX", "opera", r"%APPDATA%\Opera Software\Opera GX Stable", "opera.exe"),
    ("🔴 Opera (Обычная)", "opera", r"%APPDATA%\Opera Software\Opera Stable", "opera.exe"),
    ("🟡 Яндекс.Браузер (Yandex)", "chrome", r"%LOCALAPPDATA%\Yandex\YandexBrowser\User Data", "browser.exe"),
    ("🦁 Brave Browser", "brave", r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data", "brave.exe"),
    ("🟣 Vivaldi", "vivaldi", r"%LOCALAPPDATA%\Vivaldi\User Data", "vivaldi.exe"),
]

YOUTUBE_STRICT_AUTH_NAMES = {
    "SID", "HSID", "SSID", "APISID", "SAPISID",
    "LOGIN_INFO", "__Secure-1PSID", "__Secure-3PSID", "__Secure-1PAPISID", "__Secure-3PAPISID"
}


def get_universal_cached_cookies_path() -> str:
    return os.path.join(get_bin_dir(), "obsidian_cookies.txt")


def get_runtime_cookie_copy_path(source_cookie_file: str) -> str:
    runtime_copy = os.path.join(get_bin_dir(), "obsidian_cookies_runtime.txt")
    try:
        if os.path.abspath(source_cookie_file) != os.path.abspath(runtime_copy):
            shutil.copy2(source_cookie_file, runtime_copy)
            return runtime_copy
    except Exception:
        pass
    return source_cookie_file


def verify_cookie_file_authenticity(file_path: str) -> Tuple[bool, int, int, bool]:
    if not file_path or not os.path.isfile(file_path):
        return False, 0, 0, False

    total_cookies = 0
    yt_auth_count = 0
    google_auth_count = 0
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                parts = s.split("\t")
                if len(parts) >= 7:
                    total_cookies += 1
                    domain, cookie_name = parts[0].lower(), parts[5]
                    if "youtube.com" in domain and cookie_name in YOUTUBE_STRICT_AUTH_NAMES:
                        yt_auth_count += 1
                    elif "google.com" in domain and cookie_name in YOUTUBE_STRICT_AUTH_NAMES:
                        google_auth_count += 1
    except Exception:
        return False, 0, 0, False

    only_google = (yt_auth_count == 0 and google_auth_count > 0)
    return (yt_auth_count >= 3), total_cookies, yt_auth_count, only_google


def find_running_browser_exe(exe_name: str) -> Optional[str]:
    if not exe_name:
        return None
    target = exe_name.lower()
    for proc in psutil.process_iter(["name", "exe"]):
        try:
            if (proc.info.get("name") or "").lower() == target:
                return proc.info.get("exe")
        except Exception:
            pass
    return None


def gracefully_close_browser(exe_name: str):
    if not exe_name:
        return
    target = exe_name.lower()
    for proc in psutil.process_iter(["name"]):
        try:
            if (proc.info.get("name") or "").lower() == target:
                proc.terminate()
        except Exception:
            pass

    for _ in range(15):
        if not find_running_browser_exe(exe_name):
            break
        time.sleep(0.2)

    for proc in psutil.process_iter(["name"]):
        try:
            if (proc.info.get("name") or "").lower() == target:
                proc.kill()
        except Exception:
            pass
    time.sleep(0.3)


def build_cookie_cli_args(browser_idx: int, cookie_txt_path: str = "") -> List[str]:
    if browser_idx <= 0 or browser_idx >= len(BROWSER_PROFILES):
        return []

    _, ytdlp_key, raw_profile_dir, _ = BROWSER_PROFILES[browser_idx]

    if ytdlp_key == "file":
        if cookie_txt_path and os.path.isfile(cookie_txt_path):
            return ["--cookies", get_runtime_cookie_copy_path(cookie_txt_path)]
        return []

    if cookie_txt_path and os.path.isfile(cookie_txt_path):
        is_valid, _, _, _ = verify_cookie_file_authenticity(cookie_txt_path)
        if is_valid:
            return ["--cookies", get_runtime_cookie_copy_path(cookie_txt_path)]

    if raw_profile_dir:
        expanded = os.path.expandvars(raw_profile_dir)
        if os.path.isdir(expanded):
            return ["--cookies-from-browser", f"{ytdlp_key}:{expanded}"]
    return ["--cookies-from-browser", ytdlp_key]


class CookieAssistantDialog(QDialog):
    """Универсальный Мастер Захвата и Строгой Проверки Cookies (.youtube.com)."""
    cookies_ready = Signal(str)

    def __init__(self, selected_browser_idx: int, test_url: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔑 Универсальный Мастер Авторизации и Захвата Cookies (18+)")
        self.resize(780, 540)
        self.setStyleSheet(CYBER_OBSIDIAN_QSS)
        self.selected_browser_idx = max(2, selected_browser_idx) if selected_browser_idx != 1 else 5
        self.test_url = test_url.strip() or "https://www.youtube.com/watch?v=jNQXAC9IVRw"

        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        lbl_t = QLabel("🔑 МАСТЕР ЗАХВАТА И ПРОВЕРКИ СЕССИИ YOUTUBE (.YOUTUBE.COM)")
        lbl_t.setObjectName("SectionTitle")
        lay.addWidget(lbl_t)

        card2 = HoloCard(accent_hex=COLOR_EMERALD)
        c2_lay = QVBoxLayout(card2)
        lbl_2 = QLabel(
            "⭐ ОСНОВНОЙ СПОСОБ (100% РАБОТАЕТ В OPERA GX / CHROME / EDGE / ЯНДЕКС)"
        )
        lbl_2.setStyleSheet(f"color: {COLOR_EMERALD}; font-weight: 800;")
        c2_lay.addWidget(lbl_2)

        lbl_info = QLabel(
            "⚠️ ВАЖНО: Нажимать кнопку «Copy» в расширении «Get cookies.txt LOCALLY» нужно ОБЯЗАТЕЛЬНО находясь\n"
            "на открытой вкладке сайта YOUTUBE.COM (а не на вкладке магазина расширений Google)!\n\n"
            "1. Откройте вкладку YouTube.com в браузере (кнопка ниже).\n"
            "2. Нажмите на иконку расширения «Get cookies.txt LOCALLY» на вкладке YouTube и нажмите «Copy».\n"
            "3. Нажмите зеленую кнопку «📋 Вставить куки YouTube из буфера» ниже!"
        )
        lbl_info.setObjectName("SubLabel")
        lbl_info.setWordWrap(True)
        c2_lay.addWidget(lbl_info)

        row_ext = QHBoxLayout()
        btn_open_yt = QPushButton("🎬 Шаг 1: Открыть вкладку YouTube.com")
        btn_open_yt.clicked.connect(lambda: webbrowser.open("https://www.youtube.com"))

        btn_open_ext = QPushButton("🧩 Расширение Get cookies.txt")
        btn_open_ext.clicked.connect(
            lambda: webbrowser.open("https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc")
        )

        btn_paste_clip = QPushButton("📋 Шаг 2: Вставить куки YouTube из буфера!")
        btn_paste_clip.setObjectName("EmeraldActionBtn")
        btn_paste_clip.setMinimumHeight(38)
        btn_paste_clip.clicked.connect(self._import_from_clipboard)

        row_ext.addWidget(btn_open_yt)
        row_ext.addWidget(btn_open_ext)
        row_ext.addWidget(btn_paste_clip, 1)
        c2_lay.addLayout(row_ext)

        self.txt_log = QPlainTextEdit()
        self.txt_log.setPlaceholderText(
            "Здесь отобразится детальный отчет проверки ваших токенов .youtube.com..."
        )
        c2_lay.addWidget(self.txt_log, 1)
        lay.addWidget(card2, 1)

        card1 = HoloCard(accent_hex=COLOR_CYAN)
        c1_lay = QVBoxLayout(card1)
        lbl_1 = QLabel("АЛЬТЕРНАТИВА: Прямое извлечение из базы браузера (Для Mozilla Firefox)")
        lbl_1.setStyleSheet(f"color: {COLOR_CYAN}; font-weight: 700;")
        c1_lay.addWidget(lbl_1)

        row_b = QHBoxLayout()
        row_b.addWidget(QLabel("Браузер:"))
        self.cmb_b = QComboBox()
        for idx in range(2, len(BROWSER_PROFILES)):
            self.cmb_b.addItem(BROWSER_PROFILES[idx][0], idx)
        for i in range(self.cmb_b.count()):
            if self.cmb_b.itemData(i) == self.selected_browser_idx:
                self.cmb_b.setCurrentIndex(i)
                break
        row_b.addWidget(self.cmb_b, 1)

        btn_try_direct = QPushButton("⚡ Попробовать прямое извлечение")
        btn_try_direct.clicked.connect(self._try_direct_browser_extraction)
        row_b.addWidget(btn_try_direct)
        c1_lay.addLayout(row_b)
        lay.addWidget(card1)

        bot = QHBoxLayout()
        self.lbl_status = QLabel("")
        bot.addWidget(self.lbl_status, 1)
        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.reject)
        bot.addWidget(btn_close)
        lay.addLayout(bot)

        self._check_existing_cache()

    def _check_existing_cache(self):
        cache_p = get_universal_cached_cookies_path()
        ok, total, yt_cnt, only_google = verify_cookie_file_authenticity(cache_p)
        if ok:
            self.lbl_status.setText(
                f"✔ АКТИВЕН: {total} куки (найдено {yt_cnt} ключей авторизации домена .youtube.com)"
            )
            self.lbl_status.setStyleSheet(f"color: {COLOR_EMERALD}; font-weight: 700;")
        elif only_google:
            self.lbl_status.setText(
                "⚠ В файле только куки от google.com (магазин расширений), а куки от .youtube.com отсутствуют!"
            )
            self.lbl_status.setStyleSheet(f"color: {COLOR_AMBER}; font-weight: 700;")
        else:
            if os.path.isfile(cache_p):
                try:
                    os.remove(cache_p)
                except Exception:
                    pass
            self.lbl_status.setText("⚠ Рабочий кэш куки для .youtube.com еще не загружен.")
            self.lbl_status.setStyleSheet(f"color: {COLOR_AMBER}; font-weight: 700;")

    def _import_from_clipboard(self):
        clip_text = QApplication.clipboard().text().strip()
        box_text = self.txt_log.toPlainText().strip()
        raw_text = clip_text if ("\t" in clip_text) else box_text

        if not raw_text or ("\t" not in raw_text):
            QMessageBox.warning(
                self,
                "Буфер обмена пуст",
                "В буфере обмена нет строк куки!\n\n"
                "1. Перейдите на вкладку YouTube.com в вашем браузере.\n"
                "2. Откройте расширение 'Get cookies.txt LOCALLY' и нажмите 'Copy'.\n"
                "3. Нажмите эту зеленую кнопку снова."
            )
            return

        cache_p = get_universal_cached_cookies_path()
        with open(cache_p, "w", encoding="utf-8") as f:
            if not raw_text.startswith("# Netscape HTTP Cookie File"):
                f.write("# Netscape HTTP Cookie File\n")
            f.write(raw_text + "\n")

        is_valid, total_c, yt_auth_c, only_google = verify_cookie_file_authenticity(cache_p)

        if only_google:
            QMessageBox.warning(
                self,
                "Скопирована не та вкладка (google.com вместо youtube.com)!",
                "⚠️ Вы нажали кнопку 'Copy' в расширении, находясь на вкладке Google или Магазина расширений!\n\n"
                "Переключитесь на вкладку с сайтом https://www.youtube.com, нажмите Copy там и повторите вставку."
            )
            self._check_existing_cache()
            return

        if not is_valid:
            QMessageBox.warning(
                self,
                "Нет авторизации YouTube",
                f"В скопированных куки (всего {total_c} шт.) найдено только {yt_auth_c} ключей авторизации для .youtube.com.\n"
                "Убедитесь, что вы вошли в свой аккаунт на вкладке YouTube.com перед нажатием 'Copy'!"
            )
            self._check_existing_cache()
            return

        self._check_existing_cache()
        self.cookies_ready.emit(cache_p)
        QMessageBox.information(
            self,
            "Куки .youtube.com успешно проверены!",
            f"🎉 Отлично! В буфере найдены настоящие куки домена .youtube.com!\n\n"
            f"• Файл сохранен: {cache_p}\n"
            f"• Всего куки: {total_c} шт.\n"
            f"• Ключей авторизации .youtube.com: {yt_auth_c} шт."
        )
        self.accept()

    def _try_direct_browser_extraction(self):
        b_idx = self.cmb_b.currentData()
        b_title, ytdlp_key, raw_dir, exe_name = BROWSER_PROFILES[b_idx]
        ytdlp = resolve_tool("yt-dlp")
        if not ytdlp:
            QMessageBox.warning(self, "Ошибка", "Утилита yt-dlp не найдена!")
            return

        profile_dir = os.path.expandvars(raw_dir) if raw_dir else ""
        if raw_dir and not os.path.isdir(profile_dir):
            self.txt_log.appendPlainText(f"[ОШИБКА] Профиль браузера {b_title} не найден по пути: {profile_dir}")
            return

        running_exe = find_running_browser_exe(exe_name)
        relaunch_after = False
        if running_exe and ytdlp_key != "firefox":
            ans = QMessageBox.question(
                self,
                f"Браузер {b_title} сейчас открыт",
                f"Для прямого чтения базы куки нужно на 1 секунду закрыть {b_title} (он сразу запустится обратно).\n"
                f"Продолжить?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if ans == QMessageBox.Yes:
                relaunch_after = True
                gracefully_close_browser(exe_name)

        cache_p = get_universal_cached_cookies_path()
        with open(cache_p, "w", encoding="utf-8") as f:
            f.write("# Netscape HTTP Cookie File\n\n")

        browser_arg = f"{ytdlp_key}:{profile_dir}" if profile_dir else ytdlp_key
        cmd = [
            ytdlp,
            "--encoding", "utf-8",
            "--cookies-from-browser", browser_arg,
            "--cookies", cache_p,
            "--simulate",
            "--no-warnings",
            self.test_url,
        ]
        self.txt_log.appendPlainText(f">>> Извлечение из {b_title}...\n$ {' '.join(cmd)}")
        QApplication.processEvents()

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdin=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
                timeout=25,
            )
            out_log = (proc.stdout + "\n" + proc.stderr).strip()
        except Exception as exc:
            out_log = str(exc)

        if relaunch_after and running_exe and os.path.isfile(running_exe):
            try:
                subprocess.Popen([running_exe], creationflags=CREATE_NO_WINDOW)
            except Exception:
                pass

        is_valid, total_c, yt_auth_c, _ = verify_cookie_file_authenticity(cache_p)
        if is_valid:
            self._check_existing_cache()
            self.cookies_ready.emit(cache_p)
            QMessageBox.information(
                self,
                "Куки успешно извлечены!",
                f"✔ Из браузера {b_title} извлечено {total_c} куки (включая {yt_auth_c} ключей .youtube.com)!"
            )
            self.accept()
        else:
            if os.path.isfile(cache_p):
                try:
                    os.remove(cache_p)
                except Exception:
                    pass
            self.txt_log.appendPlainText(
                f"\n[ОТЧЕТ] Извлечено ключей .youtube.com: {yt_auth_c} шт.\n{out_log[:300]}\n"
                f"👉 Используйте зеленую кнопку выше (копирование через расширение на вкладке YouTube.com)!"
            )
            self._check_existing_cache()


class UrlProbeWorker(QThread):
    """Асинхронный воркер опроса `yt-dlp -J` и скачивания обложки видео в ОЗУ."""
    probe_done = Signal(dict, bytes, str)

    def __init__(self, url: str, browser_idx: int = 0, cookie_txt_path: str = ""):
        super().__init__()
        self.url = url
        self.browser_idx = browser_idx
        self.cookie_txt_path = cookie_txt_path

    def run(self):
        ytdlp = resolve_tool("yt-dlp")
        if not ytdlp:
            self.probe_done.emit({}, b"", "Утилита yt-dlp не найдена. Откройте 'CLI Утилиты' для быстрой докачки.")
            return

        cmd = [ytdlp, "--encoding", "utf-8", "-J", "--no-playlist", "--no-warnings"]
        cmd += build_cookie_cli_args(self.browser_idx, self.cookie_txt_path)
        cmd.append(self.url)

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdin=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
                timeout=30,
            )
            if proc.returncode != 0:
                raw_err = (proc.stderr or proc.stdout).strip()
                low = raw_err.lower()
                if "sign in to confirm your age" in low:
                    raw_err = (
                        "Это видео 18+ (в файле куки нет токенов домена .youtube.com). "
                        "Откройте вкладку YouTube.com в браузере, нажмите Copy в расширении и вставьте через «🔑 Мастер захвата Cookies»!"
                    )
                self.probe_done.emit({}, b"", raw_err)
                return

            info = json.loads(proc.stdout)
            thumb_bytes = b""
            thumb_url = info.get("thumbnail", "")
            if thumb_url:
                try:
                    req = urllib.request.Request(thumb_url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=8) as resp:
                        thumb_bytes = resp.read()
                except Exception:
                    pass

            self.probe_done.emit(info, thumb_bytes, "")
        except Exception as exc:
            self.probe_done.emit({}, b"", str(exc))


class UltimateDownloaderModule(QWidget):
    """Модуль скоростной загрузки потокового медиа (yt-dlp + Aria2c + SponsorBlock) v5.9."""

    def __init__(self, engine: BatchProcessEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.probe_worker: UrlProbeWorker = None
        self.current_duration: float = 0.0
        self.download_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(10)

        top_card = HoloCard(accent_hex=COLOR_CYAN)
        top_lay = QHBoxLayout(top_card)

        self.lbl_thumb = QLabel("NO THUMBNAIL")
        self.lbl_thumb.setFixedSize(210, 118)
        self.lbl_thumb.setAlignment(Qt.AlignCenter)
        self.lbl_thumb.setStyleSheet("background-color: #07090F; border: 1px solid #1E2436; border-radius: 6px;")
        top_lay.addWidget(self.lbl_thumb)

        url_col = QVBoxLayout()
        url_row = QHBoxLayout()
        self.ed_url = QLineEdit()
        self.ed_url.setPlaceholderText("Вставьте ссылку на YouTube (включая 18+), Twitch, Vimeo, VK, TikTok...")
        self.btn_analyze = QPushButton("🔍 Анализировать потоки (-J)")
        self.btn_analyze.setObjectName("CyanActionBtn")
        self.btn_analyze.clicked.connect(self.analyze_current_url)
        url_row.addWidget(self.ed_url, 1)
        url_row.addWidget(self.btn_analyze)
        url_col.addLayout(url_row)

        self.lbl_title = QLabel("Ожидание ссылки для анализа...")
        self.lbl_title.setStyleSheet(f"color: {COLOR_CYAN}; font-weight: 700; font-size: 13px;")
        self.lbl_title.setWordWrap(True)
        url_col.addWidget(self.lbl_title)

        self.lbl_meta = QLabel("Канал: —  |  Длительность: —  |  Просмотров: —")
        self.lbl_meta.setObjectName("SubLabel")
        url_col.addWidget(self.lbl_meta)

        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("Папка загрузки:"))
        self.ed_save_dir = QLineEdit(self.download_dir)
        btn_dir = QPushButton("📂 Выбрать")
        btn_dir.clicked.connect(self._browse_save_dir)
        dir_row.addWidget(self.ed_save_dir, 1)
        dir_row.addWidget(btn_dir)
        url_col.addLayout(dir_row)

        top_lay.addLayout(url_col, 1)
        root.addWidget(top_card)

        mid_row = QHBoxLayout()

        fmt_card = HoloCard(accent_hex=COLOR_PURPLE)
        fmt_lay = QVBoxLayout(fmt_card)
        lbl_t = QLabel("📊 ДОСТУПНЫЕ ПОТОКИ И ФОРМАТЫ (ВЫБЕРИТЕ СТРОКУ ИЛИ ИСПОЛЬЗУЙТЕ АВТО-ПРЕСЕТ)")
        lbl_t.setObjectName("SectionTitle")
        fmt_lay.addWidget(lbl_t)

        self.tbl_formats = QTableWidget(0, 7)
        self.tbl_formats.setHorizontalHeaderLabels([
            "Format ID", "Контейнер", "Разрешение / Тип", "FPS", "Видеокодек", "Аудиокодек", "Размер"
        ])
        self.tbl_formats.setWordWrap(False)
        self.tbl_formats.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_formats.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl_formats.setAlternatingRowColors(True)
        fmt_lay.addWidget(self.tbl_formats, 1)
        mid_row.addWidget(fmt_card, 3)

        opt_card = HoloCard(accent_hex=COLOR_EMERALD)
        opt_lay = QVBoxLayout(opt_card)
        lbl_o = QLabel("⚡ ТУРБО, АВТОРИЗАЦИЯ 18+ И УМНЫЕ ОПЦИИ")
        lbl_o.setObjectName("SectionTitle")
        opt_lay.addWidget(lbl_o)

        grid = QGridLayout()
        grid.addWidget(QLabel("Быстрый пресет качества:"), 0, 0)
        self.cmb_preset = QComboBox()
        self.cmb_preset.addItems([
            "Авто: 1080p FullHD MP4 (Кодек H.264 — открывается везде без кодеков!)",
            "Авто: 720p HD MP4 (Кодек H.264 — легкий и совместимый)",
            "Авто: Максимальное качество до 4K/8K HDR (Кодек AV1/VP9)",
            "Авто: Только Лучшее Аудио (конвертация в MP3 320k)",
            "Использовать выделенный Format ID из таблицы (+ лучшее аудио)",
        ])
        grid.addWidget(self.cmb_preset, 0, 1, 1, 2)

        self.chk_aria2c = QCheckBox("🚀 Турбо-режим Aria2c (-x 16 -s 16 -k 1M)")
        self.chk_aria2c.setChecked(True)
        grid.addWidget(self.chk_aria2c, 1, 0, 1, 3)

        grid.addWidget(QLabel("Скачать только отрезок (таймкод):"), 2, 0)
        self.ed_section = QLineEdit()
        self.ed_section.setPlaceholderText("напр. 00:01:15-00:03:40")
        grid.addWidget(self.ed_section, 2, 1, 1, 2)

        grid.addWidget(QLabel("Авторизация / Cookies (18+):"), 3, 0)
        self.cmb_cookies = QComboBox()
        for title, _, _, _ in BROWSER_PROFILES:
            self.cmb_cookies.addItem(title)
        self.cmb_cookies.currentIndexChanged.connect(self._on_cookie_mode_changed)
        grid.addWidget(self.cmb_cookies, 3, 1)

        self.btn_cookie_wizard = QPushButton("🔑 Мастер захвата Cookies")
        self.btn_cookie_wizard.setObjectName("PurpleActionBtn")
        self.btn_cookie_wizard.clicked.connect(self._open_cookie_wizard)
        grid.addWidget(self.btn_cookie_wizard, 3, 2)

        grid.addWidget(QLabel("Файл cookies.txt:"), 4, 0)
        self.ed_cookies_txt = QLineEdit()
        self.ed_cookies_txt.setPlaceholderText("Путь к проверенному файлу cookies.txt...")
        self.btn_browse_cookies = QPushButton("📂 Файл")
        self.btn_browse_cookies.clicked.connect(self._browse_cookies_txt)
        grid.addWidget(self.ed_cookies_txt, 4, 1)
        grid.addWidget(self.btn_browse_cookies, 4, 2)

        self.chk_playlist = QCheckBox("📑 Скачать весь плейлист/канал с авто-нумерацией")
        grid.addWidget(self.chk_playlist, 5, 0, 1, 3)

        self.chk_subs = QCheckBox("💬 Скачать и вшить субтитры:")
        grid.addWidget(self.chk_subs, 6, 0)
        self.cmb_sub_langs = QComboBox()
        self.cmb_sub_langs.addItems([
            "Только русские (ru) — без ошибок 429",
            "Только английские (en)",
            "Русские и английские (ru,en)",
        ])
        grid.addWidget(self.cmb_sub_langs, 6, 1, 1, 2)

        opt_lay.addLayout(grid)

        lbl_sb = QLabel("🛡 ИНТЕГРАЦИЯ SPONSORBLOCK (ВЫРЕЗАТЬ НА ЛЕТУ):")
        lbl_sb.setStyleSheet(f"color: {COLOR_EMERALD}; font-weight: 700; margin-top: 6px;")
        opt_lay.addWidget(lbl_sb)

        sb_grid = QGridLayout()
        self.chk_sb_sponsor = QCheckBox("Спонсорские вставки (sponsor)")
        self.chk_sb_intro = QCheckBox("Интро / Заставки (intro)")
        self.chk_sb_outro = QCheckBox("Аутро / Титры (outro)")
        self.chk_sb_selfpromo = QCheckBox("Самореклама (selfpromo)")
        sb_grid.addWidget(self.chk_sb_sponsor, 0, 0)
        sb_grid.addWidget(self.chk_sb_intro, 0, 1)
        sb_grid.addWidget(self.chk_sb_outro, 1, 0)
        sb_grid.addWidget(self.chk_sb_selfpromo, 1, 1)
        opt_lay.addLayout(sb_grid)

        opt_lay.addStretch(1)

        btn_dl = QPushButton("⬇ ЗАПУСТИТЬ СКОРОСТНУЮ ЗАГРУЗКУ")
        btn_dl.setObjectName("EmeraldActionBtn")
        btn_dl.setMinimumHeight(44)
        btn_dl.clicked.connect(self._enqueue_download)
        opt_lay.addWidget(btn_dl)

        mid_row.addWidget(opt_card, 2)
        root.addLayout(mid_row, 1)

        cached_p = get_universal_cached_cookies_path()
        is_ok, _, _, _ = verify_cookie_file_authenticity(cached_p)
        if is_ok:
            self.ed_cookies_txt.setText(cached_p)
            self.cmb_cookies.setCurrentIndex(1)
        else:
            self._on_cookie_mode_changed()

    def _on_cookie_mode_changed(self):
        idx = self.cmb_cookies.currentIndex()
        is_file_mode = (idx == 1)
        self.ed_cookies_txt.setEnabled(is_file_mode)
        self.btn_browse_cookies.setEnabled(is_file_mode)

    def _open_cookie_wizard(self):
        dlg = CookieAssistantDialog(
            selected_browser_idx=self.cmb_cookies.currentIndex(),
            test_url=self.ed_url.text(),
            parent=self,
        )
        dlg.cookies_ready.connect(self._on_cookies_ready)
        dlg.exec()

    def _on_cookies_ready(self, verified_path: str):
        self.ed_cookies_txt.setText(verified_path)
        self.cmb_cookies.setCurrentIndex(1)

    def _browse_cookies_txt(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "Выберите файл cookies.txt (Netscape format)", "", "Cookies (*.txt);;All (*.*)"
        )
        if p:
            is_ok, total_c, yt_c, only_google = verify_cookie_file_authenticity(p)
            if only_google:
                QMessageBox.warning(
                    self, "В файле нет куки от .youtube.com",
                    "Этот файл был экспортирован со страницы google.com (или магазина расширений), в нем нет куки от .youtube.com!\n"
                    "Экспортируйте куки, находясь на открытой вкладке YouTube.com."
                )
                return
            if total_c == 0:
                QMessageBox.warning(self, "Пустой файл", "В выбранном файле нет строк куки!")
                return
            self.ed_cookies_txt.setText(p)
            self.cmb_cookies.setCurrentIndex(1)

    def _browse_save_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Выберите папку для загрузки", self.ed_save_dir.text())
        if d:
            self.ed_save_dir.setText(d)

    def set_url_and_analyze(self, url: str):
        self.ed_url.setText(url)
        self.analyze_current_url()

    def analyze_current_url(self):
        url = self.ed_url.text().strip()
        if not url:
            QMessageBox.warning(self, "Загрузчик", "Вставьте корректный URL-адрес!")
            return

        b_idx = self.cmb_cookies.currentIndex()
        cookie_txt = self.ed_cookies_txt.text().strip()
        if b_idx == 1 and not os.path.isfile(cookie_txt):
            QMessageBox.warning(
                self, "Файл cookies.txt",
                "Нажмите «🔑 Мастер захвата Cookies» или выберите существующий файл cookies.txt!"
            )
            return

        self.btn_analyze.setEnabled(False)
        self.lbl_title.setText("⏳ Выполняется глубокий опрос потоков через yt-dlp -J...")
        self.tbl_formats.setRowCount(0)

        if self.probe_worker and self.probe_worker.isRunning():
            return
        self.probe_worker = UrlProbeWorker(url, b_idx, cookie_txt)
        self.probe_worker.probe_done.connect(self._on_probe_finished)
        self.probe_worker.start()

    def _on_probe_finished(self, info: Dict[str, Any], thumb_bytes: bytes, err: str):
        self.btn_analyze.setEnabled(True)
        if err or not info:
            self.lbl_title.setText(f"❌ Ошибка анализа: {err}")
            return

        title = info.get("title", "Без названия")
        uploader = info.get("uploader", "Неизвестный автор")
        self.current_duration = float(info.get("duration", 0.0) or 0.0)
        views = info.get("view_count", 0) or 0

        self.lbl_title.setText(f"🎬 {title}")
        self.lbl_meta.setText(
            f"Канал: {uploader}  |  Длительность: {int(self.current_duration) // 60}м {int(self.current_duration) % 60}с  |  "
            f"Просмотров: {views:,}"
        )

        if thumb_bytes:
            pix = QPixmap()
            pix.loadFromData(thumb_bytes)
            self.lbl_thumb.setPixmap(pix.scaled(self.lbl_thumb.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

        formats = info.get("formats", [])
        self.tbl_formats.setRowCount(0)
        for f in reversed(formats):
            fid = str(f.get("format_id", ""))
            ext = str(f.get("ext", ""))
            res = f.get("resolution") or f.get("format_note") or "audio only"
            fps = str(f.get("fps") or "—")
            vcodec = str(f.get("vcodec") or "none")
            acodec = str(f.get("acodec") or "none")
            sz = f.get("filesize") or f.get("filesize_approx") or 0
            sz_str = f"{sz / (1024 * 1024):.1f} МБ" if sz else "Поток"

            row = self.tbl_formats.rowCount()
            self.tbl_formats.insertRow(row)
            for col, val in enumerate([fid, ext, res, fps, vcodec, acodec, sz_str]):
                self.tbl_formats.setItem(row, col, QTableWidgetItem(val))

    def _enqueue_download(self):
        url = self.ed_url.text().strip()
        if not url:
            QMessageBox.warning(self, "Загрузчик", "Введите URL для скачивания!")
            return

        ytdlp = resolve_tool("yt-dlp") or "yt-dlp"
        if OutputDirectoryManager.use_custom_dir and OutputDirectoryManager.custom_dir_path:
            save_dir = OutputDirectoryManager.custom_dir_path
        else:
            save_dir = self.ed_save_dir.text().strip() or self.download_dir
        os.makedirs(save_dir, exist_ok=True)

        cmd = [ytdlp, "--newline", "--ignore-errors", "--encoding", "utf-8"]

        ffmpeg_path = resolve_tool("ffmpeg")
        if ffmpeg_path:
            cmd += ["--ffmpeg-location", os.path.dirname(ffmpeg_path)]

        if self.chk_playlist.isChecked():
            cmd += ["--yes-playlist", "-o", os.path.join(save_dir, "%(playlist_index)03d - %(title)s.%(ext)s")]
        else:
            cmd += ["--no-playlist", "-o", os.path.join(save_dir, "%(title)s.%(ext)s")]

        preset_idx = self.cmb_preset.currentIndex()
        sel_rows = self.tbl_formats.selectionModel().selectedRows()
        if preset_idx == 4 and sel_rows:
            fid = self.tbl_formats.item(sel_rows[0].row(), 0).text()
            cmd += ["-f", f"{fid}+bestaudio[ext=m4a]/bestaudio/best", "--merge-output-format", "mp4"]
        elif preset_idx == 0:
            cmd += [
                "-f", "bestvideo[height<=1080][vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]",
                "--merge-output-format", "mp4",
            ]
        elif preset_idx == 1:
            cmd += [
                "-f", "bestvideo[height<=720][vcodec^=avc1]+bestaudio[ext=m4a]/best[height<=720]",
                "--merge-output-format", "mp4",
            ]
        elif preset_idx == 3:
            cmd += ["-f", "bestaudio/best", "-x", "--audio-format", "mp3", "--audio-quality", "0"]
        else:
            cmd += ["-f", "bestvideo+bestaudio/best", "--merge-output-format", "mp4"]

        aria2_path = resolve_tool("aria2c")
        if self.chk_aria2c.isChecked() and aria2_path:
            cmd += [
                "--external-downloader", aria2_path,
                "--external-downloader-args", "aria2c:-x 16 -s 16 -k 1M"
            ]

        sec = self.ed_section.text().strip()
        if sec:
            if not sec.startswith("*"):
                sec = f"*{sec}"
            cmd += ["--download-sections", sec]

        cmd += build_cookie_cli_args(
            self.cmb_cookies.currentIndex(),
            self.ed_cookies_txt.text().strip(),
        )

        if self.chk_subs.isChecked():
            sub_idx = self.cmb_sub_langs.currentIndex()
            sub_lang = "ru" if sub_idx == 0 else ("en" if sub_idx == 1 else "ru,en")
            cmd += ["--write-subs", "--write-auto-subs", "--sub-langs", sub_lang, "--embed-subs"]

        sb_cats = []
        if self.chk_sb_sponsor.isChecked():
            sb_cats.append("sponsor")
        if self.chk_sb_intro.isChecked():
            sb_cats.append("intro")
        if self.chk_sb_outro.isChecked():
            sb_cats.append("outro")
        if self.chk_sb_selfpromo.isChecked():
            sb_cats.append("selfpromo")
        if sb_cats:
            cmd += ["--sponsorblock-remove", ",".join(sb_cats)]

        cmd.append(url)

        spec = TaskSpec(
            task_id=str(uuid.uuid4())[:8],
            title=f"Загрузка -> {save_dir}",
            module_name="Загрузчик yt-dlp",
            commands=[cmd],
            working_dir=save_dir,
            output_path=save_dir,
            expected_duration_sec=self.current_duration,
        )
        self.engine.submit_task(spec)