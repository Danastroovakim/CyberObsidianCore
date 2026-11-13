# -*- coding: utf-8 -*-
"""
mod_ai_lab.py — Модуль 4: Локальные ИИ-инструменты (Tesseract OCR + Whisper CLI + Real-ESRGAN / Upscayl Vulkan) v5.4.
Добавлено:
- Поддержка кастомных NCNN-моделей (4x-AnimeSharp-fp16, ultrasharp-4x) через движок Upscayl-NCNN (upscayl-bin.exe)
- Автоматическая докачка движка upscayl-bin и выбранной модели в 1 клик прямо из очереди задач
"""

import os
import uuid
import shutil
import zipfile
import tempfile
import urllib.request
import subprocess
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QCheckBox, QTabWidget,
    QPlainTextEdit, QFileDialog, QMessageBox, QApplication
)

from core_engine import (
    BatchProcessEngine, TaskSpec, OutputDirectoryManager,
    resolve_tool, get_bin_dir, heal_realesrgan_models,
    resolve_github_asset_url, TOOL_REGISTRY, CREATE_NO_WINDOW
)
from ui_cyber_widgets import HoloCard, COLOR_PURPLE

VIDEO_EXTS = (".mp4", ".mkv", ".mov", ".avi", ".webm", ".wmv", ".m4v", ".flv")
ESRGAN_DIRECT_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
CONVERTIBLE_IMAGE_EXTS = (".bmp", ".tif", ".tiff")

CUSTOM_UPSCAYL_MODELS = {
    "4x-AnimeSharp-fp16": {
        "label": "4x-AnimeSharp-fp16 (ТОП для аниме/артов, ~34 МБ)",
        "param_url": "https://huggingface.co/Kim2091/AnimeSharp/resolve/main/NCNN/4x-AnimeSharp-fp16.param",
        "bin_url": "https://huggingface.co/Kim2091/AnimeSharp/resolve/main/NCNN/4x-AnimeSharp-fp16.bin",
    },
    "ultrasharp-4x": {
        "label": "4x-UltraSharp (ТОП для фото и скриншотов, ~33 МБ)",
        "param_url": "https://raw.githubusercontent.com/upscayl/upscayl/main/resources/models/ultrasharp-4x.param",
        "bin_url": "https://raw.githubusercontent.com/upscayl/upscayl/main/resources/models/ultrasharp-4x.bin",
    },
}


class LocalAILabModule(QWidget):
    """Локальная нейросетевая лаборатория: OCR, Whisper Subtitles и Real-ESRGAN / Upscayl Vulkan Upscale."""

    def __init__(self, engine: BatchProcessEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._pending_after_dl: set[str] = set()
        self.engine.task_finished.connect(self._on_engine_task_finished)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)

        card = HoloCard(accent_hex=COLOR_PURPLE)
        lay = QVBoxLayout(card)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_ocr_tab(), "👁 Tesseract OCR (Текст с картинок и сканов)")
        self.tabs.addTab(self._build_whisper_tab(), "🎙 AI Субтитры и Транскрибация (Whisper CLI)")
        self.tabs.addTab(self._build_esrgan_tab(), "🔮 AI Upscale 4x на GPU (Real-ESRGAN / AnimeSharp)")

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

        grid.addWidget(QLabel("Нейросетевая модель:"), 1, 0)
        self.cmb_esr_model = QComboBox()
        self.cmb_esr_model.addItem(CUSTOM_UPSCAYL_MODELS["4x-AnimeSharp-fp16"]["label"], "4x-AnimeSharp-fp16")
        self.cmb_esr_model.addItem(CUSTOM_UPSCAYL_MODELS["ultrasharp-4x"]["label"], "ultrasharp-4x")
        self.cmb_esr_model.addItem("realesrgan-x4plus (Универсальная)", "realesrgan-x4plus")
        self.cmb_esr_model.addItem("realesrgan-x4plus-anime (Аниме 6B)", "realesrgan-x4plus-anime")
        self.cmb_esr_model.addItem("realesr-animevideov3 (Быстрая для видео 2x/3x/4x)", "realesr-animevideov3")
        self.cmb_esr_model.currentIndexChanged.connect(self._on_esrgan_model_changed)
        grid.addWidget(self.cmb_esr_model, 1, 1)

        self.btn_dl_model = QPushButton("⬇ Скачать модель + движок")
        self.btn_dl_model.setObjectName("PurpleActionBtn")
        self.btn_dl_model.clicked.connect(self._download_selected_custom_model)
        grid.addWidget(self.btn_dl_model, 1, 2)

        grid.addWidget(QLabel("Кратность увеличения:"), 2, 0)
        self.cmb_esr_scale = QComboBox()
        self.cmb_esr_scale.addItems(["4", "3", "2"])
        grid.addWidget(self.cmb_esr_scale, 2, 1, 1, 2)

        self.lbl_esr_hint = QLabel("")
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

        self._on_esrgan_model_changed()
        return w

    def _current_esrgan_model_key(self) -> str:
        return self.cmb_esr_model.currentData() or self.cmb_esr_model.currentText()

    def _on_esrgan_model_changed(self):
        model_name = self._current_esrgan_model_key()
        cur = self.cmb_esr_scale.currentText()
        self.cmb_esr_scale.clear()

        if model_name in CUSTOM_UPSCAYL_MODELS or model_name == "realesr-animevideov3":
            self.cmb_esr_scale.addItems(["4", "3", "2"])
            if cur in ("4", "3", "2"):
                self.cmb_esr_scale.setCurrentText(cur)
        else:
            self.cmb_esr_scale.addItems(["4"])

        if model_name in CUSTOM_UPSCAYL_MODELS:
            bin_dir = get_bin_dir()
            has_engine = bool(resolve_tool("upscayl-bin"))
            models_dir = os.path.join(bin_dir, "models")
            has_weights = (
                os.path.isfile(os.path.join(models_dir, f"{model_name}.param"))
                and os.path.isfile(os.path.join(models_dir, f"{model_name}.bin"))
            )
            self.btn_dl_model.setVisible(True)
            if has_engine and has_weights:
                self.btn_dl_model.setText("✔ Модель готова")
                self.lbl_esr_hint.setText(
                    f"✔ Движок Upscayl-NCNN и модель {model_name} установлены и готовы к работе."
                )
            else:
                self.btn_dl_model.setText("⬇ Скачать модель + движок")
                self.lbl_esr_hint.setText(
                    f"ℹ Модель {model_name} работает через Upscayl-NCNN (~2.3 МБ + веса ~34 МБ). "
                    "Нажмите «⬇ Скачать» или сразу «Запустить» — скачается автоматически."
                )
        else:
            self.btn_dl_model.setVisible(False)
            self.lbl_esr_hint.setText(
                "ℹ Модели x4plus / x4plus-anime работают только в 4x; realesr-animevideov3 поддерживает 2x, 3x и 4x."
            )

    @staticmethod
    def _download_atomic(url: str, dest_path: str, label: str, report_cb):
        tmp_path = f"{dest_path}.part"
        req = urllib.request.Request(url, headers={"User-Agent": "CyberObsidianCore/5.4"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp, open(tmp_path, "wb") as out_f:
                total = int(resp.info().get("Content-Length", 0) or 0)
                done = 0
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    out_f.write(chunk)
                    done += len(chunk)
                    if total > 0:
                        pct = (done / total) * 100.0
                        report_cb(pct, f"Скачивание {label}: {done / 1048576:.1f} / {total / 1048576:.1f} МБ")
            os.replace(tmp_path, dest_path)
        except Exception:
            if os.path.isfile(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            raise

    def _enqueue_custom_model_download(self, model_key: str, auto_run_upscale: bool = False):
        cfg = CUSTOM_UPSCAYL_MODELS[model_key]
        bin_dir = get_bin_dir()
        models_dir = os.path.join(bin_dir, "models")
        os.makedirs(models_dir, exist_ok=True)
        task_id = str(uuid.uuid4())[:8]

        def dl_job(report):
            if not resolve_tool("upscayl-bin"):
                info = TOOL_REGISTRY["upscayl-bin"]
                zip_url = resolve_github_asset_url(
                    info["github_repo"], info["github_asset_keyword"], fallback_url=info["direct_url"]
                )
                tmp_zip = os.path.join(bin_dir, "upscayl_bin_tmp.zip")
                self._download_atomic(zip_url, tmp_zip, "Upscayl-NCNN", report)
                report(50.0, "Распаковка upscayl-bin.exe в ./bin...")
                with zipfile.ZipFile(tmp_zip, "r") as zf:
                    for member in zf.namelist():
                        fname = os.path.basename(member.replace("\\", "/"))
                        if fname.lower().endswith((".exe", ".dll")):
                            with zf.open(member) as src, open(os.path.join(bin_dir, fname), "wb") as dst:
                                shutil.copyfileobj(src, dst)
                if os.path.isfile(tmp_zip):
                    os.remove(tmp_zip)

            param_dest = os.path.join(models_dir, f"{model_key}.param")
            bin_dest = os.path.join(models_dir, f"{model_key}.bin")
            if not os.path.isfile(param_dest):
                self._download_atomic(cfg["param_url"], param_dest, f"{model_key}.param", report)
            if not os.path.isfile(bin_dest):
                self._download_atomic(cfg["bin_url"], bin_dest, f"{model_key}.bin", report)
            return f"Upscayl-NCNN и модель {model_key} готовы!"

        if auto_run_upscale:
            self._pending_after_dl.add(task_id)

        spec = TaskSpec(
            task_id=task_id,
            title=f"Скачивание ИИ-модели {model_key}",
            module_name="Real-ESRGAN / Upscayl",
            output_path=models_dir,
            native_callable=dl_job,
        )
        self.engine.submit_task(spec)

    def _download_selected_custom_model(self):
        model_key = self._current_esrgan_model_key()
        if model_key not in CUSTOM_UPSCAYL_MODELS:
            return
        self._enqueue_custom_model_download(model_key, auto_run_upscale=False)

    def _on_engine_task_finished(self, task_id: str, success: bool, _msg: str, _out: str):
        self._on_esrgan_model_changed()
        if task_id in self._pending_after_dl:
            self._pending_after_dl.discard(task_id)
            if success:
                self._enqueue_esrgan_task()

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
            QMessageBox.warning(self, "Real-ESRGAN / Upscayl", "Выберите существующий файл!")
            return

        model = self._current_esrgan_model_key()
        scale = self.cmb_esr_scale.currentText()
        is_custom = model in CUSTOM_UPSCAYL_MODELS

        if is_custom:
            bin_dir = get_bin_dir()
            models_dir = os.path.join(bin_dir, "models")
            engine_bin = resolve_tool("upscayl-bin")
            has_weights = (
                os.path.isfile(os.path.join(models_dir, f"{model}.param"))
                and os.path.isfile(os.path.join(models_dir, f"{model}.bin"))
            )
            if not engine_bin or not has_weights:
                ans = QMessageBox.question(
                    self,
                    "Докачка модели",
                    f"Для модели {model} нужен движок Upscayl-NCNN (~2.3 МБ) и веса (~34 МБ).\n\n"
                    "Скачать их автоматически и сразу запустить апскейл?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if ans == QMessageBox.Yes:
                    self._enqueue_custom_model_download(model, auto_run_upscale=True)
                return
            work_dir = os.path.dirname(os.path.abspath(engine_bin))
            heal_realesrgan_models(work_dir)
            extra_scale_args = ["-z", "4", "-s", scale]
        else:
            engine_bin = resolve_tool("realesrgan-ncnn-vulkan") or resolve_tool("upscayl-bin")
            if not engine_bin:
                QMessageBox.warning(
                    self, "Real-ESRGAN не установлен",
                    "Не найден realesrgan-ncnn-vulkan.exe.\nУстановите его через «CLI утилиты и портативность»."
                )
                return
            work_dir = os.path.dirname(os.path.abspath(engine_bin))
            heal_realesrgan_models(work_dir)
            models_dir = os.path.join(work_dir, "models")
            param_name = f"{model}-x{scale}.param" if model == "realesr-animevideov3" else f"{model}.param"
            if not os.path.isfile(os.path.join(models_dir, param_name)):
                QMessageBox.warning(
                    self, "Модели не найдены",
                    f"Не найден файл модели:\n{os.path.join(models_dir, param_name)}\n\n"
                    "Переустановите Real-ESRGAN Vulkan через «CLI утилиты и портативность»."
                )
                return
            extra_scale_args = ["-s", scale]

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
                [engine_bin, "-i", raw_frames, "-o", up_frames, "-m", models_dir, "-n", model] + extra_scale_args + ["-f", "jpg", "-v"],
                [
                    ffmpeg_bin, "-y", "-framerate", fps_str,
                    "-i", os.path.join(up_frames, "frame_%06d.jpg"),
                    "-i", in_path, "-map", "0:v:0", "-map", "1:a?",
                    "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", out_video
                ],
            ]
            out_path = out_video
            cleanup_targets = (raw_frames, up_frames)
        elif ext in ESRGAN_DIRECT_IMAGE_EXTS:
            out_img = OutputDirectoryManager.resolve_output_path(in_path, f"_ai_{scale}x.png")
            cmds = [[engine_bin, "-i", in_path, "-o", out_img, "-m", models_dir, "-n", model] + extra_scale_args + ["-v"]]
            out_path = out_img
            cleanup_targets = ()
        elif ext in CONVERTIBLE_IMAGE_EXTS and ffmpeg_bin:
            tmp_png = OutputDirectoryManager.resolve_output_path(in_path, f"_tmp_{task_id}.png")
            out_img = OutputDirectoryManager.resolve_output_path(in_path, f"_ai_{scale}x.png")
            cmds = [
                [ffmpeg_bin, "-y", "-i", in_path, tmp_png],
                [engine_bin, "-i", tmp_png, "-o", out_img, "-m", models_dir, "-n", model] + extra_scale_args + ["-v"],
            ]
            out_path = out_img
            cleanup_targets = (tmp_png,)
        else:
            QMessageBox.warning(
                self, "Неподдерживаемый формат",
                "Поддерживаются изображения .jpg, .png, .webp (и .bmp/.tiff при наличии FFmpeg), а также видеофайлы."
            )
            return

        def _cleanup(_ok: bool, _log: str):
            for p in cleanup_targets:
                try:
                    if os.path.isdir(p):
                        shutil.rmtree(p, ignore_errors=True)
                    elif os.path.isfile(p):
                        os.remove(p)
                except Exception:
                    pass

        spec = TaskSpec(
            task_id=task_id,
            title=f"AI Upscale ({model} {scale}x) -> {os.path.basename(out_path)}",
            module_name="Real-ESRGAN / Upscayl",
            commands=cmds,
            working_dir=work_dir,
            output_path=out_path,
            post_callback=_cleanup if cleanup_targets else None,
        )
        self.engine.submit_task(spec)