# Project Map - CyberObsidianCore

## Project purpose
Десктопный мультимедийный и файловый комбайн на Python (PySide6) с интерфейсом в стиле киберпанк.

## Project Purpose
Десктопный медиа- и файловый комбайн на Python (Qt/PyQt), упаковываемый через PyInstaller в единый `CyberObsidianCore.exe`. Объединяет 4 модуля: видео/аудио студию, загрузчик медиа, универсальный конвертер/архиватор и локальную ИИ-лабораторию (OCR/Транскрибация).

## Core Architecture & Modules
- `main.py` — Точка входа, главное окно `CyberObsidianMainWindow`, диалог проверки/докачки утилит `BootstrapperDialog`, HUD и глобальная очередь задач.
- `core_engine.py` — Ядро системы: `BatchProcessEngine` (управление пулом потоков `QThread` и дочерними процессами), `TaskSpec`, поиск и проверка внешних CLI-утилит (`resolve_tool()`, `get_tools_status()`), сборка Portable ZIP.
- `ui_cyber_widgets.py` — Кастомные киберпанк-виджеты интерфейса (`HoloCard`, таблицы, анимации, HUD-мониторинг GPU через `nvidia-smi`).
- `mod_studio.py` — `MediaStudioModule`: монтаж, склейка и конвертация видео/аудио через `ffmpeg` / `ffprobe` (с поддержкой аппаратных энкодеров).
- `mod_downloader.py` — `UltimateDownloaderModule`: скачивание видео/аудио через `yt-dlp` (` probe_worker`, работа с `obsidian_cookies.txt` и браузерами).
- `mod_converter.py` — `UniversalConverterModule`: конвертация PDF/документов/изображений и работа с архивами (`PyMuPDF/fitz`, `Pillow`, `soffice`, `7z`, `exiftool`, `tarfile`).
- `mod_ai_lab.py` — `LocalAILabModule`: локальный OCR и обработка аудио/видео (`tesseract`, `whisper` / `ggml-base.bin`, покадровая обработка).
- `deploy_and_build.py` — Скрипт сборки релизного `.exe` через PyInstaller (`CyberObsidianCore.spec`).

## Key Relationships & Rules for AI
1. **Сначала граф:** Перед поиском связей всегда сверяйся с `graphify-out/GRAPH_REPORT.md`.
2. **Главные узлы (God Nodes):** `CyberObsidianMainWindow` -> модули `mod_*` -> формируют `TaskSpec` -> передают в `BatchProcessEngine` (`core_engine.py`), который вызывает внешние бинарники через `resolve_tool()`.
3. **Игнорировать:** Папки `bin/`, `build/`, `dist/`, `__pycache__/`, `test/` и файл `CyberObsidianCore.exe` не трогать и не индексировать.
