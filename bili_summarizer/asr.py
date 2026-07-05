"""ASR 语音转写模块（faster-whisper）。

当视频没有CC字幕时，下载音频并用 faster-whisper 进行语音转写。
支持 CUDA GPU 加速和 CPU 回退。
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .subtitle import SubtitleSegment

console = Console()

MODEL_SIZES = {
    "tiny": "~75MB",
    "base": "~150MB",
    "small": "~500MB",
    "medium": "~1.5GB",
    "large-v3": "~3GB",
}


def _check_ffmpeg() -> None:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
    except FileNotFoundError:
        raise RuntimeError(
            "未找到 ffmpeg，ASR 功能需要 ffmpeg。\n"
            "安装方法：\n"
            "  - Windows: choco install ffmpeg 或从 https://ffmpeg.org/download.html 下载\n"
            "  - Mac: brew install ffmpeg\n"
            "  - Linux: sudo apt install ffmpeg"
        )


def _download_audio(bvid: str, output_path: Path, sessdata: str = "") -> Path:
    url = f"https://www.bilibili.com/video/{bvid}"
    try:
        cmd = [
            "yt-dlp", "-x",
            "--audio-format", "wav", "--audio-quality", "0",
            "-o", str(output_path),
            "--no-playlist",
            "--add-header", "Origin:https://www.bilibili.com",
            "--referer", "https://www.bilibili.com",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode == 0 and output_path.exists():
            return output_path
        else:
            console.print(f"[dim]yt-dlp 下载失败: {result.stderr[:200]}[/dim]")
    except FileNotFoundError:
        console.print("[dim]yt-dlp 未安装[/dim]")
    raise RuntimeError("音频下载失败。请安装 yt-dlp：pip install yt-dlp")


def transcribe_audio(
    bvid: str, model_size: str = "base", language: str = "zh",
    device: str = "auto", sessdata: str = "",
) -> list[SubtitleSegment]:
    _check_ffmpeg()
    if device == "auto":
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"
    console.print(f"[dim]ASR 设备: {device}, 模型: {model_size}[/dim]")
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = Path(tmpdir) / "audio.wav"
        console.print("[dim]正在下载音频...[/dim]")
        audio_path = _download_audio(bvid, audio_path, sessdata)
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise RuntimeError(
                "未安装 faster-whisper。\n"
                "  CPU: pip install faster-whisper\n"
                "  GPU: pip install faster-whisper ct2[nvidia]"
            )
        compute_type = "float16" if device == "cuda" else "int8"
        console.print(f"[dim]正在加载模型 (compute_type={compute_type})...[/dim]")
        model = WhisperModel(model_size, device=device, compute_type=compute_type)
        console.print("[dim]正在转写音频...[/dim]")
        segments_iter, info = model.transcribe(
            str(audio_path), language=language, beam_size=5,
            vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500),
        )
        segments = []
        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console,
        ) as progress:
            task = progress.add_task("转写中...", total=None)
            for i, seg in enumerate(segments_iter):
                if seg.text.strip():
                    segments.append(SubtitleSegment(
                        index=i + 1, start_time=seg.start,
                        end_time=seg.end, text=seg.text.strip(),
                    ))
                progress.update(task, description=f"转写中... [{seg.end:.1f}s]")
        console.print(f"[green]✓[/green] ASR 转写完成，共 {len(segments)} 条字幕片段")
        return segments


def transcribe_local_file(
    file_path: str, model_size: str = "base", language: str = "zh",
    device: str = "auto",
) -> list[SubtitleSegment]:
    _check_ffmpeg()
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    if device == "auto":
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError("未安装 faster-whisper。\n  CPU: pip install faster-whisper\n  GPU: pip install faster-whisper ct2[nvidia]")
    compute_type = "float16" if device == "cuda" else "int8"
    console.print(f"[dim]ASR 设备: {device}, 模型: {model_size}, 文件: {path.name}[/dim]")
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    segments_iter, info = model.transcribe(
        str(path), language=language, beam_size=5,
        vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500),
    )
    segments = []
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console,
    ) as progress:
        task = progress.add_task("转写中...", total=None)
        for i, seg in enumerate(segments_iter):
            if seg.text.strip():
                segments.append(SubtitleSegment(
                    index=i + 1, start_time=seg.start,
                    end_time=seg.end, text=seg.text.strip(),
                ))
                progress.update(task, description=f"转写中... [{seg.end:.1f}s]")
    console.print(f"[green]✓[/green] ASR 转写完成，共 {len(segments)} 条字幕片段")
    return segments
