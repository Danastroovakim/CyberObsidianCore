import os
import re
import uuid
import json
import subprocess

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox,
    QFileDialog, QTreeWidget, QTreeWidgetItem, QTabWidget, QListWidget, QMessageBox
)

from core_engine import (
    BatchProcessEngine, TaskSpec, OutputDirectoryManager,
    resolve_tool, detect_gpu_encoders, CREATE_NO_WINDOW
)
from ui_cyber_widgets import HoloCard, COLOR_CYAN, COLOR_EMERALD


class MediaStudioModule(QWidget):
    """Полный студийный комбайн обработки видео и аудио на базе FFmpeg и FFprobe."""

    def __init__(self, engine: BatchProcessEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.current_file: str = ""
        self.media_duration: float = 0.0
        self.gpu_encoders = detect_gpu_encoders()
        self._build_ui()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(12)

        left_card = HoloCard(accent_hex=COLOR_CYAN)
        left_card.setMinimumWidth(365)
        left_layout = QVBoxLayout(left_card)

        lbl_insp = QLabel("🔍 FFPROBE МЕДИА-ИНСПЕКТОР")
        lbl_insp.setObjectName("SectionTitle")
        left_layout.addWidget(lbl_insp)

        file_row = QHBoxLayout()
        self.ed_input = QLineEdit()
        self.ed_input.setPlaceholderText("Выберите или перетащите видео/аудио файл...")
        self.ed_input.editingFinished.connect(lambda: self.load_file(self.ed_input.text().strip()))
        btn_browse = QPushButton("📂 Обзор")
        btn_browse.clicked.connect(self._browse_input_file)
        file_row.addWidget(self.ed_input, 1)
        file_row.addWidget(btn_browse)
        left_layout.addLayout(file_row)

        self.lbl_summary = QLabel("Файл не загружен")
        self.lbl_summary.setObjectName("SubLabel")
        self.lbl_summary.setWordWrap(True)
        left_layout.addWidget(self.lbl_summary)

        self.tree_probe = QTreeWidget()
        self.tree_probe.setHeaderLabels(["Параметр / Поток", "Значение"])
        self.tree_probe.setColumnWidth(0, 175)
        left_layout.addWidget(self.tree_probe, 1)

        root.addWidget(left_card, 2)

        right_card = HoloCard(accent_hex="#9D4EDD")
        right_layout = QVBoxLayout(right_card)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_video_tab(), "🎬 Видео-Рендер и Обрезка")
        self.tabs.addTab(self._build_audio_tab(), "🎧 Аудио-Лаборатория")
        self.tabs.addTab(self._build_special_tab(), "✨ Спец-Операции (GIF / Склейка / Стаб)")
        right_layout.addWidget(self.tabs)

        root.addWidget(right_card, 3)

    def _build_video_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setColumnMinimumWidth(3, 145)

        grid.addWidget(QLabel("Начало обрезки (-ss):"), 0, 0)
        self.ed_trim_start = QLineEdit("00:00:00")
        self.ed_trim_start.textChanged.connect(self._update_bitrate_preview)
        grid.addWidget(self.ed_trim_start, 0, 1)

        grid.addWidget(QLabel("Конец обрезки (-to, пусто = до конца):"), 0, 2)
        self.ed_trim_end = QLineEdit("")
        self.ed_trim_end.setPlaceholderText("напр. 00:02:30")
        self.ed_trim_end.textChanged.connect(self._update_bitrate_preview)
        grid.addWidget(self.ed_trim_end, 0, 3)

        self.chk_stream_copy = QCheckBox("⚡ Мгновенная обрезка без перекодирования (-c copy, 1 сек на 1 ГБ)")
        self.chk_stream_copy.toggled.connect(self._on_stream_copy_toggled)
        grid.addWidget(self.chk_stream_copy, 1, 0, 1, 4)

        grid.addWidget(QLabel("Аппаратный движок (GPU/CPU):"), 2, 0)
        self.cmb_hw_family = QComboBox()
        preferred_gpu_idx = 0
        for fam, encs in self.gpu_encoders.items():
            if encs:
                self.cmb_hw_family.addItem(f"{fam} ({', '.join(encs)})", fam)
                if fam in ("NVIDIA NVENC", "AMD AMF", "Intel QSV") and preferred_gpu_idx == 0:
                    preferred_gpu_idx = self.cmb_hw_family.count() - 1

        self.cmb_hw_family.setCurrentIndex(preferred_gpu_idx)
        self.cmb_hw_family.currentIndexChanged.connect(self._update_encoder_list)
        grid.addWidget(self.cmb_hw_family, 2, 1)

        grid.addWidget(QLabel("Видеокодек:"), 2, 2)
        self.cmb_encoder = QComboBox()
        grid.addWidget(self.cmb_encoder, 2, 3)
        self._update_encoder_list()

        grid.addWidget(QLabel("Разрешение:"), 3, 0)
        self.cmb_resolution = QComboBox()
        self.cmb_resolution.addItems([
            "Исходное (Original)",
            "3840x2160 (4K UHD)",
            "2560x1440 (2K QHD)",
            "1920x1080 (1080p FullHD)",
            "1280x720 (720p HD)",
            "854x480 (480p SD)",
            "Кастомное (с сохр. пропорций по ширине)",
        ])
        self.cmb_resolution.currentIndexChanged.connect(self._on_resolution_changed)
        grid.addWidget(self.cmb_resolution, 3, 1)

        grid.addWidget(QLabel("Кастомная ширина (px):"), 3, 2)
        self.spn_custom_width = QSpinBox()
        self.spn_custom_width.setRange(128, 7680)
        self.spn_custom_width.setValue(1920)
        self.spn_custom_width.setEnabled(False)
        grid.addWidget(self.spn_custom_width, 3, 3)

        grid.addWidget(QLabel("Алгоритм скейлинга:"), 4, 0)
        self.cmb_scaler = QComboBox()
        self.cmb_scaler.addItems(["lanczos", "bicubic", "bilinear", "spline", "neighbor"])
        grid.addWidget(self.cmb_scaler, 4, 1)

        grid.addWidget(QLabel("Частота кадров (FPS):"), 4, 2)
        self.cmb_fps = QComboBox()
        self.cmb_fps.addItems(["Исходный", "24", "30", "60", "120"])
        grid.addWidget(self.cmb_fps, 4, 3)

        grid.addWidget(QLabel("Режим контроля битрейта:"), 5, 0)
        self.cmb_rate_mode = QComboBox()
        self.cmb_rate_mode.addItems([
            "🎯 Под целевой размер файла (МБ) — Точный авторасчет!",
            "✨ По постоянному качеству (CRF / CQ)",
        ])
        self.cmb_rate_mode.currentIndexChanged.connect(self._on_rate_mode_changed)
        grid.addWidget(self.cmb_rate_mode, 5, 1)

        grid.addWidget(QLabel("Качество CRF/CQ (меньше=лучше):"), 5, 2)
        self.spn_crf = QSpinBox()
        self.spn_crf.setRange(0, 51)
        self.spn_crf.setValue(23)
        grid.addWidget(self.spn_crf, 5, 3)

        grid.addWidget(QLabel("Целевой размер файла (МБ):"), 6, 0)
        self.spn_target_mb = QDoubleSpinBox()
        self.spn_target_mb.setRange(1.0, 50000.0)
        self.spn_target_mb.setValue(20.0)
        self.spn_target_mb.setSuffix(" МБ")
        self.spn_target_mb.valueChanged.connect(self._update_bitrate_preview)
        grid.addWidget(self.spn_target_mb, 6, 1)

        grid.addWidget(QLabel("Выходной контейнер:"), 6, 2)
        self.cmb_v_ext = QComboBox()
        self.cmb_v_ext.addItems(["mp4", "mkv", "mov", "webm", "avi"])
        grid.addWidget(self.cmb_v_ext, 6, 3)

        lay.addLayout(grid)

        self.lbl_rate_calc = QLabel("📊 Выберите видеофайл слева для автоматического расчета битрейта под целевой размер.")
        self.lbl_rate_calc.setStyleSheet(
            f"color: {COLOR_EMERALD}; background-color: #070C16; border: 1px solid #1C2E4A; "
            f"border-radius: 6px; padding: 8px 12px; font-weight: 700;"
        )
        lay.addWidget(self.lbl_rate_calc)

        lay.addStretch(1)

        btn_run_video = QPushButton("🚀 ЗАПУСТИТЬ ОБРАБОТКУ ВИДЕО В ОЧЕРЕДЬ")
        btn_run_video.setObjectName("CyanActionBtn")
        btn_run_video.setMinimumHeight(44)
        btn_run_video.clicked.connect(self._enqueue_video_task)
        lay.addWidget(btn_run_video)

        self._on_rate_mode_changed()
        return w

    def _build_audio_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        grid = QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(QLabel("Операция Аудио-Лаборатории:"), 0, 0)
        self.cmb_audio_op = QComboBox()
        self.cmb_audio_op.addItems([
            "Извлечь / Конвертировать аудиодорожку",
            "Заменить аудиодорожку в видео на внешний аудиофайл",
            "Смикшировать (наложить) внешний аудиофайл с родным звуком видео",
        ])
        grid.addWidget(self.cmb_audio_op, 0, 1, 1, 3)

        grid.addWidget(QLabel("Целевой аудиокодек / формат:"), 1, 0)
        self.cmb_a_format = QComboBox()
        self.cmb_a_format.addItems(["mp3 (libmp3lame)", "aac", "flac", "wav (pcm_s16le)", "opus (libopus)"])
        grid.addWidget(self.cmb_a_format, 1, 1)

        grid.addWidget(QLabel("Битрейт аудио:"), 1, 2)
        self.cmb_a_bitrate = QComboBox()
        self.cmb_a_bitrate.addItems(["320k", "256k", "192k", "128k", "96k", "64k"])
        grid.addWidget(self.cmb_a_bitrate, 1, 3)

        grid.addWidget(QLabel("Частота дискретизации (Гц):"), 2, 0)
        self.cmb_a_sr = QComboBox()
        self.cmb_a_sr.addItems(["48000", "44100", "32000", "22050", "16000"])
        grid.addWidget(self.cmb_a_sr, 2, 1)

        self.chk_loudnorm = QCheckBox("🔊 Нормализация громкости EBU R128 (loudnorm=I=-16:TP=-1.5:LRA=11)")
        self.chk_loudnorm.setChecked(True)
        grid.addWidget(self.chk_loudnorm, 3, 0, 1, 4)

        self.chk_silenceremove = QCheckBox("✂ Удаление тишины в начале и паузах (silenceremove=-50dB)")
        grid.addWidget(self.chk_silenceremove, 4, 0, 1, 4)

        grid.addWidget(QLabel("Внешний аудиофайл (для замены/микширования):"), 5, 0)
        self.ed_ext_audio = QLineEdit()
        self.ed_ext_audio.setPlaceholderText("Путь к внешнему .mp3 / .wav...")
        btn_ext_a = QPushButton("📂 Выбрать аудио")
        btn_ext_a.clicked.connect(self._browse_external_audio)
        grid.addWidget(self.ed_ext_audio, 5, 1, 1, 2)
        grid.addWidget(btn_ext_a, 5, 3)

        lay.addLayout(grid)
        lay.addStretch(1)

        btn_run_audio = QPushButton("🎧 ВЫПОЛНИТЬ АУДИО-ОПЕРАЦИЮ")
        btn_run_audio.setObjectName("PurpleActionBtn")
        btn_run_audio.setMinimumHeight(44)
        btn_run_audio.clicked.connect(self._enqueue_audio_task)
        lay.addWidget(btn_run_audio)
        return w

    def _build_special_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        grid = QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(QLabel("Выберите спец-операцию:"), 0, 0)
        self.cmb_spec_op = QComboBox()
        self.cmb_spec_op.addItems([
            "Создать кристально чистый GIF (2-проходный palettegen + paletteuse)",
            "Повернуть / Отразить видео",
            "Стабилизировать тряску камеры (FFmpeg deshake)",
            "Извлечь серию кадров в PNG",
            "Склеить несколько видеофайлов без потери качества (Concat Demuxer)",
        ])
        grid.addWidget(self.cmb_spec_op, 0, 1, 1, 3)

        grid.addWidget(QLabel("Поворот / Отражение:"), 1, 0)
        self.cmb_rotate = QComboBox()
        self.cmb_rotate.addItems([
            "90° по часовой стрелке (transpose=1)",
            "90° против часовой стрелки (transpose=2)",
            "180° переворот (hflip,vflip)",
            "Горизонтальное зеркало (hflip)",
            "Вертикальное зеркало (vflip)",
        ])
        grid.addWidget(self.cmb_rotate, 1, 1)

        grid.addWidget(QLabel("GIF ширина / FPS:"), 1, 2)
        self.cmb_gif_preset = QComboBox()
        self.cmb_gif_preset.addItems(["640px @ 15 FPS", "480px @ 12 FPS", "800px @ 20 FPS"])
        grid.addWidget(self.cmb_gif_preset, 1, 3)

        lay.addLayout(grid)

        lay.addWidget(QLabel("Список файлов для склейки (Concat Demuxer):"))
        concat_row = QHBoxLayout()
        self.lst_concat = QListWidget()
        concat_btns = QVBoxLayout()
        btn_add_c = QPushButton("➕ Добавить видео")
        btn_add_c.clicked.connect(self._add_concat_files)
        btn_clr_c = QPushButton("🗑 Очистить")
        btn_clr_c.clicked.connect(self.lst_concat.clear)
        concat_btns.addWidget(btn_add_c)
        concat_btns.addWidget(btn_clr_c)
        concat_btns.addStretch(1)
        concat_row.addWidget(self.lst_concat, 1)
        concat_row.addLayout(concat_btns)
        lay.addLayout(concat_row, 1)

        btn_run_spec = QPushButton("✨ ЗАПУСТИТЬ СПЕЦ-ОПЕРАЦИЮ")
        btn_run_spec.setObjectName("EmeraldActionBtn")
        btn_run_spec.setMinimumHeight(44)
        btn_run_spec.clicked.connect(self._enqueue_special_task)
        lay.addWidget(btn_run_spec)
        return w

    def _on_resolution_changed(self):
        if not self.chk_stream_copy.isChecked():
            self.spn_custom_width.setEnabled(self.cmb_resolution.currentIndex() == 6)

    def _on_rate_mode_changed(self):
        if self.chk_stream_copy.isChecked():
            return
        is_target_size = (self.cmb_rate_mode.currentIndex() == 0)
        self.spn_target_mb.setEnabled(is_target_size)
        self.spn_crf.setEnabled(not is_target_size)
        self._update_bitrate_preview()

    def _on_stream_copy_toggled(self, checked: bool):
        for w in (
            self.cmb_hw_family, self.cmb_encoder, self.cmb_resolution,
            self.spn_custom_width, self.cmb_scaler, self.cmb_fps,
            self.cmb_rate_mode, self.spn_crf, self.spn_target_mb
        ):
            w.setEnabled(not checked)
        if not checked:
            self._on_resolution_changed()
            self._on_rate_mode_changed()

    @staticmethod
    def _parse_hms_to_sec(val: str) -> float:
        val = val.strip()
        if not val:
            return 0.0
        parts = val.split(":")
        try:
            if len(parts) == 3:
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
            elif len(parts) == 2:
                return float(parts[0]) * 60 + float(parts[1])
            return float(parts[0])
        except Exception:
            return 0.0

    def _get_effective_duration(self) -> float:
        dur = self.media_duration
        ss_sec = self._parse_hms_to_sec(self.ed_trim_start.text())
        to_sec = self._parse_hms_to_sec(self.ed_trim_end.text())
        if to_sec > 0:
            if to_sec <= ss_sec:
                return 0.0
            return to_sec - ss_sec
        if ss_sec > 0 and dur > ss_sec:
            return dur - ss_sec
        return dur

    def _calculate_target_bitrates(self) -> tuple[int, int]:
        eff_dur = max(1.0, self._get_effective_duration())
        target_mb = self.spn_target_mb.value()
        usable_kilobits = target_mb * 8192.0 * 0.96
        total_kbps = usable_kilobits / eff_dur

        audio_kbps = 128 if total_kbps > 350 else 64
        video_kbps = max(100, int(total_kbps - audio_kbps))
        return video_kbps, audio_kbps

    def _update_bitrate_preview(self):
        if self.cmb_rate_mode.currentIndex() == 1:
            self.lbl_rate_calc.setText(
                f"✨ Режим постоянного качества (CRF/CQ = {self.spn_crf.value()}). Итоговый размер зависит от сложности сцен."
            )
            return

        eff_dur = self._get_effective_duration()
        if eff_dur <= 0:
            self.lbl_rate_calc.setText(
                f"🎯 Режим целевого размера ({self.spn_target_mb.value():.1f} МБ). Выберите видеофайл или проверьте таймкоды обрезки."
            )
            return

        v_kbps, a_kbps = self._calculate_target_bitrates()
        self.lbl_rate_calc.setText(
            f"🎯 АВТОРАСЧЕТ ПОД {self.spn_target_mb.value():.1f} МБ (длительность {eff_dur:.1f} сек):  "
            f"Видео = {v_kbps} kbps  |  Аудио = {a_kbps} kbps"
        )

    def _update_encoder_list(self):
        fam = self.cmb_hw_family.currentData()
        self.cmb_encoder.clear()
        if fam and fam in self.gpu_encoders:
            self.cmb_encoder.addItems(self.gpu_encoders[fam])

    def _browse_input_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите медиафайл", "", "Media Files (*.*)")
        if path:
            self.load_file(path)

    def _browse_external_audio(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите аудиофайл", "", "Audio Files (*.mp3 *.wav *.flac *.aac *.ogg *.m4a);;All (*.*)"
        )
        if path:
            self.ed_ext_audio.setText(path)

    def _add_concat_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Выберите видеофайлы для склейки", "", "Video Files (*.mp4 *.mkv *.mov *.avi *.webm);;All (*.*)"
        )
        for p in paths:
            self.lst_concat.addItem(p)

    def _probe_duration_via_ffmpeg(self, path: str) -> float:
        ffmpeg_bin = resolve_tool("ffmpeg")
        if not ffmpeg_bin or not os.path.isfile(path):
            return 0.0
        try:
            proc = subprocess.run(
                [ffmpeg_bin, "-hide_banner", "-i", path],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdin=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
                timeout=6,
            )
            m = re.search(r"Duration:\s*(\d{2}):(\d{2}):(\d{2})\.(\d{2})", proc.stderr + proc.stdout)
            if m:
                h, m_, s, cs = m.groups()
                return int(h) * 3600 + int(m_) * 60 + int(s) + int(cs) / 100.0
        except Exception:
            pass
        return 0.0

    def load_file(self, path: str):
        if not path or not os.path.isfile(path):
            return
        self.current_file = path
        self.ed_input.setText(path)
        self.tree_probe.clear()
        self.media_duration = 0.0

        ffprobe_bin = resolve_tool("ffprobe")
        if ffprobe_bin:
            try:
                proc = subprocess.run(
                    [
                        ffprobe_bin, "-v", "quiet",
                        "-print_format", "json",
                        "-show_format", "-show_streams", path
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    stdin=subprocess.DEVNULL,
                    creationflags=CREATE_NO_WINDOW,
                    timeout=8,
                )
                data = json.loads(proc.stdout or "{}")
                fmt = data.get("format", {})
                self.media_duration = float(fmt.get("duration", 0.0) or 0.0)
                size_mb = int(fmt.get("size", 0) or 0) / (1024 * 1024)
                bit_rate_kbps = int(fmt.get("bit_rate", 0) or 0) // 1000

                self.lbl_summary.setText(
                    f"📄 {os.path.basename(path)}  |  ⏱ {self.media_duration:.2f} сек  |  "
                    f"💾 {size_mb:.2f} МБ  |  ⚡ {bit_rate_kbps} kbps"
                )

                fmt_root = QTreeWidgetItem(self.tree_probe, ["Контейнер (Format)", fmt.get("format_long_name", "N/A")])
                QTreeWidgetItem(fmt_root, ["Длительность", f"{self.media_duration:.2f} сек"])
                QTreeWidgetItem(fmt_root, ["Размер", f"{size_mb:.2f} МБ"])
                QTreeWidgetItem(fmt_root, ["Общий битрейт", f"{bit_rate_kbps} kbps"])

                for s in data.get("streams", []):
                    stype = s.get("codec_type", "unknown").upper()
                    idx = s.get("index", 0)
                    codec = s.get("codec_name", "N/A")
                    s_item = QTreeWidgetItem(self.tree_probe, [f"Поток #{idx} [{stype}]", codec])
                    if stype == "VIDEO":
                        w, h = s.get("width", "?"), s.get("height", "?")
                        pix = s.get("pix_fmt", "N/A")
                        cs = s.get("color_space", "bt709")
                        fps_raw = s.get("r_frame_rate", "0/1")
                        QTreeWidgetItem(s_item, ["Разрешение", f"{w}x{h}"])
                        QTreeWidgetItem(s_item, ["Цветовое пространство", f"{pix} ({cs})"])
                        QTreeWidgetItem(s_item, ["Частота кадров", fps_raw])
                    elif stype == "AUDIO":
                        sr = s.get("sample_rate", "?")
                        ch = s.get("channels", "?")
                        lang = s.get("tags", {}).get("language", "und")
                        QTreeWidgetItem(s_item, ["Дискретизация / Каналы", f"{sr} Гц / {ch} кан."])
                        QTreeWidgetItem(s_item, ["Язык дорожки", lang])
                    elif stype == "SUBTITLE":
                        lang = s.get("tags", {}).get("language", "und")
                        QTreeWidgetItem(s_item, ["Язык субтитров", lang])

                self.tree_probe.expandAll()
            except Exception as exc:
                self.lbl_summary.setText(f"Ошибка чтения метаданных FFprobe: {exc}")

        if self.media_duration <= 0:
            self.media_duration = self._probe_duration_via_ffmpeg(path)
            size_mb = os.path.getsize(path) / (1024 * 1024)
            self.lbl_summary.setText(
                f"📄 {os.path.basename(path)}  |  ⏱ {self.media_duration:.2f} сек  |  💾 {size_mb:.2f} МБ"
            )

        self._update_bitrate_preview()

    def _enqueue_video_task(self):
        in_path = self.ed_input.text().strip()
        if not in_path or not os.path.isfile(in_path):
            QMessageBox.warning(self, "Студия", "Сначала выберите исходный видеофайл!")
            return

        if self.media_duration <= 0:
            self.load_file(in_path)

        ss = self.ed_trim_start.text().strip()
        to = self.ed_trim_end.text().strip()
        if to and self._parse_hms_to_sec(to) <= self._parse_hms_to_sec(ss):
            QMessageBox.warning(self, "Ошибка обрезки", "Время конца (-to) должно быть больше времени начала (-ss)!")
            return

        ffmpeg_bin = resolve_tool("ffmpeg") or "ffmpeg"
        ext = self.cmb_v_ext.currentText()
        out_path = OutputDirectoryManager.resolve_output_path(in_path, f"_obsidian.{ext}")

        cmd = [ffmpeg_bin, "-y"]
        if ss and ss != "00:00:00":
            cmd += ["-ss", ss]
        if to:
            cmd += ["-to", to]
        cmd += ["-i", in_path]

        if self.chk_stream_copy.isChecked():
            cmd += ["-c", "copy", out_path]
        else:
            encoder = self.cmb_encoder.currentText() or "libx264"
            audio_codec = "aac"
            if ext == "webm":
                if not any(k in encoder for k in ("vp9", "vp8", "av1")):
                    encoder = "libvpx-vp9"
                audio_codec = "libopus"

            cmd += ["-c:v", encoder]

            vf_parts = []
            res_choice = self.cmb_resolution.currentIndex()
            scaler = self.cmb_scaler.currentText()
            res_map = {1: "3840:2160", 2: "2560:1440", 3: "1920:1080", 4: "1280:720", 5: "854:480"}
            if res_choice in res_map:
                vf_parts.append(f"scale={res_map[res_choice]}:flags={scaler}")
            elif res_choice == 6:
                cw = self.spn_custom_width.value()
                vf_parts.append(f"scale={cw}:-2:flags={scaler}")

            fps_txt = self.cmb_fps.currentText()
            if fps_txt != "Исходный":
                vf_parts.append(f"fps={fps_txt}")

            if vf_parts:
                cmd += ["-vf", ",".join(vf_parts)]

            if self.cmb_rate_mode.currentIndex() == 0:
                if self._get_effective_duration() <= 0:
                    QMessageBox.warning(
                        self, "Ошибка длительности",
                        "Не удалось определить длительность видео для расчета размера. Проверьте наличие FFmpeg."
                    )
                    return
                video_kbps, audio_kbps = self._calculate_target_bitrates()
                max_kbps = int(video_kbps * 1.05)
                buf_kbps = int(video_kbps * 2.0)

                if "nvenc" in encoder:
                    cmd += [
                        "-rc", "vbr",
                        "-b:v", f"{video_kbps}k",
                        "-maxrate", f"{max_kbps}k",
                        "-bufsize", f"{buf_kbps}k",
                        "-preset", "p5",
                    ]
                else:
                    cmd += [
                        "-b:v", f"{video_kbps}k",
                        "-maxrate", f"{max_kbps}k",
                        "-bufsize", f"{buf_kbps}k",
                    ]
                cmd += ["-c:a", audio_codec, "-b:a", f"{audio_kbps}k", out_path]
            else:
                q_val = str(self.spn_crf.value())
                if "nvenc" in encoder:
                    cmd += ["-rc", "vbr", "-cq", q_val, "-b:v", "0", "-preset", "p5"]
                elif "amf" in encoder or "qsv" in encoder:
                    cmd += ["-global_quality", q_val]
                elif "vpx" in encoder:
                    cmd += ["-crf", q_val, "-b:v", "0", "-deadline", "good", "-cpu-used", "2"]
                elif "svtav1" in encoder:
                    cmd += ["-crf", q_val, "-preset", "6"]
                else:
                    cmd += ["-crf", q_val, "-preset", "medium"]
                cmd += ["-c:a", audio_codec, "-b:a", "192k" if audio_codec == "aac" else "160k", out_path]

        spec = TaskSpec(
            task_id=str(uuid.uuid4())[:8],
            title=f"Видео-рендер -> {os.path.basename(out_path)}",
            module_name="Видео Студия",
            commands=[cmd],
            output_path=out_path,
            expected_duration_sec=self._get_effective_duration(),
        )
        self.engine.submit_task(spec)

    def _enqueue_audio_task(self):
        in_path = self.ed_input.text().strip()
        if not in_path or not os.path.isfile(in_path):
            QMessageBox.warning(self, "Аудио-Лаборатория", "Сначала выберите исходный файл!")
            return

        ffmpeg_bin = resolve_tool("ffmpeg") or "ffmpeg"
        op_idx = self.cmb_audio_op.currentIndex()

        af_chain = []
        if self.chk_silenceremove.isChecked():
            af_chain.append("silenceremove=start_periods=1:start_silence=0.5:start_threshold=-50dB")
        if self.chk_loudnorm.isChecked():
            af_chain.append("loudnorm=I=-16:TP=-1.5:LRA=11")

        if op_idx == 0:
            fmt_raw = self.cmb_a_format.currentText().split()[0]
            codec_map = {
                "mp3": "libmp3lame",
                "aac": "aac",
                "flac": "flac",
                "wav": "pcm_s16le",
                "opus": "libopus",
            }
            out_path = OutputDirectoryManager.resolve_output_path(in_path, f"_audio.{fmt_raw}")
            cmd = [ffmpeg_bin, "-y", "-i", in_path, "-vn"]
            if af_chain:
                cmd += ["-af", ",".join(af_chain)]
            cmd += [
                "-c:a", codec_map[fmt_raw],
                "-b:a", self.cmb_a_bitrate.currentText(),
                "-ar", self.cmb_a_sr.currentText(),
                out_path,
            ]
        elif op_idx == 1:
            ext_a = self.ed_ext_audio.text().strip()
            if not os.path.isfile(ext_a):
                QMessageBox.warning(self, "Аудио-Лаборатория", "Укажите существующий внешний аудиофайл!")
                return
            out_path = OutputDirectoryManager.resolve_output_path(in_path, "_replaced_audio.mp4")
            cmd = [
                ffmpeg_bin, "-y", "-i", in_path, "-i", ext_a,
                "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-shortest", out_path
            ]
        else:
            ext_a = self.ed_ext_audio.text().strip()
            if not os.path.isfile(ext_a):
                QMessageBox.warning(self, "Аудио-Лаборатория", "Укажите существующий внешний аудиофайл!")
                return
            out_path = OutputDirectoryManager.resolve_output_path(in_path, "_mixed_audio.mp4")
            cmd = [
                ffmpeg_bin, "-y", "-i", in_path, "-i", ext_a,
                "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=2[aout]",
                "-map", "0:v:0", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", out_path
            ]

        spec = TaskSpec(
            task_id=str(uuid.uuid4())[:8],
            title=f"Аудио-Лаб -> {os.path.basename(out_path)}",
            module_name="Аудио Студия",
            commands=[cmd],
            output_path=out_path,
            expected_duration_sec=self.media_duration,
        )
        self.engine.submit_task(spec)

    def _enqueue_special_task(self):
        ffmpeg_bin = resolve_tool("ffmpeg") or "ffmpeg"
        op_idx = self.cmb_spec_op.currentIndex()

        if op_idx == 4:
            if self.lst_concat.count() < 2:
                QMessageBox.warning(self, "Склейка видео", "Добавьте минимум 2 видеофайла в список!")
                return
            first_file = self.lst_concat.item(0).text()
            out_dir = OutputDirectoryManager.resolve_output_dir(first_file)
            os.makedirs(out_dir, exist_ok=True)
            list_txt = os.path.join(out_dir, "obsidian_concat_list.txt")
            with open(list_txt, "w", encoding="utf-8") as f:
                for i in range(self.lst_concat.count()):
                    escaped = self.lst_concat.item(i).text().replace("'", "'\\''")
                    f.write(f"file '{escaped}'\n")
            out_path = os.path.join(out_dir, "merged_obsidian.mp4")
            cmd = [ffmpeg_bin, "-y", "-f", "concat", "-safe", "0", "-i", list_txt, "-c", "copy", out_path]
            spec = TaskSpec(
                task_id=str(uuid.uuid4())[:8],
                title=f"Склейка ({self.lst_concat.count()} видео)",
                module_name="Спец-Операции",
                commands=[cmd],
                output_path=out_path,
            )
            self.engine.submit_task(spec)
            return

        in_path = self.ed_input.text().strip()
        if not in_path or not os.path.isfile(in_path):
            QMessageBox.warning(self, "Спец-операции", "Сначала выберите исходный видеофайл слева!")
            return

        if op_idx == 0:
            preset = self.cmb_gif_preset.currentText()
            w_px = preset.split("px")[0].strip()
            fps_v = preset.split("@")[1].replace("FPS", "").strip()
            out_path = OutputDirectoryManager.resolve_output_path(in_path, "_crystal.gif")
            filter_str = (
                f"fps={fps_v},scale={w_px}:-1:flags=lanczos,split[s0][s1];"
                f"[s0]palettegen=stats_mode=diff[p];[s1][p]paletteuse=dither=bayer:bayer_scale=5"
            )
            cmd = [ffmpeg_bin, "-y", "-i", in_path, "-vf", filter_str, out_path]
        elif op_idx == 1:
            rot_idx = self.cmb_rotate.currentIndex()
            rot_filters = ["transpose=1", "transpose=2", "hflip,vflip", "hflip", "vflip"]
            out_path = OutputDirectoryManager.resolve_output_path(in_path, "_rotated.mp4")
            cmd = [ffmpeg_bin, "-y", "-i", in_path, "-vf", rot_filters[rot_idx], "-c:a", "copy", out_path]
        elif op_idx == 2:
            out_path = OutputDirectoryManager.resolve_output_path(in_path, "_stabilized.mp4")
            cmd = [ffmpeg_bin, "-y", "-i", in_path, "-vf", "deshake=rx=32:ry=32", "-c:a", "copy", out_path]
        else:
            frames_dir = OutputDirectoryManager.resolve_output_path(in_path, "_frames")
            os.makedirs(frames_dir, exist_ok=True)
            out_path = os.path.join(frames_dir, "frame_%05d.png")
            cmd = [ffmpeg_bin, "-y", "-i", in_path, "-vf", "fps=1", out_path]

        spec = TaskSpec(
            task_id=str(uuid.uuid4())[:8],
            title=f"Спец-операция -> {os.path.basename(out_path)}",
            module_name="Спец-Операции",
            commands=[cmd],
            output_path=out_path,
            expected_duration_sec=self.media_duration,
        )
        self.engine.submit_task(spec)