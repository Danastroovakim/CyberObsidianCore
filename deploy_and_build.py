# -*- coding: utf-8 -*-
"""
deploy_and_build.py — Сборщик нативного .EXE v5.1.
Копирует 7z.exe вместе с 7z.dll в ./bin и компилирует CyberObsidianCore.exe с --uac-admin.
"""

import os
import sys
import shutil
import subprocess

REQUIRED_PACKAGES = [
    "PySide6",
    "psutil",
    "pillow",
    "pymupdf",
    "python-docx",
    "pyinstaller",
]


def install_dependencies():
    print("=== [1/5] Проверка и установка зависимостей Python ===")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade"] + REQUIRED_PACKAGES)


def populate_portable_bin(base_dir: str):
    print("=== [2/5] Безопасная комплектация портативной директории ./bin (включая 7z.dll) ===")
    from core_engine import resolve_tool, copy_tool_with_companions

    bin_dir = os.path.join(base_dir, "bin")
    os.makedirs(bin_dir, exist_ok=True)

    portable_keys = ["ffmpeg", "ffprobe", "yt-dlp", "aria2c", "pandoc", "7z"]
    for key in portable_keys:
        found = resolve_tool(key)
        if found and os.path.isfile(found):
            try:
                copy_tool_with_companions(found, bin_dir)
                print(f"  [+] Утилита {key} подготовлена в ./bin")
            except Exception as exc:
                print(f"  [!] Не удалось скопировать {key}: {exc}")


def generate_cyber_icon(ico_path: str):
    print("=== [3/5] Генерация векторной иконки cyber_obsidian.ico ===")
    from PIL import Image, ImageDraw

    size = 256
    img = Image.new("RGBA", (size, size), (5, 6, 10, 255))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle([10, 10, size - 10, size - 10], radius=44, outline=(0, 240, 255, 255), width=8)
    draw.rounded_rectangle([26, 26, size - 26, size - 26], radius=32, outline=(157, 78, 221, 255), width=5)

    diamond = [(size // 2, 44), (size - 44, size // 2), (size // 2, size - 44), (44, size // 2)]
    draw.polygon(diamond, fill=(11, 14, 23, 255), outline=(0, 255, 157, 255))
    inner = [(size // 2, 82), (size - 82, size // 2), (size // 2, size - 82), (82, size // 2)]
    draw.polygon(inner, fill=(0, 240, 255, 255))

    img.save(ico_path, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])


def compile_executable(ico_path: str) -> str:
    print("=== [4/5] Компиляция монолитного .EXE с манифестом Администратора (--uac-admin) ===")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(base_dir, "main.py")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--uac-admin",
        "--name", "CyberObsidianCore",
        "--icon", ico_path,
        main_script,
    ]
    subprocess.check_call(cmd, cwd=base_dir)

    dist_exe = os.path.join(base_dir, "dist", "CyberObsidianCore.exe")
    final_exe = os.path.join(base_dir, "CyberObsidianCore.exe")
    if os.path.isfile(dist_exe):
        shutil.copy2(dist_exe, final_exe)
    print(f"[OK] Скомпилированный исполняемый файл готов: {final_exe}")
    return final_exe


def create_desktop_shortcut(exe_path: str, ico_path: str):
    print("=== [5/5] Обновление ярлыка на Рабочем столе Windows ===")
    if sys.platform != "win32":
        return
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    lnk_path = os.path.join(desktop, "Cyber-Obsidian Core.lnk")
    work_dir = os.path.dirname(exe_path)

    ps_script = (
        f'$ws = New-Object -ComObject WScript.Shell; '
        f'$s = $ws.CreateShortcut("{lnk_path}"); '
        f'$s.TargetPath = "{exe_path}"; '
        f'$s.WorkingDirectory = "{work_dir}"; '
        f'$s.IconLocation = "{ico_path}"; '
        f'$s.Description = "Cyber-Obsidian Media & Document Core v5.1"; '
        f'$s.Save()'
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], check=False)


if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    ico_file = os.path.join(base, "cyber_obsidian.ico")

    install_dependencies()
    populate_portable_bin(base)
    generate_cyber_icon(ico_file)
    built_exe = compile_executable(ico_file)
    create_desktop_shortcut(built_exe, ico_file)
    print("\n======================================================================")
    print(" CYBER-OBSIDIAN CORE v5.1 УСПЕШНО ОБНОВЛЕН И СОБРАН!")
    print("======================================================================")