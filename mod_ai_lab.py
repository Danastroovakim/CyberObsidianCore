# -*- coding: utf-8 -*-
"""
mod_ai_lab.py — Модуль 4: Локальные ИИ-инструменты (Tesseract OCR + Whisper CLI + Real-ESRGAN Vulkan) v5.3.
"""

import os
import uuid
import shutil
import tempfile
import subprocess
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QCheckBox, QTabWidget,
    QPlainTextEdit, QFileDialog, QMessageBox, QApplication
)

from core_engine import (
    BatchProcessEngine, TaskSpec, OutputDirectoryManager,
    resolve_tool, get_bin_dir, heal_realesrgan_models, CREATE_NO_WINDOW
)
from ui_cyber_widgets import HoloCard, COLOR_PURPLE

VIDEO_EXTS = (".mp4", ".mkv", ".mov", ".avi", ".webm", ".wmv", ".m4v", ".flv")
ESRGAN_DIRECT_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
CONVERTIBLE_IMAGE_EXTS = (".bmp", ".tif", ".tiff")


class LocalAILabModule(QWidget):
    """Локальная нейросетевая лаборатория: OCR, Whisper Subtitles и Real-ESRGAN Vulkan Upscale."""

    def __init__(self, engine: BatchProcessEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)

        card = HoloCard(accent_hex=COLOR_PURPLE)
        lay = QVBoxLayout(card)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_ocr_tab(), "👁 Tesseract OCR (Текст с картинок и сканов)")
        self.tabs.addTab(self._build_whisper_tab(), "🎙 AI Субтитры и Транскрибация (Whisper CLI)")
        self.tabs.addTab(self._build_esrgan_tab(), "🔮 AI Upscale 4x на GPU (Real-ESRGAN Vulkan)")

        lay.addWidget(self.tabs)
        root.addWidget(card)

    def _build_ocr_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        top = QHBoxLayout()
        self.ed_ocr_img = QLineEdit()
        self.ed_ocr_img.setPlaceholderText("Выберите изображение, скан или PDF (PNG, JPG, WEBP, TIFF, BMP, PDF)...")
        btn_b = QPushButton("📂 Выбрать файл")
        btn_b.clicked.connect(self._browse_ocr_image)

        self.cmb_ocr_lang = QComboBox()
        self.cmb_ocr_lang.addItems(["rus+eng", "eng", "rus"])

        btn_run = QPushButton("👁 РАСПОЗНАТЬ ТЕКСТ СЕЙЧАС")
        btn_run.setObjectName("CyanActionBtn")
        btn_run.clicked.connect(self._run_ocr_instant)

        top.addWidget(self.ed_ocr_img, 1)
        top.addWidget(btn_b)
        top.addWidget(QLabel("Язык:"))
        top.addWidget(self.cmb_ocr_lang)
        top.addWidget(btn_run)
        lay.addLayout(top)

        self.txt_ocr_result = QPlainTextEdit()
        self.txt_ocr_result.setPlaceholderText("Здесь появится распознанный текст...")
        lay.addWidget(self.txt_ocr_result, 1)

        bot = QHBoxLayout()
        btn_copy = QPushButton("📋 Скопировать в буфер обмена")
        btn_copy.clicked.connect(lambda: QApplication.clipboard().setText(self.txt_ocr_result.toPlainText()))
        btn_save_txt = QPushButton("💾 Сохранить как .TXT")
        btn_save_txt.clicked.connect(self._save_ocr_txt)
        btn_save_docx = QPushButton("📘 Экспортировать в .DOCX (Работает из коробки)")
        btn_save_docx.setObjectName("PurpleActionBtn")
        btn_save_docx.clicked.connect(self._save_ocr_docx)

        bot.addWidget(btn_copy)
        bot.addWidget(btn_save_txt)
        bot.addWidget(btn_save_docx)
        lay.addLayout(bot)
        return w

    def _build_whisper_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        grid = QGridLayout()

        grid.addWidget(QLabel("Исходный видео или аудиофайл:"), 0, 0)
        self.ed_wh_input = QLineEdit()
        btn_b = QPushButton("📂 Выбрать медиа")
        btn_b.clicked.connect(self._browse_whisper_input)
        grid.addWidget(self.ed_wh_input, 0, 1)
        grid.addWidget(btn_b, 0, 2)

        grid.addWidget(QLabel("Файл весов модели (.bin для whisper.cpp):"), 1, 0)
        self.ed_wh_model = QLineEdit(os.path.join(get_bin_dir(), "ggml-base.bin"))
        btn_m = QPushButton("📂 Выбрать модель")
        btn_m.clicked.connect(self._browse_whisper_model)
        grid.addWidget(self.ed_wh_model, 1, 1)
        grid.addWidget(btn_m, 1, 2)

        grid.addWidget(QLabel("Язык речи:"), 2, 0)
        self.cmb_wh_lang = QComboBox()
        self.cmb_wh_lang.addItems(["ru", "en", "auto"])
        grid.addWidget(self.cmb_wh_lang, 2, 1, 1, 2)

        self.chk_wh_burn = QCheckBox("🔥 Сразу вшить полученные субтитры .SRT в видеоролик через FFmpeg!")
        self.chk_wh_burn.setChecked(True)
        grid.addWidget(self.chk_wh_burn, 3, 0, 1, 3)

        lay.addLayout(grid)
        lay.addStretch(1)

        btn_wh = QPushButton("🎙 ЗАПУСТИТЬ ИИ-ТРАНСКРИБАЦИЮ WHISPER В ОЧЕРЕДЬ")
        btn_wh.setObjectName("PurpleActionBtn")
        btn_wh.setMinimumHeight(44)
        btn_wh.clicked.connect(self._enqueue_whisper_pipeline)
        lay.addWidget(btn_wh)
        return w

    def _build_esrgan_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        grid = QGridLayout()

        grid.addWidget(QLabel("Изображение или видео для AI-апскейла:"), 0, 0)
        self.ed_esr_input = QLineEdit()
        btn_b = QPushButton("📂 Выбрать файл")
        btn_b.clicked.connect(self._browse_esrgan_input)
        grid.addWidget(self.ed_esr_input, 0, 1)
        grid.addWidget(btn_b, 0, 2)

        grid.addWidget(QLabel("Нейросетевая модель Real-ESRGAN:"), 1, 0)
        self.cmb_esr_model = QComboBox()
        self.cmb_esr_model.addItems([
            "realesrgan-x4plus",
            "realesrgan-x4plus-anime",
            "realesr-animevideov3",
        ])
        self.cmb_esr_model.currentTextChanged.connect(self._on_esrgan_model_changed)
        grid.addWidget(self.cmb_esr_model, 1, 1, 1, 2)

        grid.addWidget(QLabel("Кратность увеличения:"), 2, 0)
        self.cmb_esr_scale = QComboBox()
        self.cmb_esr_scale.addItems(["4"])
        grid.addWidget(self.cmb_esr_scale, 2, 1, 1, 2)

        self.lbl_esr_hint = QLabel(
            "ℹ Модели x4plus / x4plus-anime работают только в 4x; модель realesr-animevideov3 поддерживает 2x, 3x и 4x."
        )
        self.lbl_esr_hint.setObjectName("SubLabel")
        self.lbl_esr_hint.setWordWrap(True)
        grid.addWidget(self.lbl_esr_hint, 3, 0, 1, 3)

        lay.addLayout(grid)
        lay.addStretch(1)

        btn_esr = QPushButton("🔮 ЗАПУСТИТЬ ИИ-АПСКЕЙЛ НА ВИДЕОКАРТЕ (VULKAN)")
        btn_esr.setObjectName("EmeraldActionBtn")
        btn_esr.setMinimumHeight(44)
        btn_esr.clicked.connect(self._enqueue_esrgan_task)
        lay.addWidget(btn_esr)
        return w

    def _on_esrgan_model_changed(self, model_name: str):
        cur = self.cmb_esr_scale.currentText()
        self.cmb_esr_scale.clear()
        if model_name == "realesr-animevideov3":
            self.cmb_esr_scale.addItems(["4", "3", "2"])
            if cur in ("4", "3", "2"):
                self.cmb_esr_scale.setCurrentText(cur)
        else:
            self.cmb_esr_scale.addItems(["4"])

    def _browse_ocr_image(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "Выберите изображение или PDF", "", "Files (*.png *.jpg *.jpeg *.webp *.bmp *.tiff *.pdf)"
        )
        if p:
            self.ed_ocr_img.setText(p)

    def _run_tesseract_on_image(self, tess: str, img_path: str, lang: str) -> str:
        proc = subprocess.run(
            [tess, img_path, "stdout", "-l", lang],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
            timeout=30,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
        proc2 = subprocess.run(
            [tess, img_path, "stdout"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
            timeout=30,
        )
        return proc2.stdout.strip() or proc.stderr.strip()

    def _run_ocr_instant(self):
        img = self.ed_ocr_img.text().strip()
        if not os.path.isfile(img):
            QMessageBox.warning(self, "OCR", "Выберите существующий файл!")
            return

        is_pdf = img.lower().endswith(".pdf")
        if is_pdf:
            try:
                import fitz
                doc = fitz.open(img)
                txt = "\n\n".join([page.get_text("text") for page in doc])
                doc.close()
                if txt.strip():
                    self.txt_ocr_result.setPlainText(txt.strip())
                    return
            except Exception:
                pass

        tess = resolve_tool("tesseract")
        if not tess:
            QMessageBox.warning(
                self, "Tesseract OCR",
                "Для распознавания текста со сканов/картинок отметьте 'Tesseract OCR' в меню 'CLI утилиты и портативность'."
            )
            return

        lang = self.cmb_ocr_lang.currentText()
        try:
            if is_pdf:
                import fitz
                doc = fitz.open(img)
                page_texts = []
                with tempfile.TemporaryDirectory() as tmpdir:
                    for idx, page in enumerate(doc):
                        pix = page.get_pixmap(dpi=220)
                        tmp_png = os.path.join(tmpdir, f"page_{idx}.png")
                        pix.save(tmp_png)
                        page_texts.append(self._run_tesseract_on_image(tess, tmp_png, lang))
                doc.close()
                self.txt_ocr_result.setPlainText("\n\n".join(filter(None, page_texts)))
            else:
                self.txt_ocr_result.setPlainText(self._run_tesseract_on_image(tess, img, lang))
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка OCR", str(exc))

    def _save_ocr_txt(self):
        default_dir = OutputDirectoryManager.resolve_output_dir()
        p, _ = QFileDialog.getSaveFileName(
            self, "Сохранить текст", os.path.join(default_dir, "ocr_result.txt"), "Text (*.txt)"
        )
        if p:
            with open(p, "w", encoding="utf-8") as f:
                f.write(self.txt_ocr_result.toPlainText())

    def _save_ocr_docx(self):
        default_dir = OutputDirectoryManager.resolve_output_dir()
        p, _ = QFileDialog.getSaveFileName(
            self, "Сохранить DOCX", os.path.join(default_dir, "ocr_result.docx"), "Word (*.docx)"
        )
        if not p:
            return
        try:
            import docx
            d = docx.Document()
            for line in self.txt_ocr_result.toPlainText().splitlines():
                d.add_paragraph(line)
            d.save(p)
            QMessageBox.information(self, "Экспорт DOCX", f"Документ успешно сохранен:\n{p}")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка DOCX", str(exc))

    def _browse_whisper_input(self):
        p, _ = QFileDialog.getOpenFileName(self, "Выберите видео или аудио", "", "Media (*.*)")
        if p:
            self.ed_wh_input.setText(p)

    def _browse_whisper_model(self):
        p, _ = QFileDialog.getOpenFileName(self, "Выберите модель ggml-*.bin", get_bin_dir(), "Model (*.bin)")
        if p:
            self.ed_wh_model.setText(p)

    def _enqueue_whisper_pipeline(self):
        in_media = self.ed_wh_input.text().strip()
        if not os.path.isfile(in_media):
            QMessageBox.warning(self, "Whisper AI", "Выберите существующий медиафайл!")
            return

        ffmpeg_bin = resolve_tool("ffmpeg")
        whisper_bin = resolve_tool("whisper-cli")
        if not ffmpeg_bin or not whisper_bin:
            QMessageBox.warning(
                self, "Whisper AI",
                "Не найден FFmpeg или Whisper.cpp CLI. Установите их через «CLI утилиты и портативность»."
            )
            return

        model_path = self.ed_wh_model.text().strip()
        if not os.path.isfile(model_path):
            QMessageBox.warning(
                self, "Модель Whisper не найдена",
                f"Файл модели не найден:\n{model_path}\n\nПереустановите Whisper.cpp CLI или выберите существующий .bin файл."
            )
            return

        lang = self.cmb_wh_lang.currentText()
        wav_16k = OutputDirectoryManager.resolve_output_path(in_media, "_16k.wav")
        srt_file = f"{wav_16k}.srt"

        cmd_wav = [ffmpeg_bin, "-y", "-i", in_media, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav_16k]
        cmd_wh = [whisper_bin, "-m", model_path, "-l", lang, "-osrt", "-otxt", "-f", wav_16k]
        cmds = [cmd_wav, cmd_wh]
        final_out = srt_file

        ext = os.path.splitext(in_media)[1].lower()
        if self.chk_wh_burn.isChecked() and ext in VIDEO_EXTS:
            subbed_video = OutputDirectoryManager.resolve_output_path(in_media, "_with_subs.mp4")
            audio_args = ["-c:a", "copy"] if ext in (".mp4", ".mov", ".m4v") else ["-c:a", "aac", "-b:a", "192k"]
            cmds.append(
                [ffmpeg_bin, "-y", "-i", in_media, "-i", srt_file, "-c:v", "copy"]
                + audio_args
                + ["-c:s", "mov_text", subbed_video]
            )
            final_out = subbed_video

        spec = TaskSpec(
            task_id=str(uuid.uuid4())[:8],
            title=f"Whisper AI -> {os.path.basename(final_out)}",
            module_name="Локальный ИИ",
            commands=cmds,
            output_path=final_out,
        )
        self.engine.submit_task(spec)

    def _browse_esrgan_input(self):
        p, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите изображение или видео",
            "",
            "Images & Video (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff *.mp4 *.mkv *.mov *.avi *.webm);;All (*.*)"
        )
        if p:
            self.ed_esr_input.setText(p)

    @staticmethod
    def _probe_video_fps(video_path: str) -> str:
        ffprobe_bin = resolve_tool("ffprobe")
        if not ffprobe_bin:
            return "30"
        try:
            proc = subprocess.run(
                [
                    ffprobe_bin, "-v", "error", "-select_streams", "v:0",
                    "-show_entries", "stream=r_frame_rate",
                    "-of", "default=noprint_wrappers=1:nokey=1", video_path
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdin=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
                timeout=6,
            )
            rate = (proc.stdout or "").strip().splitlines()[0].strip()
            if "/" in rate:
                num, den = rate.split("/", 1)
                fps_val = float(num) / float(den)
                if 1.0 <= fps_val <= 240.0:
                    return rate
            elif rate:
                fps_val = float(rate)
                if 1.0 <= fps_val <= 240.0:
                    return rate
        except Exception:
            pass
        return "30"

    def _enqueue_esrgan_task(self):
        in_path = self.ed_esr_input.text().strip()
        if not os.path.isfile(in_path):
            QMessageBox.warning(self, "Real-ESRGAN Vulkan", "Выберите существующий файл!")
            return

        esr_bin = resolve_tool("realesrgan-ncnn-vulkan")
        if not esr_bin:
            QMessageBox.warning(
                self, "Real-ESRGAN не установлен",
                "Не найден realesrgan-ncnn-vulkan.exe.\nУстановите его через «CLI утилиты и портативность»."
            )
            return

        esr_dir = os.path.dirname(os.path.abspath(esr_bin))
        heal_realesrgan_models(esr_dir)
        models_dir = os.path.join(esr_dir, "models")

        model = self.cmb_esr_model.currentText()
        scale = self.cmb_esr_scale.currentText()
        param_name = f"{model}-x{scale}.param" if model == "realesr-animevideov3" else f"{model}.param"
        if not os.path.isfile(os.path.join(models_dir, param_name)):
            QMessageBox.warning(
                self, "Модели Real-ESRGAN не найдены",
                f"Не найден файл модели:\n{os.path.join(models_dir, param_name)}\n\n"
                "Удалите бинарник Real-ESRGAN из ./bin и скачайте пакет заново через «CLI утилиты и портативность»."
            )
            return

        ffmpeg_bin = resolve_tool("ffmpeg")
        ext = os.path.splitext(in_path)[1].lower()
        task_id = str(uuid.uuid4())[:8]

        if ext in VIDEO_EXTS:
            if not ffmpeg_bin:
                QMessageBox.warning(self, "FFmpeg не найден", "Для ИИ-апскейла видео требуется FFmpeg!")
                return
            fps_str = self._probe_video_fps(in_path)
            raw_frames = OutputDirectoryManager.resolve_output_path(in_path, f"_frames_in_{task_id}")
            up_frames = OutputDirectoryManager.resolve_output_path(in_path, f"_frames_up_{task_id}")
            os.makedirs(raw_frames, exist_ok=True)
            os.makedirs(up_frames, exist_ok=True)
            out_video = OutputDirectoryManager.resolve_output_path(in_path, f"_ai_{scale}x.mp4")

            cmds = [
                [ffmpeg_bin, "-y", "-i", in_path, "-qscale:v", "2", os.path.join(raw_frames, "frame_%06d.jpg")],
                [esr_bin, "-i", raw_frames, "-o", up_frames, "-m", "models", "-n", model, "-s", scale, "-f", "jpg", "-v"],
                [
                    ffmpeg_bin, "-y", "-framerate", fps_str,
                    "-i", os.path.join(up_frames, "frame_%06d.jpg"),
                    "-i", in_path, "-map", "0:v:0", "-map", "1:a?",
                    "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", out_video
                ],
            ]
            out_path = out_video
            cleanup_dirs = (raw_frames, up_frames)
        elif ext in ESRGAN_DIRECT_IMAGE_EXTS:
            out_img = OutputDirectoryManager.resolve_output_path(in_path, f"_ai_{scale}x.png")
            cmds = [[esr_bin, "-i", in_path, "-o", out_img, "-m", "models", "-n", model, "-s", scale, "-v"]]
            out_path = out_img
            cleanup_dirs = ()
        elif ext in CONVERTIBLE_IMAGE_EXTS and ffmpeg_bin:
            tmp_png = OutputDirectoryManager.resolve_output_path(in_path, f"_tmp_{task_id}.png")
            out_img = OutputDirectoryManager.resolve_output_path(in_path, f"_ai_{scale}x.png")
            cmds = [
                [ffmpeg_bin, "-y", "-i", in_path, tmp_png],
                [esr_bin, "-i", tmp_png, "-o", out_img, "-m", "models", "-n", model, "-s", scale, "-v"],
            ]
            out_path = out_img
            cleanup_dirs = (tmp_png,)
        else:
            QMessageBox.warning(
                self, "Неподдерживаемый формат",
                "Real-ESRGAN поддерживает изображения .jpg, .png, .webp (и .bmp/.tiff при наличии FFmpeg), а также видеофайлы."
            )
            return

        def _cleanup(ok: bool, _log: str):
            for p in cleanup_dirs:
                try:
                    if os.path.isdir(p):
                        shutil.rmtree(p, ignore_errors=True)
                    elif os.path.isfile(p):
                        os.remove(p)
                except Exception:
                    pass

        spec = TaskSpec(
            task_id=task_id,
            title=f"AI Upscale {scale}x -> {os.path.basename(out_path)}",
            module_name="Real-ESRGAN GPU",
            commands=cmds,
            working_dir=esr_dir,
            output_path=out_path,
            post_callback=_cleanup if cleanup_dirs else None,
        )
        self.engine.submit_task(spec)