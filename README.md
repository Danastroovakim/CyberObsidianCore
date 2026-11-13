# CyberObsidianCore

Десктопный мультимедийный и файловый комбайн на Python (PySide6) с интерфейсом в стиле киберпанк.

## Основные возможности

Система состоит из 4 ключевых функциональных модулей:

1. **Media Studio (`mod_studio.py`)**
   - Нарезка, склейка, транскодирование видео и аудио.
   - Поддержка аппаратных энкодеров (NVENC, QSV, AMF) и фильтров через `ffmpeg`/`ffprobe`.

2. **Ultimate Downloader (`mod_downloader.py`)**
   - Загрузка медиапотоков через `yt-dlp`.
   - Поддержка извлечения аудио, списков воспроизведения и интеграции cookies браузеров.

3. **Universal Converter (`mod_converter.py`)**
   - Пакетная конвертация форматов документов, изображений и PDF (`PyMuPDF`, `Pillow`, `python-docx`, `soffice`).
   - Управление архивами (`7z`, `tarfile`).

4. **Local AI Lab (`mod_ai_lab.py`)**
   - Локальное распознавание текста (OCR) через `tesseract`.
   - Автономная транскрибация аудио/видео в текст через `whisper.cpp` (`ggml-base.bin`).

## Архитектура проекта

- `main.py` — главное окно приложения (`CyberObsidianMainWindow`), статус-панель и очередь задач.
- `core_engine.py` — движок фоновых потоков `BatchProcessEngine` (`QThread`), спецификации задач `TaskSpec`, автопоиск внешних утилит `resolve_tool()`.
- `ui_cyber_widgets.py` — кастомные UI-компоненты (`HoloCard`, стилизованные таблицы, графики, мониторинг GPU).
- `deploy_and_build.py` — автоматизация сборки нативного `.exe` через PyInstaller.

## Требования и установка

### Зависимости Python

Требуется Python 3.10+:

```bash
pip install -r requirements.txt
```

### Внешние бинарные утилиты

Для полной функциональности проект использует внешние CLI-утилиты (размещаются в папке `./bin/` или системном `PATH`):
- `ffmpeg`, `ffprobe`
- `yt-dlp`
- `7z`
- `aria2c`
- `tesseract`
- `whisper-cli` / `ggml-base.bin`

При запуске встроенный автозагрузчик проверяет наличие необходимых компонентов.

## Запуск и сборка

### Запуск в режиме разработки

```bash
python main.py
```

### Сборка автономного .EXE

```bash
python deploy_and_build.py
```

## Лицензия

Проект распространяется под лицензией [MIT](LICENSE).
