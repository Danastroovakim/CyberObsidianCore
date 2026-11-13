# -*- coding: utf-8 -*-
"""
core_engine.py — Системное ядро Cyber-Obsidian Media & Document Core v5.4.
Добавлена поддержка Upscayl-NCNN (upscayl-bin.exe) для кастомных моделей (4x-AnimeSharp, 4x-UltraSharp).
"""

import os
import sys
import re
import glob
import json
import shutil
import ctypes
import zipfile
import urllib.request
import subprocess
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Tuple

import psutil
from PySide6.QtCore import QObject, Signal, QThread, QMutex, QMutexLocker

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
HIGH_PRIORITY_CLASS = 0x00000080 if sys.platform == "win32" else 0


def is_admin() -> bool:
    if sys.platform != "win32":
        return os.geteuid() == 0
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def elevate_to_admin():
    if sys.platform == "win32" and not is_admin():
        executable = sys.executable
        args = sys.argv[1:] if getattr(sys, "frozen", False) else sys.argv
        params = " ".join([f'"{arg}"' for arg in args])
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, None, 1)
        if int(rc) > 32:
            sys.exit(0)


def get_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def refresh_system_path_from_registry():
    if sys.platform != "win32":
        return
    try:
        import winreg
        paths = []
        for hive, subkey in [
            (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
            (winreg.HKEY_CURRENT_USER, r"Environment"),
        ]:
            try:
                with winreg.OpenKey(hive, subkey) as key:
                    val, _ = winreg.QueryValueEx(key, "Path")
                    if val:
                        paths.append(os.path.expandvars(val))
            except Exception:
                pass
        if paths:
            cur = os.environ.get("PATH", "")
            combined = os.pathsep.join(paths + [cur])
            seen = set()
            clean_list = []
            for p in combined.split(os.pathsep):
                p_norm = p.strip()
                if p_norm and p_norm.lower() not in seen:
                    seen.add(p_norm.lower())
                    clean_list.append(p_norm)
            os.environ["PATH"] = os.pathsep.join(clean_list)
    except Exception:
        pass


def get_bin_dir() -> str:
    bin_path = os.path.join(get_base_dir(), "bin")
    os.makedirs(bin_path, exist_ok=True)
    current_path = os.environ.get("PATH", "")
    if bin_path not in current_path:
        os.environ["PATH"] = f"{bin_path}{os.pathsep}{current_path}"
    return bin_path


def heal_realesrgan_models(bin_dir: Optional[str] = None):
    """
    Переносит файлы моделей (.param и парные/realesr* .bin) из корня ./bin
    в подпапку ./bin/models, не затрагивая ggml-*.bin (модели Whisper).
    """
    if not bin_dir:
        bin_dir = get_bin_dir()
    if not os.path.isdir(bin_dir):
        return
    models_dir = os.path.join(bin_dir, "models")
    try:
        entries = os.listdir(bin_dir)
    except Exception:
        return

    param_stems = {
        os.path.splitext(f)[0].lower()
        for f in entries
        if f.lower().endswith(".param") and os.path.isfile(os.path.join(bin_dir, f))
    }
    has_realesr_bins = any(
        f.lower().startswith("realesr") and f.lower().endswith(".bin")
        and os.path.isfile(os.path.join(bin_dir, f))
        for f in entries
    )
    if not param_stems and not has_realesr_bins:
        return

    os.makedirs(models_dir, exist_ok=True)
    for fname in entries:
        fpath = os.path.join(bin_dir, fname)
        if not os.path.isfile(fpath):
            continue
        low = fname.lower()
        stem, ext = os.path.splitext(low)
        if ext == ".param" or (ext == ".bin" and (stem in param_stems or stem.startswith("realesr"))):
            dest = os.path.join(models_dir, fname)
            try:
                if os.path.isfile(dest):
                    os.remove(fpath)
                else:
                    shutil.move(fpath, dest)
            except Exception:
                pass


def _decode_console_bytes(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        if sys.platform == "win32":
            try:
                return raw.decode("mbcs")
            except Exception:
                pass
        return raw.decode("utf-8", errors="replace")


class OutputDirectoryManager:
    """Глобальный маршрутизатор папки сохранения готовых файлов."""
    use_custom_dir: bool = False
    custom_dir_path: str = os.path.join(os.path.expanduser("~"), "Downloads", "CyberObsidian_Output")

    @classmethod
    def resolve_output_path(cls, input_path: str, suffix_with_ext: str) -> str:
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        out_filename = f"{base_name}{suffix_with_ext}"

        if cls.use_custom_dir and cls.custom_dir_path.strip():
            target_dir = cls.custom_dir_path.strip()
            os.makedirs(target_dir, exist_ok=True)
            return os.path.join(target_dir, out_filename)
        else:
            source_dir = os.path.dirname(os.path.abspath(input_path))
            return os.path.join(source_dir, out_filename)

    @classmethod
    def resolve_output_dir(cls, fallback_input_path: str = "") -> str:
        if cls.use_custom_dir and cls.custom_dir_path.strip():
            target_dir = cls.custom_dir_path.strip()
            os.makedirs(target_dir, exist_ok=True)
            return target_dir
        if fallback_input_path:
            return os.path.dirname(os.path.abspath(fallback_input_path))
        os.makedirs(cls.custom_dir_path, exist_ok=True)
        return cls.custom_dir_path


def detect_gpu_encoders() -> Dict[str, List[str]]:
    encoders = {
        "CPU (Software)": ["libx264", "libx265", "libsvtav1", "libvpx-vp9"],
        "NVIDIA NVENC": [],
        "AMD AMF": [],
        "Intel QSV": [],
    }
    ffmpeg_bin = resolve_tool("ffmpeg")
    if not ffmpeg_bin:
        return encoders
    try:
        proc = subprocess.run(
            [ffmpeg_bin, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
            timeout=6,
        )
        out = proc.stdout
        for enc in ["h264_nvenc", "hevc_nvenc", "av1_nvenc"]:
            if enc in out:
                encoders["NVIDIA NVENC"].append(enc)
        for enc in ["h264_amf", "hevc_amf", "av1_amf"]:
            if enc in out:
                encoders["AMD AMF"].append(enc)
        for enc in ["h264_qsv", "hevc_qsv", "av1_qsv"]:
            if enc in out:
                encoders["Intel QSV"].append(enc)
    except Exception:
        pass
    return encoders


TOOL_REGISTRY: Dict[str, Dict[str, str]] = {
    "ffmpeg": {
        "name": "FFmpeg",
        "exe": "ffmpeg.exe",
        "winget_id": "Gyan.FFmpeg",
        "direct_url": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
        "size_hint": "~85 МБ (Portable ZIP)",
        "fast_portable": "true",
        "builtin_fallback": "false",
        "desc": "Ядро рендера видео и аудио",
    },
    "ffprobe": {
        "name": "FFprobe",
        "exe": "ffprobe.exe",
        "winget_id": "Gyan.FFmpeg",
        "direct_url": "",
        "size_hint": "Входит в архив FFmpeg",
        "fast_portable": "true",
        "builtin_fallback": "false",
        "desc": "JSON-инспектор медиапотоков",
    },
    "yt-dlp": {
        "name": "yt-dlp",
        "exe": "yt-dlp.exe",
        "winget_id": "yt-dlp.yt-dlp",
        "direct_url": "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe",
        "size_hint": "~16 МБ (Прямой .EXE)",
        "fast_portable": "true",
        "builtin_fallback": "false",
        "desc": "Загрузчик видео/аудио с 1000+ сайтов",
    },
    "aria2c": {
        "name": "Aria2c",
        "exe": "aria2c.exe",
        "winget_id": "aria2.aria2",
        "direct_url": "https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-win-64bit-build1.zip",
        "size_hint": "~5 МБ (Portable ZIP)",
        "fast_portable": "true",
        "builtin_fallback": "false",
        "desc": "16-поточный турбо-ускоритель загрузок",
    },
    "pandoc": {
        "name": "Pandoc",
        "exe": "pandoc.exe",
        "winget_id": "JohnMacFarlane.Pandoc",
        "direct_url": "https://github.com/jgm/pandoc/releases/download/3.6.3/pandoc-3.6.3-windows-x86_64.zip",
        "size_hint": "~38 МБ (Portable ZIP)",
        "fast_portable": "true",
        "builtin_fallback": "true",
        "desc": "Конвертер документов (есть встроенное ядро)",
    },
    "soffice": {
        "name": "LibreOffice Headless",
        "exe": "soffice.exe",
        "winget_id": "TheDocumentFoundation.LibreOffice",
        "direct_url": "",
        "size_hint": "~350 МБ (Тяжелый инсталлятор — ОПЦИОНАЛЬНО)",
        "fast_portable": "false",
        "builtin_fallback": "true",
        "desc": "Офисный пакет (заменяется встроенным ядром Python)",
    },
    "magick": {
        "name": "ImageMagick",
        "exe": "magick.exe",
        "winget_id": "ImageMagick.ImageMagick",
        "direct_url": "",
        "size_hint": "~30 МБ (Есть встроенное ядро Pillow)",
        "fast_portable": "false",
        "builtin_fallback": "true",
        "desc": "Графический конвейер (из коробки работает через Pillow)",
    },
    "7z": {
        "name": "7-Zip CLI",
        "exe": "7z.exe",
        "winget_id": "7zip.7zip",
        "direct_url": "",
        "size_hint": "~2 МБ (Есть встроенное ядро архиватора)",
        "fast_portable": "true",
        "builtin_fallback": "true",
        "desc": "Ультра-архиватор (ZIP/TAR работают из коробки)",
    },
    "exiftool": {
        "name": "ExifTool",
        "exe": "exiftool.exe",
        "winget_id": "OliverBetz.ExifTool",
        "direct_url": "",
        "size_hint": "~8 МБ (Есть встроенная очистка EXIF)",
        "fast_portable": "true",
        "builtin_fallback": "true",
        "desc": "Аудит и уничтожение метаданных (работает из коробки)",
    },
    "qpdf": {
        "name": "QPDF",
        "exe": "qpdf.exe",
        "winget_id": "QPDF.QPDF",
        "github_repo": "qpdf/qpdf",
        "github_asset_keyword": "mingw64.zip",
        "direct_url": "",
        "size_hint": "~12 МБ (Заменяется встроенным PyMuPDF)",
        "fast_portable": "true",
        "builtin_fallback": "true",
        "desc": "Шифрование и склейка PDF (работает из коробки)",
    },
    "gswin64c": {
        "name": "Ghostscript",
        "exe": "gswin64c.exe",
        "winget_id": "ArtifexSoftware.GhostScript.AGPL",
        "github_repo": "ArtifexSoftware/ghostpdl-downloads",
        "github_asset_keyword": "w64.exe",
        "direct_url": "",
        "size_hint": "~45 МБ (Заменяется встроенным PyMuPDF)",
        "fast_portable": "false",
        "builtin_fallback": "true",
        "desc": "Сжатие и рендер PDF (работает из коробки)",
    },
    "tesseract": {
        "name": "Tesseract OCR",
        "exe": "tesseract.exe",
        "winget_id": "UB-Mannheim.TesseractOCR",
        "direct_url": "",
        "size_hint": "~40 МБ (WinGet пакет)",
        "fast_portable": "false",
        "builtin_fallback": "false",
        "desc": "Оптическое распознавание текста с картинок",
    },
    "whisper-cli": {
        "name": "Whisper.cpp CLI",
        "exe": "whisper-cli.exe",
        "winget_id": "",
        "github_repo": "ggml-org/whisper.cpp",
        "github_asset_keyword": "whisper-bin-x64.zip",
        "direct_url": "https://github.com/ggml-org/whisper.cpp/releases/download/v1.7.4/whisper-bin-x64.zip",
        "size_hint": "~8 МБ (Portable ZIP)",
        "fast_portable": "true",
        "builtin_fallback": "false",
        "desc": "Нейросетевая транскрибация речи в .SRT",
    },
    "realesrgan-ncnn-vulkan": {
        "name": "Real-ESRGAN Vulkan",
        "exe": "realesrgan-ncnn-vulkan.exe",
        "winget_id": "",
        "direct_url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip",
        "size_hint": "~45 МБ (Portable ZIP с весами)",
        "fast_portable": "true",
        "builtin_fallback": "false",
        "desc": "ИИ-апскейл картинок и видео 4x на видеокарте",
    },
    "upscayl-bin": {
        "name": "Upscayl-NCNN Engine",
        "exe": "upscayl-bin.exe",
        "winget_id": "",
        "github_repo": "upscayl/upscayl-ncnn",
        "github_asset_keyword": "windows.zip",
        "direct_url": "https://github.com/upscayl/upscayl-ncnn/releases/download/20251207-174704/upscayl-bin-20251207-174704-windows.zip",
        "size_hint": "~2.3 МБ (Для AnimeSharp / UltraSharp)",
        "fast_portable": "true",
        "builtin_fallback": "false",
        "desc": "Движок Vulkan для кастомных моделей 4x-AnimeSharp и 4x-UltraSharp",
    },
}

WILDCARD_WINDOWS_PATTERNS = [
    r"C:\Program Files\qpdf*\bin\qpdf.exe",
    r"C:\Program Files (x86)\qpdf*\bin\qpdf.exe",
    r"C:\Program Files\gs\gs*\bin\gswin64c.exe",
    r"C:\Program Files (x86)\gs\gs*\bin\gswin32c.exe",
    r"C:\Program Files\ImageMagick*\magick.exe",
    r"C:\Program Files\7-Zip*\7z.exe",
    r"C:\Program Files (x86)\7-Zip*\7z.exe",
    r"C:\Program Files\LibreOffice*\program\soffice.exe",
    r"C:\Program Files\Tesseract-OCR*\tesseract.exe",
    r"C:\Program Files\Pandoc*\pandoc.exe",
]


def resolve_github_asset_url(repo: str, keyword: str, fallback_url: str = "") -> str:
    api_url = f"https://api.github.com/repos/{repo}/releases?per_page=12"
    try:
        req = urllib.request.Request(
            api_url,
            headers={
                "User-Agent": "CyberObsidianCore/5.4",
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            releases = json.loads(resp.read().decode("utf-8", errors="replace"))
            for rel in releases:
                for asset in rel.get("assets", []):
                    name = asset.get("name", "").lower()
                    if keyword.lower() in name:
                        return asset.get("browser_download_url", "")
    except Exception:
        pass
    return fallback_url


def _heal_7zip_in_bin(bin_dir: str):
    local_7z = os.path.join(bin_dir, "7z.exe")
    local_dll = os.path.join(bin_dir, "7z.dll")
    if os.path.isfile(local_7z) and not os.path.isfile(local_dll):
        for prog_dir in [r"C:\Program Files\7-Zip", r"C:\Program Files (x86)\7-Zip"]:
            sys_dll = os.path.join(prog_dir, "7z.dll")
            if os.path.isfile(sys_dll):
                try:
                    shutil.copy2(sys_dll, local_dll)
                    return
                except Exception:
                    pass
        try:
            os.remove(local_7z)
        except Exception:
            pass


def copy_tool_with_companions(src_exe: str, bin_dir: str):
    exe_name = os.path.basename(src_exe).lower()
    src_dir = os.path.dirname(os.path.abspath(src_exe))

    if exe_name in ("soffice.exe", "tesseract.exe", "gswin64c.exe", "magick.exe", "qpdf.exe"):
        return
    if exe_name == "exiftool.exe" and os.path.isdir(os.path.join(src_dir, "exiftool_files")):
        return

    dest_exe = os.path.join(bin_dir, os.path.basename(src_exe))
    if os.path.abspath(src_exe).lower() != os.path.abspath(dest_exe).lower():
        shutil.copy2(src_exe, dest_exe)

    if exe_name == "7z.exe":
        dll_src = os.path.join(src_dir, "7z.dll")
        if os.path.isfile(dll_src):
            shutil.copy2(dll_src, os.path.join(bin_dir, "7z.dll"))


def resolve_tool(tool_key: str) -> Optional[str]:
    bin_dir = get_bin_dir()
    _heal_7zip_in_bin(bin_dir)
    if tool_key in ("realesrgan-ncnn-vulkan", "upscayl-bin"):
        heal_realesrgan_models(bin_dir)

    info = TOOL_REGISTRY.get(tool_key, {})
    exe_name = info.get("exe", f"{tool_key}.exe" if sys.platform == "win32" else tool_key)

    local_candidate = os.path.join(bin_dir, exe_name)
    if os.path.isfile(local_candidate):
        return local_candidate

    which_candidate = shutil.which(tool_key) or shutil.which(exe_name)
    if which_candidate:
        return which_candidate

    if tool_key == "whisper-cli":
        for alt in ["whisper-cli.exe", "main.exe", "whisper.exe", "faster-whisper-xxl.exe"]:
            alt_local = os.path.join(bin_dir, alt)
            if os.path.isfile(alt_local):
                return alt_local
            alt_which = shutil.which(alt)
            if alt_which:
                return alt_which

    if tool_key == "gswin64c":
        for alt in ["gswin64c.exe", "gswin32c.exe", "gs.exe", "gs"]:
            alt_local = os.path.join(bin_dir, alt)
            if os.path.isfile(alt_local):
                return alt_local
            alt_which = shutil.which(alt)
            if alt_which:
                return alt_which

    if sys.platform == "win32":
        for pattern in WILDCARD_WINDOWS_PATTERNS:
            if os.path.basename(pattern).lower() == exe_name.lower() or (
                tool_key == "gswin64c" and "gswin" in os.path.basename(pattern).lower()
            ):
                matches = sorted(glob.glob(pattern), reverse=True)
                if matches and os.path.isfile(matches[0]):
                    return matches[0]

        winget_links = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links")
        link_candidate = os.path.join(winget_links, exe_name)
        if os.path.isfile(link_candidate):
            return link_candidate

        for root_env in [
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs"),
            os.path.expandvars(r"%USERPROFILE%\scoop\apps"),
        ]:
            if os.path.isdir(root_env):
                for root, _, files in os.walk(root_env):
                    for f in files:
                        if f.lower() == exe_name.lower():
                            return os.path.join(root, f)

    return None


def verify_tool_works(tool_key: str) -> Tuple[bool, str]:
    path = resolve_tool(tool_key)
    if not path:
        return False, "Не установлен"

    test_args = {
        "ffmpeg": ["-version"],
        "ffprobe": ["-version"],
        "yt-dlp": ["--version"],
        "aria2c": ["--version"],
        "pandoc": ["--version"],
        "7z": ["i"],
        "exiftool": ["-ver"],
        "qpdf": ["--version"],
        "gswin64c": ["--version"],
        "tesseract": ["--version"],
        "whisper-cli": ["-h"],
        "realesrgan-ncnn-vulkan": ["-h"],
        "upscayl-bin": ["-h"],
        "magick": ["-version"],
        "soffice": ["--version"],
    }.get(tool_key, ["--version"])

    try:
        proc = subprocess.run(
            [path] + test_args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
            timeout=6,
        )
        out_combined = (proc.stdout + "\n" + proc.stderr).strip()
        unsigned_rc = proc.returncode & 0xFFFFFFFF

        if unsigned_rc in (0xC0000135, 0xC0000142, 0xC0000005, 0xC000007B):
            return False, f"Ошибка запуска / нет DLL (0x{unsigned_rc:08X})"
        if proc.returncode != 0 and not out_combined:
            return False, f"Процесс завершился с кодом {proc.returncode}"
        if "can't load" in out_combined.lower() or "missing" in out_combined.lower():
            return False, f"Ошибка DLL: {out_combined[:60]}"

        if tool_key == "realesrgan-ncnn-vulkan":
            models_dir = os.path.join(os.path.dirname(os.path.abspath(path)), "models")
            if not os.path.isdir(models_dir) or not any(
                f.lower().endswith(".param") for f in os.listdir(models_dir)
            ):
                return False, "Отсутствует папка models/ с .param весами"

        first_line = out_combined.splitlines()[0] if out_combined else "OK"
        return True, f"ОК ({first_line[:45]})"
    except Exception as exc:
        return False, f"Ошибка запуска: {exc}"


def get_tools_status() -> Dict[str, Tuple[bool, str]]:
    refresh_system_path_from_registry()
    heal_realesrgan_models(get_bin_dir())
    status = {}
    for key, info in TOOL_REGISTRY.items():
        path = resolve_tool(key)
        if path:
            status[key] = (True, path)
        elif info.get("builtin_fallback") == "true":
            status[key] = (False, "⚡ РАБОТАЕТ ИЗ КОРОБКИ (Встроенное ядро Python)")
        else:
            status[key] = (False, "НЕ УСТАНОВЛЕНО")
    return status


WINGET_CODE_HINTS = {
    2147942432: "Пакет уже установлен или его файлы открыты в системе (0x80070020)",
    2316632107: "Пакет УЖЕ установлен в системе и не требует обновления (0x8A15002B)",
    2316632084: "Пакет не найден в источнике WinGet (0x8A150014) — используем прямую загрузку с GitHub",
    2316632067: "Пакет уже установлен (NO_APPLICABLE_INSTALLER)",
}


class AutoBootstrapperThread(QThread):
    progress_signal = Signal(int, str)
    log_signal = Signal(str)
    finished_signal = Signal(dict)

    def __init__(self, target_keys: List[str]):
        super().__init__()
        self.target_keys = target_keys
        self._abort = False
        self._current_proc: Optional[subprocess.Popen] = None

    def request_abort(self):
        self._abort = True
        if self._current_proc and self._current_proc.poll() is None:
            try:
                parent = psutil.Process(self._current_proc.pid)
                for ch in parent.children(recursive=True):
                    ch.kill()
                parent.kill()
            except Exception:
                pass

    def _download_file(self, url: str, dest: str, label: str):
        req = urllib.request.Request(url, headers={"User-Agent": "CyberObsidianCore/5.4"})
        with urllib.request.urlopen(req, timeout=30) as response, open(dest, "wb") as out_file:
            total = int(response.info().get("Content-Length", 0) or 0)
            downloaded = 0
            chunk_size = 65536
            while True:
                if self._abort:
                    raise InterruptedError("Загрузка остановлена пользователем")
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                out_file.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = int(downloaded * 100 / total)
                    self.progress_signal.emit(
                        pct, f"Скачивание {label}: {pct}% ({downloaded / 1048576:.1f} / {total / 1048576:.1f} МБ)"
                    )

    def _run_winget_streamed(self, winget_id: str, name: str) -> int:
        cmd = [
            "winget", "install", "--id", winget_id,
            "--silent", "--disable-interactivity",
            "--accept-package-agreements", "--accept-source-agreements"
        ]
        self.log_signal.emit(f"[WINGET] $ {' '.join(cmd)}")

        self._current_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            bufsize=0,
            creationflags=CREATE_NO_WINDOW,
        )

        byte_buf = b""
        while True:
            if self._abort:
                break
            chunk = self._current_proc.stdout.read(4096)
            if not chunk:
                if byte_buf:
                    line = _decode_console_bytes(byte_buf).strip()
                    if len(line) > 3 and line not in ("-", "\\", "|", "/"):
                        self.log_signal.emit(f"  [winget] {line}")
                break
            byte_buf += chunk
            while True:
                idx_r = byte_buf.find(b"\r")
                idx_n = byte_buf.find(b"\n")
                if idx_r == -1 and idx_n == -1:
                    break
                pos = idx_n if idx_r == -1 else (idx_r if idx_n == -1 else min(idx_r, idx_n))
                raw_line = byte_buf[:pos]
                byte_buf = byte_buf[pos + 1:]
                line = _decode_console_bytes(raw_line).strip()
                if len(line) > 3 and line not in ("-", "\\", "|", "/"):
                    self.log_signal.emit(f"  [winget] {line}")
                    self.progress_signal.emit(50, f"{name}: {line[:55]}")

        rc = self._current_proc.wait()
        self._current_proc = None
        return rc

    def _extract_zip_to_bin(self, zip_path: str, bin_dir: str, tool_key: str):
        models_dir = os.path.join(bin_dir, "models")
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.namelist():
                norm_member = member.replace("\\", "/")
                if norm_member.endswith("/"):
                    continue
                filename = os.path.basename(norm_member)
                if not filename:
                    continue
                low_name = filename.lower()
                if not low_name.endswith((".exe", ".dll", ".bin", ".param")):
                    continue

                is_model_asset = (
                    "/models/" in f"/{norm_member.lower()}"
                    or (tool_key in ("realesrgan-ncnn-vulkan", "upscayl-bin") and low_name.endswith((".bin", ".param")))
                )
                if is_model_asset:
                    os.makedirs(models_dir, exist_ok=True)
                    target_path = os.path.join(models_dir, filename)
                else:
                    target_path = os.path.join(bin_dir, filename)

                with zf.open(member) as source, open(target_path, "wb") as target:
                    shutil.copyfileobj(source, target)

        if tool_key == "whisper-cli":
            main_exe = os.path.join(bin_dir, "main.exe")
            wh_exe = os.path.join(bin_dir, "whisper-cli.exe")
            if os.path.isfile(main_exe) and not os.path.isfile(wh_exe):
                shutil.copy2(main_exe, wh_exe)

    def run(self):
        bin_dir = get_bin_dir()
        refresh_system_path_from_registry()
        heal_realesrgan_models(bin_dir)
        total_tools = max(1, len(self.target_keys))

        for idx, key in enumerate(self.target_keys):
            if self._abort:
                self.log_signal.emit("[STOP] Установка остановлена пользователем.")
                break

            existing = resolve_tool(key)
            info = TOOL_REGISTRY.get(key, {})
            name = info.get("name", key)
            base_pct = int((idx / total_tools) * 100)

            if existing:
                self.log_signal.emit(f"[OK] {name} уже обнаружен: {existing}")
                self.progress_signal.emit(base_pct, f"{name} активен")
                continue

            self.log_signal.emit(f"\n[BOOT] >>> Развертывание {name} ({info.get('size_hint', '')})...")
            self.progress_signal.emit(base_pct, f"Установка {name}...")

            direct_url = info.get("direct_url", "")
            gh_repo = info.get("github_repo", "")
            gh_kw = info.get("github_asset_keyword", "")
            if gh_repo and gh_kw:
                self.log_signal.emit(f"[GITHUB API] Поиск актуального релиза {gh_repo} ({gh_kw})...")
                resolved_url = resolve_github_asset_url(gh_repo, gh_kw, fallback_url=direct_url)
                if resolved_url:
                    direct_url = resolved_url
                    self.log_signal.emit(f"[GITHUB API] Найден релиз: {direct_url}")

            winget_id = info.get("winget_id", "")

            if direct_url:
                try:
                    if direct_url.endswith(".zip"):
                        tmp_zip = os.path.join(bin_dir, f"{key}_temp.zip")
                        self._download_file(direct_url, tmp_zip, name)
                        self.log_signal.emit(f"[UNPACK] Распаковка {name} в ./bin...")
                        self._extract_zip_to_bin(tmp_zip, bin_dir, key)
                        os.remove(tmp_zip)

                        if key == "whisper-cli":
                            model_dest = os.path.join(bin_dir, "ggml-base.bin")
                            if not os.path.isfile(model_dest):
                                self.log_signal.emit("[WHISPER] Докачка нейросетевой модели ggml-base.bin (~142 МБ)...")
                                model_url = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin"
                                self._download_file(model_url, model_dest, "Модель ggml-base.bin")

                        if resolve_tool(key):
                            self.log_signal.emit(f"[OK] {name} успешно установлен в ./bin!")
                            continue

                    elif direct_url.endswith(".exe"):
                        if key == "gswin64c":
                            tmp_installer = os.path.join(bin_dir, "gs_setup_w64.exe")
                            self._download_file(direct_url, tmp_installer, name)
                            sz_bin = resolve_tool("7z")
                            if sz_bin:
                                self.log_signal.emit("[UNPACK] Извлечение портативного Ghostscript через 7-Zip в ./bin...")
                                subprocess.run(
                                    [sz_bin, "e", tmp_installer, f"-o{bin_dir}", "gswin64c.exe", "gsdll64.dll", "-r", "-y"],
                                    stdin=subprocess.DEVNULL,
                                    creationflags=CREATE_NO_WINDOW,
                                )
                            if not resolve_tool("gswin64c"):
                                self.log_signal.emit("[SETUP] Тихая установка Ghostscript (/S)...")
                                subprocess.run([tmp_installer, "/S"], stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
                            try:
                                os.remove(tmp_installer)
                            except Exception:
                                pass
                            refresh_system_path_from_registry()
                            if resolve_tool(key):
                                self.log_signal.emit(f"[OK] {name} готов к работе!")
                                continue
                        else:
                            dest_exe = os.path.join(bin_dir, info["exe"])
                            self._download_file(direct_url, dest_exe, name)
                            self.log_signal.emit(f"[OK] Портативный {name} сохранен в ./bin")
                            continue
                except Exception as exc:
                    if self._abort:
                        break
                    self.log_signal.emit(f"[WARN] Прямая загрузка {name} не удалась ({exc}), пробуем WinGet...")

            if winget_id and shutil.which("winget") and not self._abort:
                try:
                    rc = self._run_winget_streamed(winget_id, name)
                    unsigned_rc = rc & 0xFFFFFFFF
                    refresh_system_path_from_registry()
                    resolved = resolve_tool(key)

                    if resolved and os.path.isfile(resolved):
                        try:
                            copy_tool_with_companions(resolved, bin_dir)
                        except Exception:
                            pass
                        ok_work, test_msg = verify_tool_works(key)
                        self.log_signal.emit(f"[OK] {name} подключен: {resolved} -> {test_msg}")
                    else:
                        hint = WINGET_CODE_HINTS.get(unsigned_rc, f"код {unsigned_rc}")
                        self.log_signal.emit(f"[INFO] Статус WinGet для {name}: {hint}")
                except Exception as exc:
                    self.log_signal.emit(f"[ERROR] Ошибка WinGet для {name}: {exc}")

        self.progress_signal.emit(100, "Инициализация выбранных инструментов завершена.")
        self.finished_signal.emit(get_tools_status())


def bundle_portable_distribution(target_zip_path: str) -> Tuple[bool, str]:
    try:
        base_dir = get_base_dir()
        bin_dir = get_bin_dir()

        for k in ["ffmpeg", "ffprobe", "yt-dlp", "aria2c", "pandoc", "7z"]:
            found = resolve_tool(k)
            if found and os.path.isfile(found):
                try:
                    copy_tool_with_companions(found, bin_dir)
                except Exception:
                    pass

        with zipfile.ZipFile(target_zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            exe_candidate = os.path.join(base_dir, "CyberObsidianCore.exe")
            if os.path.isfile(exe_candidate):
                zf.write(exe_candidate, "CyberObsidianCore/CyberObsidianCore.exe")
            for fname in os.listdir(base_dir):
                if fname.endswith((".py", ".ico")):
                    zf.write(os.path.join(base_dir, fname), f"CyberObsidianCore/{fname}")
            for root, _, files in os.walk(bin_dir):
                for f in files:
                    if "cookies" in f.lower() and f.lower().endswith(".txt"):
                        continue
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, base_dir)
                    zf.write(full_p, f"CyberObsidianCore/{rel_p}")

        return True, f"Портативный дистрибутив упакован: {target_zip_path}"
    except Exception as exc:
        return False, str(exc)


@dataclass
class TaskSpec:
    task_id: str
    title: str
    module_name: str
    commands: List[List[str]] = field(default_factory=list)
    working_dir: str = ""
    output_path: str = ""
    expected_duration_sec: float = 0.0
    native_callable: Optional[Callable[[Callable[[float, str], None]], str]] = None
    post_callback: Optional[Callable[[bool, str], None]] = None
    metadata: Dict[str, str] = field(default_factory=dict)


class RegexStreamParser:
    RE_FFMPEG_DUR = re.compile(r"Duration:\s*(\d{2}):(\d{2}):(\d{2})\.(\d{2})")
    RE_FFMPEG_TIME = re.compile(r"time=\s*(\d{2}):(\d{2}):(\d{2})\.(\d{2})")
    RE_FFMPEG_FPS = re.compile(r"fps=\s*([\d\.]+)")
    RE_FFMPEG_SPEED = re.compile(r"speed=\s*([\d\.]+)x")
    RE_FFMPEG_BITRATE = re.compile(r"bitrate=\s*([\d\.]+\s*\w+/s)")

    RE_YTDLP_PCT = re.compile(
        r"\[download\]\s+([\d\.]+)%\s+of\s+~?([\d\.]+\w+)\s+at\s+([\d\.]+\w+/s)\s+ETA\s+([\d:]+)"
    )
    RE_YTDLP_SIMPLE = re.compile(r"\[download\]\s+([\d\.]+)%")
    RE_ARIA2C = re.compile(
        r"\[#[0-9a-fA-F]+\s+[^\(\)]+\(([\d\.]+)%\)\s+CN:\d+\s+DL:([^\s]+)(?:\s+ETA:([^\]]+))?\]"
    )
    RE_ESRGAN_PCT = re.compile(r"^(\d+(?:\.\d+)?)%$")

    def __init__(self, initial_duration: float = 0.0):
        self.duration_sec = initial_duration

    @staticmethod
    def hms_to_sec(h: str, m: str, s: str, cs: str) -> float:
        return int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100.0

    def parse_line(self, line: str) -> Optional[Tuple[float, str]]:
        if self.duration_sec <= 0:
            m_dur = self.RE_FFMPEG_DUR.search(line)
            if m_dur:
                self.duration_sec = self.hms_to_sec(*m_dur.groups())

        m_time = self.RE_FFMPEG_TIME.search(line)
        if m_time:
            cur_sec = self.hms_to_sec(*m_time.groups())
            pct = min(99.9, (cur_sec / self.duration_sec) * 100.0) if self.duration_sec > 0 else 50.0
            fps_m = self.RE_FFMPEG_FPS.search(line)
            spd_m = self.RE_FFMPEG_SPEED.search(line)
            br_m = self.RE_FFMPEG_BITRATE.search(line)

            fps_str = f"{fps_m.group(1)} FPS" if fps_m else ""
            spd_val = float(spd_m.group(1)) if spd_m and float(spd_m.group(1)) > 0 else 0.0
            spd_str = f"{spd_val:.2f}x" if spd_val > 0 else ""
            br_str = br_m.group(1) if br_m else ""

            eta_str = ""
            if self.duration_sec > cur_sec and spd_val > 0:
                rem_sec = int((self.duration_sec - cur_sec) / spd_val)
                eta_str = f"ETA {rem_sec // 60:02d}:{rem_sec % 60:02d}"

            metrics = " | ".join(filter(None, [fps_str, spd_str, br_str, eta_str]))
            return pct, metrics or f"Рендер: {cur_sec:.1f} сек"

        m_yt = self.RE_YTDLP_PCT.search(line)
        if m_yt:
            pct = float(m_yt.group(1))
            size_s, speed_s, eta_s = m_yt.group(2), m_yt.group(3), m_yt.group(4)
            return pct, f"{size_s} | {speed_s} | ETA {eta_s}"

        m_aria = self.RE_ARIA2C.search(line)
        if m_aria:
            pct = float(m_aria.group(1))
            dl_s = m_aria.group(2)
            eta_s = m_aria.group(3) or "--:--"
            return pct, f"Aria2c 16x | {dl_s}/s | ETA {eta_s}"

        m_yts = self.RE_YTDLP_SIMPLE.search(line)
        if m_yts:
            return float(m_yts.group(1)), "Скачивание потока..."

        m_esr = self.RE_ESRGAN_PCT.match(line.strip())
        if m_esr:
            return min(99.9, float(m_esr.group(1))), f"ИИ-апскейл GPU: {m_esr.group(1)}%"

        return None


class AsyncTaskWorker(QThread):
    task_started = Signal(str, str)
    task_progress = Signal(str, float, str)
    task_log = Signal(str, str)
    task_finished = Signal(str, bool, str, str)

    def __init__(self, spec: TaskSpec, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.spec = spec
        self._active_pid: Optional[int] = None
        self._cancelled = False
        self._paused = False
        self._mutex = QMutex()

    def _mask_arg(self, arg: str) -> str:
        s = str(arg)
        pwd = self.spec.metadata.get("pwd")
        if (pwd and s == f"-p{pwd}") or (
            s.startswith("-p") and len(s) > 2
            and s not in ("-preset", "-pix_fmt", "-pass", "-png")
            and not s.startswith("-profile")
        ):
            return "-p***"
        return f'"{s}"' if " " in s else s

    def get_formatted_command(self) -> str:
        if self.spec.native_callable and not self.spec.commands:
            return f"[NATIVE PYTHON CORE] Выполнение встроенного модуля: {self.spec.title}"
        cmds = []
        for c in self.spec.commands:
            cmds.append(" ".join([self._mask_arg(arg) for arg in c]))
        return " && ".join(cmds)

    def pause_process(self):
        with QMutexLocker(self._mutex):
            if self._active_pid and not self._paused:
                try:
                    parent = psutil.Process(self._active_pid)
                    for child in parent.children(recursive=True):
                        child.suspend()
                    parent.suspend()
                    self._paused = True
                    self.task_log.emit(self.spec.task_id, "[SYSTEM] Поток приостановлен (SUSPENDED).")
                except Exception as exc:
                    self.task_log.emit(self.spec.task_id, f"[WARN] Ошибка паузы: {exc}")

    def resume_process(self):
        with QMutexLocker(self._mutex):
            if self._active_pid and self._paused:
                try:
                    parent = psutil.Process(self._active_pid)
                    parent.resume()
                    for child in parent.children(recursive=True):
                        child.resume()
                    self._paused = False
                    self.task_log.emit(self.spec.task_id, "[SYSTEM] Поток возобновлен (RESUMED).")
                except Exception as exc:
                    self.task_log.emit(self.spec.task_id, f"[WARN] Ошибка возобновления: {exc}")

    def kill_process_tree(self):
        with QMutexLocker(self._mutex):
            self._cancelled = True
            if self._active_pid:
                try:
                    parent = psutil.Process(self._active_pid)
                    for child in parent.children(recursive=True):
                        try:
                            child.kill()
                        except Exception:
                            pass
                    parent.kill()
                    self.task_log.emit(self.spec.task_id, "[SYSTEM] Дерево процессов принудительно завершено.")
                except Exception:
                    pass

    def run(self):
        full_cmd_str = self.get_formatted_command()
        self.task_started.emit(self.spec.task_id, full_cmd_str)

        if self.spec.native_callable:
            try:
                self.task_log.emit(self.spec.task_id, f">>> Запуск встроенного нативного движка: {self.spec.title}")

                def report_cb(pct: float, msg: str):
                    self.task_progress.emit(self.spec.task_id, pct, msg)
                    self.task_log.emit(self.spec.task_id, f"[NATIVE] {pct:.1f}% — {msg}")

                result_msg = self.spec.native_callable(report_cb)
                self.task_progress.emit(self.spec.task_id, 100.0, "ЗАВЕРШЕНО 100% (ВСТРОЕННОЕ ЯДРО)")
                self.task_finished.emit(self.spec.task_id, True, result_msg or "Готово", self.spec.output_path)
            except Exception as exc:
                self.task_log.emit(self.spec.task_id, f"[NATIVE ERROR] {exc}")
                self.task_finished.emit(self.spec.task_id, False, str(exc), self.spec.output_path)
            return

        parser = RegexStreamParser(initial_duration=self.spec.expected_duration_sec)
        total_steps = max(1, len(self.spec.commands))
        collected_output: List[str] = []

        child_env = os.environ.copy()
        child_env["PYTHONIOENCODING"] = "utf-8"
        child_env["PYTHONUTF8"] = "1"

        def _handle_line(line: str, step_idx: int):
            collected_output.append(line)
            if len(collected_output) > 300:
                collected_output.pop(0)
            self.task_log.emit(self.spec.task_id, line)
            parsed = parser.parse_line(line)
            if parsed:
                raw_pct, metrics = parsed
                overall_pct = ((step_idx + (raw_pct / 100.0)) / total_steps) * 100.0
                self.task_progress.emit(self.spec.task_id, overall_pct, metrics)

        for step_idx, cmd in enumerate(self.spec.commands):
            if self._cancelled:
                break

            step_str = " ".join([self._mask_arg(a) for a in cmd])
            self.task_log.emit(self.spec.task_id, f"\n>>> [ШАГ {step_idx + 1}/{total_steps}] $ {step_str}")

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    cwd=self.spec.working_dir or None,
                    env=child_env,
                    bufsize=0,
                    creationflags=CREATE_NO_WINDOW,
                )
            except FileNotFoundError:
                err_msg = f"Бинарник '{cmd[0]}' не найден. Откройте 'CLI Утилиты' для быстрой докачки."
                self.task_log.emit(self.spec.task_id, f"[FATAL] {err_msg}")
                self.task_finished.emit(self.spec.task_id, False, err_msg, self.spec.output_path)
                return
            except Exception as exc:
                err_msg = f"Ошибка запуска процесса: {exc}"
                self.task_log.emit(self.spec.task_id, f"[FATAL] {err_msg}")
                self.task_finished.emit(self.spec.task_id, False, err_msg, self.spec.output_path)
                return

            with QMutexLocker(self._mutex):
                self._active_pid = proc.pid

            try:
                ps_proc = psutil.Process(proc.pid)
                if sys.platform == "win32":
                    ps_proc.nice(psutil.HIGH_PRIORITY_CLASS)
            except Exception:
                pass

            byte_buf = b""
            while True:
                if self._cancelled:
                    break
                chunk = proc.stdout.read(4096)
                if not chunk:
                    if byte_buf:
                        line = _decode_console_bytes(byte_buf).strip()
                        byte_buf = b""
                        if line:
                            _handle_line(line, step_idx)
                    break
                byte_buf += chunk
                while True:
                    idx_r = byte_buf.find(b"\r")
                    idx_n = byte_buf.find(b"\n")
                    if idx_r == -1 and idx_n == -1:
                        break
                    pos = idx_n if idx_r == -1 else (idx_r if idx_n == -1 else min(idx_r, idx_n))
                    raw_line = byte_buf[:pos]
                    byte_buf = byte_buf[pos + 1:]
                    line = _decode_console_bytes(raw_line).strip()
                    if line:
                        _handle_line(line, step_idx)

            proc.wait()
            if self._cancelled:
                self.task_finished.emit(self.spec.task_id, False, "Отменено пользователем", self.spec.output_path)
                return

            if proc.returncode != 0:
                full_tail = "\n".join(collected_output[-15:])
                if (
                    "unable to download video subtitles" in full_tail.lower()
                    and (
                        "merging formats into" in full_tail.lower()
                        or "has already been downloaded" in full_tail.lower()
                        or "[sponsorblock]" in full_tail.lower()
                    )
                ):
                    self.task_log.emit(
                        self.spec.task_id,
                        "[INFO] Видео успешно скачано (одна из дорожек субтитров была пропущена из-за лимита YouTube 429)."
                    )
                else:
                    tail = "\n".join(collected_output[-4:])
                    err_msg = f"Код возврата {proc.returncode}: {tail}"
                    self.task_finished.emit(self.spec.task_id, False, err_msg, self.spec.output_path)
                    return

            step_done_pct = ((step_idx + 1) / total_steps) * 100.0
            self.task_progress.emit(self.spec.task_id, step_done_pct, f"Шаг {step_idx + 1}/{total_steps} готов")

        self.task_progress.emit(self.spec.task_id, 100.0, "ЗАВЕРШЕНО 100%")
        if self.spec.post_callback:
            try:
                self.spec.post_callback(True, "\n".join(collected_output))
            except Exception as cb_err:
                self.task_log.emit(self.spec.task_id, f"[WARN] Post-callback: {cb_err}")

        self.task_finished.emit(self.spec.task_id, True, "Успешно выполнено", self.spec.output_path)


class BatchProcessEngine(QObject):
    task_added = Signal(TaskSpec)
    task_started = Signal(str, str)
    task_progress = Signal(str, float, str)
    task_log = Signal(str, str)
    task_finished = Signal(str, bool, str, str)
    active_count_changed = Signal(int)

    def __init__(self, max_concurrent: int = 2):
        super().__init__()
        self.max_concurrent = max_concurrent
        self.queue: List[TaskSpec] = []
        self.active_workers: Dict[str, AsyncTaskWorker] = {}
        self.history_specs: Dict[str, TaskSpec] = {}

    def submit_task(self, spec: TaskSpec):
        self.history_specs[spec.task_id] = spec
        self.queue.append(spec)
        self.task_added.emit(spec)
        self._pump_queue()

    def _pump_queue(self):
        while len(self.active_workers) < self.max_concurrent and self.queue:
            spec = self.queue.pop(0)
            worker = AsyncTaskWorker(spec, self)
            worker.task_started.connect(self.task_started.emit)
            worker.task_progress.connect(self.task_progress.emit)
            worker.task_log.connect(self.task_log.emit)
            worker.task_finished.connect(self._on_worker_finished)
            worker.finished.connect(worker.deleteLater)
            self.active_workers[spec.task_id] = worker
            worker.start()
        self.active_count_changed.emit(len(self.active_workers))

    def _on_worker_finished(self, task_id: str, success: bool, msg: str, out_path: str):
        self.active_workers.pop(task_id, None)
        self.task_finished.emit(task_id, success, msg, out_path)
        self._pump_queue()

    def pause_task(self, task_id: str):
        if task_id in self.active_workers:
            self.active_workers[task_id].pause_process()

    def resume_task(self, task_id: str):
        if task_id in self.active_workers:
            self.active_workers[task_id].resume_process()

    def cancel_task(self, task_id: str):
        for i, sp in enumerate(self.queue):
            if sp.task_id == task_id:
                self.queue.pop(i)
                self.task_finished.emit(task_id, False, "Удалено из очереди", sp.output_path)
                return
        if task_id in self.active_workers:
            self.active_workers[task_id].kill_process_tree()