"""B站视频AI总结 — 桌面应用启动器。

双击此文件即可启动应用，无需打开命令行。
使用 pywebview 将 Streamlit 包在原生窗口中。
"""

from __future__ import annotations

import os
import sys
import time
import threading
import subprocess
import webbrowser
from pathlib import Path

# ─── 配置 ────────────────────────────────────────────────────
APP_NAME = "B站视频AI总结"
STREAMLIT_PORT = 8765
STREAMLIT_SCRIPT = Path(__file__).parent / "app.py"

def _find_python() -> str:
    """找到当前 Python 解释器。"""
    return sys.executable


def _start_streamlit() -> subprocess.Popen:
    """在后台启动 Streamlit 服务器。"""
    python = _find_python()
    
    # Windows 下隐藏控制台窗口
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = (
            subprocess.CREATE_NO_WINDOW
            | subprocess.DETACHED_PROCESS
        )

    proc = subprocess.Popen(
        [
            python, "-m", "streamlit", "run",
            str(STREAMLIT_SCRIPT),
            "--server.port", str(STREAMLIT_PORT),
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
            "--server.fileWatcherType", "none",
            "--theme.primaryColor", "#00b4d8",
            "--theme.backgroundColor", "#0d1117",
            "--theme.secondaryBackgroundColor", "#161b22",
            "--theme.textColor", "#c9d1d9",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **kwargs,
    )
    return proc


def _wait_for_server(url: str, timeout: int = 30) -> bool:
    """等待 Streamlit 服务器就绪。"""
    import urllib.request
    import urllib.error

    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(url, method="HEAD")
            urllib.request.urlopen(req, timeout=2)
            return True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.5)
    return False


def _open_native_window(url: str) -> None:
    """使用 pywebview 打开原生窗口。"""
    try:
        import webview
    except ImportError:
        # pywebview 未安装，回退到浏览器
        print(f"pywebview 未安装，使用浏览器打开: {url}")
        print("安装原生窗口支持: pip install pywebview")
        webbrowser.open(url)
        return

    # 窗口图标
    icon_path = Path(__file__).parent / "assets" / "icon.ico"
    icon = str(icon_path) if icon_path.exists() else None

    class Api:
        """JS ↔ Python 桥接（预留）。"""
        def quit(self):
            window.destroy()

    api = Api()
    window = webview.create_window(
        title=APP_NAME,
        url=url,
        width=1280,
        height=860,
        min_size=(900, 600),
        resizable=True,
        icon=icon,
        js_api=api,
    )

    # 关闭窗口时结束 Streamlit 进程
    _streamlit_proc = getattr(_open_native_window, '_proc', None)
    
    def on_closing():
        if _streamlit_proc:
            _streamlit_proc.terminate()
        os._exit(0)

    window.events.closing += on_closing
    _open_native_window._window = window

    webview.start(debug=False)


def main():
    """主入口。"""
    url = f"http://localhost:{STREAMLIT_PORT}"

    # 启动 Streamlit
    print(f"正在启动 {APP_NAME}...")
    proc = _start_streamlit()
    _open_native_window._proc = proc

    # 等待服务器就绪
    print("等待服务器就绪...")
    if not _wait_for_server(url, timeout=30):
        print("服务器启动超时，尝试用浏览器打开...")
        webbrowser.open(url)
        # 仍然保持运行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            proc.terminate()
        return

    print(f"服务器已就绪: {url}")
    print("正在打开应用窗口...")

    # 打开原生窗口（此调用会阻塞直到窗口关闭）
    _open_native_window(url)


if __name__ == "__main__":
    main()
