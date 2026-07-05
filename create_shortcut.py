"""创建桌面快捷方式。

运行此脚本可在桌面创建应用快捷方式，双击即可启动。
"""

import os
import sys
import subprocess
from pathlib import Path


def create_shortcut():
    """在桌面创建快捷方式。"""
    try:
        import win32com.client
    except ImportError:
        print("需要 pywin32，正在安装...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pywin32"])
        import win32com.client

    desktop = Path.home() / "Desktop"
    project_dir = Path(__file__).parent.resolve()
    start_script = project_dir / "start.pyw"
    icon_path = project_dir / "assets" / "icon.ico"

    # 使用虚拟环境的 pythonw.exe（无控制台窗口）
    venv_pythonw = project_dir / ".venv" / "Scripts" / "pythonw.exe"
    if venv_pythonw.exists():
        target_exe = str(venv_pythonw)
    else:
        # 回退到当前解释器所在目录的 pythonw
        python_dir = Path(sys.executable).parent
        pythonw = python_dir / "pythonw.exe"
        target_exe = str(pythonw) if pythonw.exists() else str(sys.executable)

    # 创建 .lnk 快捷方式
    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut_path = str(desktop / "B站视频AI总结.lnk")
    shortcut = shell.CreateShortCut(shortcut_path)

    shortcut.TargetPath = target_exe
    shortcut.Arguments = str(start_script)
    shortcut.WorkingDirectory = str(project_dir)
    shortcut.Description = "B站视频AI总结工具"
    shortcut.WindowStyle = 1  # 正常窗口

    if icon_path.exists():
        shortcut.IconLocation = str(icon_path)
    else:
        shortcut.IconLocation = str(sys.executable) + ",0"

    shortcut.Save()
    print(f"✓ 快捷方式已创建: {shortcut_path}")
    print(f"  目标: {target_exe}")
    print(f"  参数: {start_script}")
    print(f"  双击桌面上的「B站视频AI总结」即可启动")


if __name__ == "__main__":
    create_shortcut()
