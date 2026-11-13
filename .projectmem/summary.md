# projectmem - CyberObsidianCore

_Last updated: 2026-11-13_

## Project purpose
Десктопный мультимедийный и файловый комбайн на Python (PySide6) с интерфейсом в стиле киберпанк.

## Recent issues
- [OPEN] #0006 _download_file writes straight to dest; aborted download leaves broken exe/ggml-base.bin treated as installed [core_engine.py:556] (open)
- [OPEN] #0005 detect_gpu_encoders checks compiled-in encoders, not hardware; NVENC auto-selected on non-NVIDIA machines [core_engine.py:153] (open)
- [OPEN] #0003 Cancel broken: between-step cancel reports success; native_callable tasks cannot cancel/pause [core_engine.py:959] (open)
- [OPEN] #0001 UI thread blocked: resolve_tool os.walk, ffprobe/tesseract/exiftool/yt-dlp subprocess.run, self-test, portable ZIP run in GUI slots [core_engine.py:450] (open)
- [DONE] #0004 Security: portable ZIP bundles ./bin incl. obsidian_cookies*.txt; 7z password shown in CLI HUD; tarfile.extractall without filter [core_engine.py:771] (fixed)
- [DONE] #0002 No closeEvent; worker deleteLater on task_finished emitted inside run(); probe_worker overwritten while running: QThread destroyed while running [core_engine.py:1092] (fixed)

## Decisions
- No decisions logged yet.

## Notes
- Architecture: PySide6 desktop app, flat layout. main.py=window+BootstrapperDialog; core_engine.py=resolve_tool, AutoBootstrapperThread, TaskSpec, BatchProcessEngine (1 QThread per task, max 2); ui_cyber_widgets.py=QSS+painted widgets; mod_*.py=4 pages build TaskSpec for engine. [core_engine.py]

## Key files
- `main.py`
- `core_engine.py`
- `ui_cyber_widgets.py`
- `os.walk`
- `subprocess.run`
- `tarfile.extractall`
- `exe/ggml-base.bin`
- `worker.deleteLater`
- `QThread.finished`
- `MainWindow.closeEvent`

## Open questions
- None logged yet.
