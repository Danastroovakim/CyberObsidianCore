# -*- coding: utf-8 -*-
"""
mod_converter.py — Модуль 3: Универсальный Конвертер «Всё во Всё» v5.3.
Содержит поддержку внешних CLI (Pandoc, LibreOffice, Ghostscript, QPDF, ImageMagick, ExifTool, 7-Zip)
и встроенное нативное ядро Python (PyMuPDF/fitz, python-docx, Pillow, zipfile/tarfile).
"""

import os
import csv
import json
import uuid
import zipfile
import tarfile
import textwrap
import subprocess

from PIL import Image, ExifTags
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QSpinBox, QTabWidget,
    QListWidget, QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox
)

from core_engine import (
    BatchProcessEngine, TaskSpec, OutputDirectoryManager, resolve_tool, CREATE_NO_WINDOW
)
from ui_cyber_widgets import HoloCard, COLOR_CYAN


class UniversalConverterModule(QWidget):
    """Универсальный комбайн документов, PDF, графики, метаданных EXIF и архивов."""

    def __init__(self, engine: BatchProcessEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)

        card = HoloCard(accent_hex=COLOR_CYAN)
        lay = QVBoxLayout(card)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_docs_tab(), "📄 Документы и Офис (Из коробки / Pandoc)")
        self.tabs.addTab(self._build_pdf_tab(), "📕 Инструментарий PDF (Из коробки / QPDF)")
        self.tabs.addTab(self._build_image_tab(), "🖼 Графический Конвейер (Из коробки / .ICO)")
        self.tabs.addTab(self._build_exif_tab(), "🕵 Чистка Метаданных (Из коробки / ExifTool)")
        self.tabs.addTab(self._build_archive_tab(), "📦 Ультра-Архиватор (Из коробки / 7-Zip)")

        lay.addWidget(self.tabs)
        root.addWidget(card)

    def _build_docs_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        grid = QGridLayout()

        grid.addWidget(QLabel("Исходный документ (DOCX, PDF, TXT, MD, HTML, EPUB, CSV, JSON):"), 0, 0)
        self.ed_doc_in = QLineEdit()
        btn_b = QPushButton("📂 Выбрать документ")
        btn_b.clicked.connect(self._browse_doc)
        grid.addWidget(self.ed_doc_in, 0, 1)
        grid.addWidget(btn_b, 0, 2)

        grid.addWidget(QLabel("Целевой формат конвертации:"), 1, 0)
        self.cmb_doc_out = QComboBox()
        self.cmb_doc_out.addItems(["pdf", "docx", "txt", "md", "html", "epub", "csv", "json"])
        grid.addWidget(self.cmb_doc_out, 1, 1, 1, 2)

        grid.addWidget(QLabel("Движок конвертации:"), 2, 0)
        self.cmb_doc_engine = QComboBox()
        self.cmb_doc_engine.addItems([
            "⚡ Авто-маршрутизатор (Встроенное Нативное Ядро Python -> Pandoc -> LibreOffice)",
            "Встроенное Нативное Ядро Python (Мгновенно из коробки, без внешних утилит)",
            "Pandoc Universal CLI",
            "LibreOffice Headless (soffice --headless)",
        ])
        grid.addWidget(self.cmb_doc_engine, 2, 1, 1, 2)

        lay.addLayout(grid)
        lay.addStretch(1)

        btn_go = QPushButton("📄 КОНВЕРТИРОВАТЬ ДОКУМЕНТ")
        btn_go.setObjectName("CyanActionBtn")
        btn_go.setMinimumHeight(44)
        btn_go.clicked.connect(self._enqueue_doc_conversion)
        lay.addWidget(btn_go)
        return w

    def _build_pdf_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        grid = QGridLayout()
        grid.addWidget(QLabel("Операция над PDF (Работает из коробки через встроенное ядро PyMuPDF или CLI):"), 0, 0)
        self.cmb_pdf_op = QComboBox()
        self.cmb_pdf_op.addItems([
            "Сжать и оптимизировать PDF (Garbage Collect + Deflate Streams)",
            "Объединить несколько PDF в один файл (Merge PDF)",
            "Извлечь диапазон страниц из PDF (Split PDF)",
            "Установить пароль шифрования AES-256 на PDF (Encrypt PDF)",
            "Снять пароль / ограничения с PDF (Decrypt PDF)",
            "Отрендерить все страницы PDF в четкие изображения PNG (300 DPI)",
        ])
        grid.addWidget(self.cmb_pdf_op, 0, 1, 1, 3)

        grid.addWidget(QLabel("Степень сжатия:"), 1, 0)
        self.cmb_gs_profile = QComboBox()
        self.cmb_gs_profile.addItems([
            "/ebook (Оптимальный баланс размера и четкости)",
            "/screen (Максимальное сжатие)",
            "/printer (Высокое качество 300 DPI)",
        ])
        grid.addWidget(self.cmb_gs_profile, 1, 1)

        grid.addWidget(QLabel("Диапазон страниц (напр. 1-5):"), 1, 2)
        self.ed_pdf_pages = QLineEdit("1-5")
        grid.addWidget(self.ed_pdf_pages, 1, 3)

        grid.addWidget(QLabel("Пароль PDF (для защиты или снятия):"), 2, 0)
        self.ed_pdf_pwd = QLineEdit()
        self.ed_pdf_pwd.setPlaceholderText("Введите пароль...")
        grid.addWidget(self.ed_pdf_pwd, 2, 1, 1, 3)

        lay.addLayout(grid)

        lay.addWidget(QLabel("Список PDF-файлов для обработки / слияния:"))
        row_lst = QHBoxLayout()
        self.lst_pdfs = QListWidget()
        col_btn = QVBoxLayout()
        btn_add_p = QPushButton("➕ Добавить PDF")
        btn_add_p.clicked.connect(self._add_pdf_files)
        btn_clr_p = QPushButton("🗑 Очистить")
        btn_clr_p.clicked.connect(self.lst_pdfs.clear)
        col_btn.addWidget(btn_add_p)
        col_btn.addWidget(btn_clr_p)
        col_btn.addStretch(1)
        row_lst.addWidget(self.lst_pdfs, 1)
        row_lst.addLayout(col_btn)
        lay.addLayout(row_lst, 1)

        btn_pdf = QPushButton("📕 ВЫПОЛНИТЬ ОПЕРАЦИЮ PDF")
        btn_pdf.setObjectName("PurpleActionBtn")
        btn_pdf.setMinimumHeight(44)
        btn_pdf.clicked.connect(self._enqueue_pdf_task)
        lay.addWidget(btn_pdf)
        return w

    def _build_image_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        grid = QGridLayout()
        grid.addWidget(QLabel("Целевой формат изображений:"), 0, 0)
        self.cmb_img_fmt = QComboBox()
        self.cmb_img_fmt.addItems([
            "webp", "png", "jpg", "ico (Мультиразмерная иконка 256..16px)", "tiff", "bmp", "pdf"
        ])
        grid.addWidget(self.cmb_img_fmt, 0, 1)

        grid.addWidget(QLabel("Качество сжатия (1-100):"), 0, 2)
        self.spn_img_q = QSpinBox()
        self.spn_img_q.setRange(1, 100)
        self.spn_img_q.setValue(92)
        grid.addWidget(self.spn_img_q, 0, 3)

        grid.addWidget(QLabel("Ресайз (напр. 1920x1080 или 50%, пусто = без изм.):"), 1, 0)
        self.ed_img_resize = QLineEdit()
        self.ed_img_resize.setPlaceholderText("напр. 1920x1080 или 50%")
        grid.addWidget(self.ed_img_resize, 1, 1, 1, 3)

        lay.addLayout(grid)

        lay.addWidget(QLabel("Пакетный список изображений (Работает из коробки через Pillow или ImageMagick):"))
        row_i = QHBoxLayout()
        self.lst_images = QListWidget()
        col_i = QVBoxLayout()
        btn_add_i = QPushButton("➕ Добавить фото")
        btn_add_i.clicked.connect(self._add_image_files)
        btn_clr_i = QPushButton("🗑 Очистить")
        btn_clr_i.clicked.connect(self.lst_images.clear)
        col_i.addWidget(btn_add_i)
        col_i.addWidget(btn_clr_i)
        col_i.addStretch(1)
        row_i.addWidget(self.lst_images, 1)
        row_i.addLayout(col_i)
        lay.addLayout(row_i, 1)

        btn_img = QPushButton("🖼 ЗАПУСТИТЬ ПАКЕТНЫЙ ГРАФИЧЕСКИЙ КОНВЕЙЕР")
        btn_img.setObjectName("EmeraldActionBtn")
        btn_img.setMinimumHeight(44)
        btn_img.clicked.connect(self._enqueue_image_batch)
        lay.addWidget(btn_img)
        return w

    def _build_exif_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        top = QHBoxLayout()
        self.ed_exif_file = QLineEdit()
        self.ed_exif_file.setPlaceholderText("Выберите фото или PDF для аудита и удаления скрытых метаданных...")
        btn_b = QPushButton("📂 Выбрать и просканировать")
        btn_b.clicked.connect(self._browse_and_inspect_exif)
        top.addWidget(self.ed_exif_file, 1)
        top.addWidget(btn_b)
        lay.addLayout(top)

        self.tbl_exif = QTableWidget(0, 2)
        self.tbl_exif.setHorizontalHeaderLabels(["Тег метаданных (EXIF / XMP / GPS / PDF Info)", "Зашитое значение"])
        self.tbl_exif.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_exif.setAlternatingRowColors(True)
        lay.addWidget(self.tbl_exif, 1)

        btn_nuke = QPushButton("☢ УНИЧТОЖИТЬ ВСЕ МЕТАДАННЫЕ (РАБОТАЕТ ИЗ КОРОБКИ И ЧЕРЕЗ EXIFTOOL)")
        btn_nuke.setObjectName("DangerBtn")
        btn_nuke.setMinimumHeight(44)
        btn_nuke.clicked.connect(self._nuke_metadata)
        lay.addWidget(btn_nuke)
        return w

    def _build_archive_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        grid = QGridLayout()
        grid.addWidget(QLabel("Режим архиватора:"), 0, 0)
        self.cmb_7z_op = QComboBox()
        self.cmb_7z_op.addItems([
            "Упаковать с максимальным сжатием Ultra",
            "Распаковать архив (zip, 7z, tar, gz, rar)",
        ])
        grid.addWidget(self.cmb_7z_op, 0, 1)

        grid.addWidget(QLabel("Формат архива:"), 0, 2)
        self.cmb_7z_fmt = QComboBox()
        self.cmb_7z_fmt.addItems(["zip (Из коробки / 7-Zip)", "7z (7-Zip Ultra)", "tar.gz (Из коробки)"])
        grid.addWidget(self.cmb_7z_fmt, 0, 3)

        grid.addWidget(QLabel("Файл или папка:"), 1, 0)
        self.ed_7z_target = QLineEdit()
        btn_7z_f = QPushButton("📂 Файл")
        btn_7z_f.clicked.connect(self._browse_7z_file)
        btn_7z_d = QPushButton("📁 Папка")
        btn_7z_d.clicked.connect(self._browse_7z_dir)
        grid.addWidget(self.ed_7z_target, 1, 1)
        grid.addWidget(btn_7z_f, 1, 2)
        grid.addWidget(btn_7z_d, 1, 3)

        grid.addWidget(QLabel("Пароль AES-256 (для 7-Zip):"), 2, 0)
        self.ed_7z_pwd = QLineEdit()
        self.ed_7z_pwd.setPlaceholderText("Опционально")
        grid.addWidget(self.ed_7z_pwd, 2, 1, 1, 3)

        lay.addLayout(grid)
        lay.addStretch(1)

        btn_7z_go = QPushButton("📦 ВЫПОЛНИТЬ ОПЕРАЦИЮ АРХИВАТОРА")
        btn_7z_go.setObjectName("CyanActionBtn")
        btn_7z_go.setMinimumHeight(44)
        btn_7z_go.clicked.connect(self._enqueue_7z_task)
        lay.addWidget(btn_7z_go)
        return w

    def load_external_file(self, path: str):
        ext = os.path.splitext(path)[1].lower()
        if ext == ".pdf":
            self.tabs.setCurrentIndex(1)
            self.lst_pdfs.addItem(path)
        elif ext in (".png", ".jpg", ".jpeg", ".webp", ".avif", ".heic", ".bmp", ".tiff", ".svg"):
            self.tabs.setCurrentIndex(2)
            self.lst_images.addItem(path)
        elif ext in (".7z", ".zip", ".rar", ".tar", ".gz", ".iso"):
            self.tabs.setCurrentIndex(4)
            self.ed_7z_target.setText(path)
            self.cmb_7z_op.setCurrentIndex(1)
        else:
            self.tabs.setCurrentIndex(0)
            self.ed_doc_in.setText(path)

    def _browse_doc(self):
        p, _ = QFileDialog.getOpenFileName(self, "Выберите документ", "", "All Files (*.*)")
        if p:
            self.ed_doc_in.setText(p)

    def _add_pdf_files(self):
        ps, _ = QFileDialog.getOpenFileNames(self, "Выберите PDF", "", "PDF Files (*.pdf)")
        for p in ps:
            self.lst_pdfs.addItem(p)

    def _add_image_files(self):
        ps, _ = QFileDialog.getOpenFileNames(
            self, "Выберите изображения", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tiff *.ico);;All (*.*)"
        )
        for p in ps:
            self.lst_images.addItem(p)

    def _browse_7z_file(self):
        p, _ = QFileDialog.getOpenFileName(self, "Выберите файл", "", "All Files (*.*)")
        if p:
            self.ed_7z_target.setText(p)

    def _browse_7z_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Выберите папку")
        if d:
            self.ed_7z_target.setText(d)

    def _enqueue_doc_conversion(self):
        in_path = self.ed_doc_in.text().strip()
        if not os.path.isfile(in_path):
            QMessageBox.warning(self, "Конвертер документов", "Выберите существующий файл документа!")
            return

        target_ext = self.cmb_doc_out.currentText()
        in_ext = os.path.splitext(in_path)[1].lower().lstrip(".")
        out_path = OutputDirectoryManager.resolve_output_path(in_path, f"_converted.{target_ext}")
        eng_choice = self.cmb_doc_engine.currentIndex()

        pandoc_bin = resolve_tool("pandoc")
        soffice_bin = resolve_tool("soffice")

        use_native = (
            eng_choice == 1
            or (in_ext, target_ext) in (("csv", "json"), ("json", "csv"))
            or (in_ext == "pdf" and target_ext in ("txt", "md", "html", "docx"))
            or (target_ext == "pdf" and eng_choice == 0 and not soffice_bin)
            or (
                in_ext in ("txt", "md", "docx")
                and target_ext in ("txt", "md", "html", "docx", "pdf")
                and not pandoc_bin
                and not soffice_bin
            )
        )

        if use_native:
            def native_doc_job(report):
                report(20.0, f"Чтение исходного документа .{in_ext}...")
                if (in_ext, target_ext) == ("csv", "json"):
                    with open(in_path, "r", encoding="utf-8", errors="replace") as f:
                        rows = list(csv.DictReader(f))
                    with open(out_path, "w", encoding="utf-8") as out_f:
                        json.dump(rows, out_f, ensure_ascii=False, indent=2)
                    return f"CSV -> JSON сохранен: {out_path}"

                if (in_ext, target_ext) == ("json", "csv"):
                    with open(in_path, "r", encoding="utf-8", errors="replace") as f:
                        data = json.load(f)
                    if isinstance(data, list) and data and isinstance(data[0], dict):
                        with open(out_path, "w", encoding="utf-8", newline="") as out_f:
                            writer = csv.DictWriter(out_f, fieldnames=list(data[0].keys()))
                            writer.writeheader()
                            writer.writerows(data)
                    return f"JSON -> CSV сохранен: {out_path}"

                extracted_text = ""
                if in_ext == "pdf":
                    import fitz
                    doc = fitz.open(in_path)
                    pages_txt = []
                    for idx, page in enumerate(doc):
                        report(20.0 + (idx / max(1, len(doc))) * 50.0, f"Извлечение страницы PDF {idx + 1}/{len(doc)}")
                        pages_txt.append(page.get_text("text"))
                    extracted_text = "\n\n".join(pages_txt)
                    doc.close()
                elif in_ext == "docx":
                    import docx
                    d = docx.Document(in_path)
                    extracted_text = "\n".join([p.text for p in d.paragraphs])
                else:
                    with open(in_path, "r", encoding="utf-8", errors="replace") as f:
                        extracted_text = f.read()

                report(80.0, f"Запись в целевой формат .{target_ext}...")
                if target_ext in ("txt", "md"):
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(extracted_text)
                elif target_ext == "html":
                    html_body = "<br>\n".join(extracted_text.splitlines())
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(f"<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>{html_body}</body></html>")
                elif target_ext == "docx":
                    import docx
                    d_out = docx.Document()
                    for line in extracted_text.splitlines():
                        d_out.add_paragraph(line)
                    d_out.save(out_path)
                elif target_ext == "pdf":
                    import fitz
                    pdf_out = fitz.open()
                    font_path = next(
                        (
                            fp for fp in (
                                r"C:\Windows\Fonts\arial.ttf",
                                r"C:\Windows\Fonts\segoeui.ttf",
                                r"C:\Windows\Fonts\times.ttf",
                            ) if os.path.isfile(fp)
                        ),
                        None,
                    )
                    wrapped_lines = []
                    for raw_line in extracted_text.splitlines():
                        if not raw_line.strip():
                            wrapped_lines.append("")
                        else:
                            wrapped_lines.extend(textwrap.wrap(raw_line, width=85, break_long_words=True))
                    if not wrapped_lines:
                        wrapped_lines = [""]

                    lines_per_page = 48
                    for i in range(0, len(wrapped_lines), lines_per_page):
                        page = pdf_out.new_page()
                        if font_path:
                            page.insert_font(fontname="cyr", fontfile=font_path)
                        y = 50
                        for ln in wrapped_lines[i:i + lines_per_page]:
                            if ln:
                                page.insert_text(
                                    (45, y), ln, fontsize=10.5,
                                    fontname="cyr" if font_path else "helv"
                                )
                            y += 15
                    try:
                        pdf_out.subset_fonts()
                    except Exception:
                        pass
                    pdf_out.save(out_path, deflate=True)
                    pdf_out.close()
                return f"Успешно сконвертировано встроенным ядром: {out_path}"

            spec = TaskSpec(
                task_id=str(uuid.uuid4())[:8],
                title=f"Документ (Из коробки) {in_ext.upper()} -> {target_ext.upper()}",
                module_name="Конвертер Документов",
                output_path=out_path,
                native_callable=native_doc_job,
            )
            self.engine.submit_task(spec)
            return

        if eng_choice == 3 or (soffice_bin and target_ext == "pdf"):
            out_dir = os.path.dirname(out_path)
            cmd = [soffice_bin or "soffice", "--headless", "--convert-to", target_ext, "--outdir", out_dir, in_path]
        else:
            cmd = [pandoc_bin or "pandoc", in_path, "-o", out_path]

        spec = TaskSpec(
            task_id=str(uuid.uuid4())[:8],
            title=f"Документ {in_ext.upper()} -> {target_ext.upper()}",
            module_name="Конвертер Документов",
            commands=[cmd],
            output_path=out_path,
        )
        self.engine.submit_task(spec)

    def _enqueue_pdf_task(self):
        if self.lst_pdfs.count() == 0:
            QMessageBox.warning(self, "PDF Комбайн", "Добавьте хотя бы один PDF файл в список!")
            return

        first_pdf = self.lst_pdfs.item(0).text()
        op_idx = self.cmb_pdf_op.currentIndex()
        all_pdfs = [self.lst_pdfs.item(i).text() for i in range(self.lst_pdfs.count())]
        page_range_str = self.ed_pdf_pages.text().strip() or "1-1"
        pwd = self.ed_pdf_pwd.text().strip()

        out_map = {
            0: OutputDirectoryManager.resolve_output_path(first_pdf, "_compressed.pdf"),
            1: OutputDirectoryManager.resolve_output_path(first_pdf, "_merged.pdf"),
            2: OutputDirectoryManager.resolve_output_path(first_pdf, f"_pages_{page_range_str}.pdf"),
            3: OutputDirectoryManager.resolve_output_path(first_pdf, "_encrypted.pdf"),
            4: OutputDirectoryManager.resolve_output_path(first_pdf, "_unlocked.pdf"),
            5: OutputDirectoryManager.resolve_output_path(first_pdf, "_pages_png"),
        }
        out_path = out_map[op_idx]

        def native_pdf_job(report):
            import fitz

            if op_idx == 0:
                report(30.0, "Глубокая очистка объектов и сжатие потоков PDF...")
                doc = fitz.open(first_pdf)
                doc.save(out_path, garbage=4, deflate=True, clean=True)
                doc.close()
                return f"PDF сжат: {out_path}"

            elif op_idx == 1:
                merged = fitz.open()
                for idx, p in enumerate(all_pdfs):
                    report(((idx + 1) / len(all_pdfs)) * 90.0, f"Слияние файла {os.path.basename(p)}...")
                    with fitz.open(p) as src:
                        merged.insert_pdf(src)
                merged.save(out_path)
                merged.close()
                return f"Объединено {len(all_pdfs)} PDF -> {out_path}"

            elif op_idx == 2:
                parts = page_range_str.split("-")
                p_start = max(1, int(parts[0])) - 1
                p_end = int(parts[1]) - 1 if len(parts) > 1 else p_start
                src = fitz.open(first_pdf)
                dst = fitz.open()
                dst.insert_pdf(src, from_page=p_start, to_page=min(len(src) - 1, p_end))
                dst.save(out_path)
                dst.close()
                src.close()
                return f"Страницы извлечены -> {out_path}"

            elif op_idx == 3:
                if not pwd:
                    raise ValueError("Не задан пароль для шифрования PDF!")
                doc = fitz.open(first_pdf)
                doc.save(
                    out_path,
                    encryption=fitz.PDF_ENCRYPT_AES_256,
                    user_pw=pwd,
                    owner_pw=pwd,
                )
                doc.close()
                return f"PDF защищен AES-256 -> {out_path}"

            elif op_idx == 4:
                doc = fitz.open(first_pdf)
                if doc.is_encrypted and not doc.authenticate(pwd):
                    doc.close()
                    raise ValueError("Неверный пароль для расшифровки PDF!")
                doc.save(out_path, encryption=fitz.PDF_ENCRYPT_NONE)
                doc.close()
                return f"Защита PDF снята -> {out_path}"

            else:
                os.makedirs(out_path, exist_ok=True)
                doc = fitz.open(first_pdf)
                total = max(1, len(doc))
                for i, page in enumerate(doc):
                    report(((i + 1) / total) * 95.0, f"Рендер страницы {i + 1}/{total} в PNG...")
                    pix = page.get_pixmap(dpi=220)
                    pix.save(os.path.join(out_path, f"page_{i + 1:03d}.png"))
                doc.close()
                return f"Страницы отрендерены в {out_path}"

        spec = TaskSpec(
            task_id=str(uuid.uuid4())[:8],
            title=f"PDF Операция -> {os.path.basename(out_path)}",
            module_name="PDF Инструментарий",
            output_path=out_path,
            native_callable=native_pdf_job,
        )
        self.engine.submit_task(spec)

    def _enqueue_image_batch(self):
        if self.lst_images.count() == 0:
            QMessageBox.warning(self, "Графический конвейер", "Добавьте изображения в пакетный список!")
            return

        fmt_raw = self.cmb_img_fmt.currentText().split()[0].lower()
        q_val = self.spn_img_q.value()
        resize_str = self.ed_img_resize.text().strip()
        files = [self.lst_images.item(i).text() for i in range(self.lst_images.count())]
        last_out = OutputDirectoryManager.resolve_output_path(files[-1], f"_obsidian.{fmt_raw}")

        def native_img_job(report):
            total = len(files)
            for idx, img_path in enumerate(files):
                out_file = OutputDirectoryManager.resolve_output_path(img_path, f"_obsidian.{fmt_raw}")
                report(((idx + 1) / total) * 95.0, f"Конвертация {os.path.basename(img_path)} -> .{fmt_raw}")
                with Image.open(img_path) as im:
                    if resize_str:
                        if resize_str.endswith("%"):
                            scale = float(resize_str[:-1]) / 100.0
                            nw, nh = max(1, int(im.width * scale)), max(1, int(im.height * scale))
                            im = im.resize((nw, nh), Image.LANCZOS)
                        elif "x" in resize_str.lower():
                            parts = resize_str.lower().replace(">", "").split("x")
                            nw, nh = int(parts[0]), int(parts[1])
                            im = im.resize((nw, nh), Image.LANCZOS)

                    if fmt_raw == "ico":
                        if im.mode != "RGBA":
                            im = im.convert("RGBA")
                        im.save(
                            out_file,
                            format="ICO",
                            sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
                        )
                    elif fmt_raw in ("jpg", "jpeg", "bmp", "pdf"):
                        if im.mode not in ("RGB", "L"):
                            im = im.convert("RGB")
                        im.save(out_file, quality=q_val)
                    else:
                        if im.mode == "P" and fmt_raw == "webp":
                            im = im.convert("RGBA")
                        im.save(out_file, quality=q_val)
            return f"Обработано {total} изображений!"

        spec = TaskSpec(
            task_id=str(uuid.uuid4())[:8],
            title=f"Графика ({len(files)} шт. -> .{fmt_raw})",
            module_name="Графический Конвейер",
            output_path=last_out,
            native_callable=native_img_job,
        )
        self.engine.submit_task(spec)

    def _browse_and_inspect_exif(self):
        p, _ = QFileDialog.getOpenFileName(self, "Выберите файл для аудита метаданных", "", "All Files (*.*)")
        if not p:
            return
        self.ed_exif_file.setText(p)
        self.tbl_exif.setRowCount(0)

        exif_bin = resolve_tool("exiftool")
        if exif_bin:
            try:
                proc = subprocess.run(
                    [exif_bin, "-j", p],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=CREATE_NO_WINDOW,
                    timeout=8,
                )
                arr = json.loads(proc.stdout or "[]")
                if arr and isinstance(arr[0], dict):
                    for k, v in arr[0].items():
                        r = self.tbl_exif.rowCount()
                        self.tbl_exif.insertRow(r)
                        self.tbl_exif.setItem(r, 0, QTableWidgetItem(str(k)))
                        self.tbl_exif.setItem(r, 1, QTableWidgetItem(str(v)))
                    return
            except Exception:
                pass

        ext = os.path.splitext(p)[1].lower()
        try:
            if ext == ".pdf":
                import fitz
                doc = fitz.open(p)
                for k, v in (doc.metadata or {}).items():
                    r = self.tbl_exif.rowCount()
                    self.tbl_exif.insertRow(r)
                    self.tbl_exif.setItem(r, 0, QTableWidgetItem(f"PDF:{k}"))
                    self.tbl_exif.setItem(r, 1, QTableWidgetItem(str(v)))
                doc.close()
            else:
                with Image.open(p) as im:
                    exif_data = im.getexif()
                    for tag_id, val in exif_data.items():
                        tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                        r = self.tbl_exif.rowCount()
                        self.tbl_exif.insertRow(r)
                        self.tbl_exif.setItem(r, 0, QTableWidgetItem(str(tag_name)))
                        self.tbl_exif.setItem(r, 1, QTableWidgetItem(str(val)))
                    for k, v in im.info.items():
                        if k != "exif":
                            r = self.tbl_exif.rowCount()
                            self.tbl_exif.insertRow(r)
                            self.tbl_exif.setItem(r, 0, QTableWidgetItem(f"Info:{k}"))
                            self.tbl_exif.setItem(r, 1, QTableWidgetItem(str(v)[:200]))
        except Exception as exc:
            QMessageBox.warning(self, "Метаданные", f"Не удалось прочитать теги: {exc}")

    def _nuke_metadata(self):
        p = self.ed_exif_file.text().strip()
        if not os.path.isfile(p):
            QMessageBox.warning(self, "Очистка метаданных", "Сначала выберите файл!")
            return

        out_clean = OutputDirectoryManager.resolve_output_path(
            p, f"_anonymized{os.path.splitext(p)[1]}"
        )
        exif_bin = resolve_tool("exiftool")

        def native_exif_nuke(report):
            report(40.0, "Удаление всех EXIF/GPS/XMP профилей...")
            ext = os.path.splitext(p)[1].lower()
            if ext == ".pdf":
                import fitz
                doc = fitz.open(p)
                doc.set_metadata({})
                doc.del_xml_metadata()
                doc.save(out_clean, garbage=4, deflate=True)
                doc.close()
            else:
                with Image.open(p) as im:
                    work = im.convert("RGBA") if im.mode in ("P", "PA") else im
                    if ext in (".jpg", ".jpeg") and work.mode not in ("RGB", "L"):
                        work = work.convert("RGB")
                    clean_img = Image.frombytes(work.mode, work.size, work.tobytes())
                    clean_img.save(out_clean, quality=95)
            return f"Метаданные полностью уничтожены: {out_clean}"

        if exif_bin and not OutputDirectoryManager.use_custom_dir:
            spec = TaskSpec(
                task_id=str(uuid.uuid4())[:8],
                title=f"ExifTool Очистка: {os.path.basename(p)}",
                module_name="Деструктор Метаданных",
                commands=[[exif_bin, "-all=", "-overwrite_original", p]],
                output_path=p,
            )
        else:
            spec = TaskSpec(
                task_id=str(uuid.uuid4())[:8],
                title=f"Анонимизация -> {os.path.basename(out_clean)}",
                module_name="Деструктор Метаданных",
                output_path=out_clean,
                native_callable=native_exif_nuke,
            )
        self.engine.submit_task(spec)

    def _enqueue_7z_task(self):
        target = self.ed_7z_target.text().strip()
        if not target or not os.path.exists(target):
            QMessageBox.warning(self, "Архиватор", "Укажите существующий файл или папку!")
            return

        sz_bin = resolve_tool("7z")
        pwd = self.ed_7z_pwd.text().strip()
        fmt = self.cmb_7z_fmt.currentText().split()[0]

        if self.cmb_7z_op.currentIndex() == 0:
            out_arch = OutputDirectoryManager.resolve_output_path(target, f"_ultra.{fmt}")
            if sz_bin and fmt in ("7z", "zip"):
                cmd = [sz_bin, "a", f"-t{fmt}", "-mx=9", "-mmt=on", out_arch, target]
                if pwd:
                    cmd.append(f"-p{pwd}")
                    if fmt == "7z":
                        cmd.append("-mhe=on")
                spec = TaskSpec(
                    task_id=str(uuid.uuid4())[:8],
                    title=f"7-Zip Ultra -> {os.path.basename(out_arch)}",
                    module_name="Архиватор",
                    commands=[cmd],
                    output_path=out_arch,
                    metadata={"pwd": pwd} if pwd else {},
                )
            else:
                def native_pack(report):
                    report(30.0, f"Упаковка в {os.path.basename(out_arch)}...")
                    if fmt == "tar.gz":
                        with tarfile.open(out_arch, "w:gz") as tf:
                            tf.add(target, arcname=os.path.basename(target))
                    else:
                        out_z = out_arch if out_arch.endswith(".zip") else f"{out_arch}.zip"
                        with zipfile.ZipFile(out_z, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
                            if os.path.isdir(target):
                                for root, _, files in os.walk(target):
                                    for f in files:
                                        fp = os.path.join(root, f)
                                        zf.write(fp, os.path.relpath(fp, os.path.dirname(target)))
                            else:
                                zf.write(target, os.path.basename(target))
                    return f"Архив создан: {out_arch}"

                spec = TaskSpec(
                    task_id=str(uuid.uuid4())[:8],
                    title=f"Упаковка (Из коробки) -> {os.path.basename(out_arch)}",
                    module_name="Архиватор",
                    output_path=out_arch,
                    native_callable=native_pack,
                )
        else:
            out_dir = OutputDirectoryManager.resolve_output_path(target, "_unpacked")
            os.makedirs(out_dir, exist_ok=True)
            if sz_bin:
                cmd = [sz_bin, "x", target, f"-o{out_dir}", "-y"]
                if pwd:
                    cmd.append(f"-p{pwd}")
                spec = TaskSpec(
                    task_id=str(uuid.uuid4())[:8],
                    title=f"Распаковка -> {os.path.basename(out_dir)}",
                    module_name="Архиватор",
                    commands=[cmd],
                    output_path=out_dir,
                    metadata={"pwd": pwd} if pwd else {},
                )
            else:
                def native_unpack(report):
                    report(40.0, "Распаковка архива встроенным ядром...")
                    if zipfile.is_zipfile(target):
                        with zipfile.ZipFile(target, "r") as zf:
                            zf.extractall(out_dir)
                    elif tarfile.is_tarfile(target):
                        with tarfile.open(target, "r:*") as tf:
                            tf.extractall(out_dir, filter="data")
                    else:
                        raise RuntimeError("Для распаковки .7z/.rar установите 7-Zip (2 МБ) через менеджер утилит.")
                    return f"Распаковано в {out_dir}"

                spec = TaskSpec(
                    task_id=str(uuid.uuid4())[:8],
                    title=f"Распаковка (Из коробки) -> {os.path.basename(out_dir)}",
                    module_name="Архиватор",
                    output_path=out_dir,
                    native_callable=native_unpack,
                )

        self.engine.submit_task(spec)