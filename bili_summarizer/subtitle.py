"""B站字幕获取模块。

直接调用B站字幕API，不依赖 video-captions 包（该包的 mlx-whisper 依赖仅支持 Apple Silicon）。
支持：
1. 从B站API获取CC字幕（JSON格式，带时间戳）
2. 自动从浏览器读取Cookie（需浏览器_cookie3）
3. 环境变量 Cookie 备选
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

import httpx
from rich.console import Console

from .config import get_config

console = Console()


@dataclass
class SubtitleSegment:
    """单条字幕片段。"""
    index: int
    start_time: float       # 秒
    end_time: float         # 秒
    text: str


@dataclass
class SubtitleBlock:
    """切片后的字幕块（对应一个时间段落）。"""
    start_time: float
    end_time: float
    text: str
    segments: list[SubtitleSegment]


@dataclass
class VideoInfo:
    """视频元信息。"""
    bvid: str
    title: str
    duration: float = 0.0
    up_name: str = ""


# ─── 工具函数 ────────────────────────────────────────────────

def format_timestamp(seconds: float) -> str:
    """将秒数格式化为 [mm:ss] 时间戳。"""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _extract_bvid(url: str) -> str:
    """从URL或纯BV号中提取BV号。"""
    bv_match = re.search(r"BV[\w]+", url)
    if bv_match:
        return bv_match.group()
    return url.strip()


# ─── Cookie 获取 ────────────────────────────────────────────────

def _get_sessdata() -> str:
    """获取B站SESSDATA，优先环境变量，其次尝试读取浏览器Cookie。"""
    import os

    # 1. 环境变量
    sessdata = os.getenv("BILIBILI_SESSDATA", "").strip()
    if sessdata:
        return sessdata

    # 2. 尝试读取浏览器Cookie
    try:
        import browser_cookie3
        for cookie_fn in [
            browser_cookie3.chrome,
            browser_cookie3.edge,
            browser_cookie3.firefox,
            browser_cookie3.brave,
        ]:
            try:
                jar = cookie_fn(domain_name=".bilibili.com")
                for cookie in jar:
                    if cookie.name == "SESSDATA":
                        console.print(f"[dim]从浏览器读取到 SESSDATA[/dim]")
                        return cookie.value
            except Exception:
                continue
    except ImportError:
        console.print("[dim]browser-cookie3 未安装，跳过浏览器Cookie读取[/dim]")

    console.print("[yellow]未获取到 SESSDATA，部分视频可能无法获取字幕[/yellow]")
    return ""


# ─── B站 API 调用 ────────────────────────────────────────────────

_BILIBILI_API = "https://api.bilibili.com"

# 伪装浏览器请求头，避免被B站反爬机制拦截（412 Precondition Failed）
# 关键：Origin 头是 2026 年 B 端新增的必检项，缺它必触发 412
# 参考：yt-dlp 社区确认 --add-header "Origin:https://www.bilibili.com" 可解 412
_BILIBILI_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com",
    "Origin": "https://www.bilibili.com",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def _get_video_info(bvid: str, sessdata: str) -> dict:
    """获取视频信息（标题、分P等）。"""
    params = {"bvid": bvid}
    cookies = {"SESSDATA": sessdata} if sessdata else {}

    with httpx.Client(timeout=15, headers=_BILIBILI_HEADERS) as client:
        resp = client.get(f"{_BILIBILI_API}/x/web-interface/view", params=params, cookies=cookies)
        resp.raise_for_status()
        data = resp.json()

    if data["code"] != 0:
        raise RuntimeError(f"获取视频信息失败: {data.get('message', '未知错误')}")

    return data["data"]


def _get_subtitle_urls(bvid: str, cid: int, sessdata: str) -> list[dict]:
    """获取字幕列表URL。"""
    params = {"bvid": bvid, "cid": cid}
    cookies = {"SESSDATA": sessdata} if sessdata else {}

    with httpx.Client(timeout=15, headers=_BILIBILI_HEADERS) as client:
        resp = client.get(f"{_BILIBILI_API}/x/player/wbi/v2", params=params, cookies=cookies)
        resp.raise_for_status()
        data = resp.json()

    if data["code"] != 0:
        raise RuntimeError(f"获取字幕信息失败: {data.get('message', '未知错误')}")

    subtitles = data.get("data", {}).get("subtitle", {}).get("subtitles", [])
    return subtitles


def _download_subtitle(subtitle_url: str) -> list[dict]:
    """下载字幕JSON内容。"""
    if not subtitle_url.startswith("http"):
        subtitle_url = "https:" + subtitle_url

    with httpx.Client(timeout=15, headers=_BILIBILI_HEADERS) as client:
        resp = client.get(subtitle_url)
        resp.raise_for_status()
        data = resp.json()

    return data.get("body", [])


def fetch_subtitles(
    url: str,
    browser: str = "auto",
    use_asr: bool = True,
    asr_model: str = "base",
) -> tuple[list[SubtitleSegment], VideoInfo]:
    """获取B站视频字幕。

    Args:
        url: B站视频URL或BV号
        browser: 未使用，保留兼容
        use_asr: CC字幕获取失败时是否回退到ASR
        asr_model: ASR模型大小

    Returns:
        (字幕片段列表, 视频信息)

    Raises:
        RuntimeError: 字幕获取失败
    """
    bvid = _extract_bvid(url)
    sessdata = _get_sessdata()

    console.print(f"[dim]正在获取视频信息: {bvid}[/dim]")

    # 1. 获取视频信息
    video_data = _get_video_info(bvid, sessdata)
    title = video_data.get("title", "")
    duration = video_data.get("duration", 0)
    up_name = video_data.get("owner", {}).get("name", "")
    cid = video_data.get("cid", 0)

    video_info = VideoInfo(bvid=bvid, title=title, duration=duration, up_name=up_name)

    # 2. 获取字幕URL列表
    subtitle_list = _get_subtitle_urls(bvid, cid, sessdata)

    if not subtitle_list:
        # 尝试所有分P
        pages = video_data.get("pages", [])
        if len(pages) > 1:
            console.print(f"[dim]视频有 {len(pages)} 个分P，正在逐P获取字幕...[/dim]")
            all_segments = []
            for page in pages:
                page_cid = page.get("cid", 0)
                page_subtitles = _get_subtitle_urls(bvid, page_cid, sessdata)
                for sub in page_subtitles:
                    raw = _download_subtitle(sub.get("subtitle_url", ""))
                    for item in raw:
                        start = item.get("from", 0)
                        end = item.get("to", 0)
                        text = item.get("content", "").strip()
                        if text:
                            all_segments.append(SubtitleSegment(
                                index=len(all_segments) + 1,
                                start_time=start,
                                end_time=end,
                                text=text,
                            ))
            if all_segments:
                console.print(f"[green]✓[/green] 获取到 {len(all_segments)} 条字幕片段（多P合并）")
                return all_segments, video_info

        # CC字幕获取失败，尝试ASR兜底
        if use_asr:
            console.print("[yellow]该视频没有CC字幕，尝试ASR语音转写...[/yellow]")
            try:
                from .asr import transcribe_audio
                config = get_config()
                segments = transcribe_audio(
                    bvid=bvid,
                    model_size=asr_model,
                    device=config.asr_device,
                    sessdata=sessdata,
                )
                if segments:
                    return segments, video_info
            except Exception as e:
                raise RuntimeError(
                    f"CC字幕和ASR均失败。\n"
                    f"CC字幕: 无\n"
                    f"ASR错误: {e}\n\n"
                    f"解决方法：\n"
                    f"  - 确认已安装: pip install bili-ai-summarizer[asr]\n"
                    f"  - 确认已安装 ffmpeg\n"
                    f"  - 使用 --no-asr 跳过ASR"
                )

        raise RuntimeError(
            f"该视频没有CC字幕。\n"
            f"可能原因：\n"
            f"  1. UP主未上传字幕\n"
            f"  2. Cookie未配置，无法访问会员字幕\n"
            f"  3. 平台AI字幕暂未生成\n\n"
            f"解决方法：\n"
            f"  - 在浏览器登录B站后重试（自动读取Cookie）\n"
            f"  - 设置环境变量: set BILIBILI_SESSDATA=你的值\n"
            f"  - pip install browser-cookie3 后重试\n"
            f"  - 安装ASR依赖: pip install bili-ai-summarizer[asr]"
        )

    # 3. 下载首选字幕（优先中文字幕）
    # 按语言排序：中文优先
    subtitle_list.sort(key=lambda s: 0 if "zh" in s.get("lan", "") else 1)
    chosen = subtitle_list[0]

    console.print(f"[dim]下载字幕: {chosen.get('lan', 'unknown')}[/dim]")
    raw_subtitle = _download_subtitle(chosen.get("subtitle_url", ""))

    # 4. 解析为 SubtitleSegment
    segments = []
    for i, item in enumerate(raw_subtitle):
        start = item.get("from", 0)
        end = item.get("to", 0)
        text = item.get("content", "").strip()
        if text:
            segments.append(SubtitleSegment(
                index=i + 1,
                start_time=start,
                end_time=end,
                text=text,
            ))

    if not segments:
        raise RuntimeError("字幕内容为空")

    console.print(f"[green]✓[/green] 获取到 {len(segments)} 条字幕片段")
    return segments, video_info


# ─── SRT 解析（备用，用于本地SRT文件） ─────────────────────────────

def parse_srt(srt_text: str) -> list[SubtitleSegment]:
    """解析SRT格式字幕，返回带时间戳的字幕片段列表。"""
    segments = []
    blocks = re.split(r"\n\s*\n", srt_text.strip())
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 2:
            continue
        try:
            index = int(lines[0].strip())
        except ValueError:
            continue

        time_match = re.match(
            r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})",
            lines[1].strip(),
        )
        if not time_match:
            continue

        g = time_match.groups()
        start_time = int(g[0]) * 3600 + int(g[1]) * 60 + int(g[2]) + int(g[3]) / 1000
        end_time = int(g[4]) * 3600 + int(g[5]) * 60 + int(g[6]) + int(g[7]) / 1000

        text = " ".join(line.strip() for line in lines[2:])
        segments.append(SubtitleSegment(index=index, start_time=start_time, end_time=end_time, text=text))

    return segments


# ─── 字幕预处理 ────────────────────────────────────────────────

class SubtitlePreprocessor:
    """字幕预处理器：合并碎片、去杂质、说话人识别。"""

    def __init__(self) -> None:
        self.config = get_config()
        self._noise_re = [re.compile(p) for p in self.config.noise_patterns]

    def process(self, segments: list[SubtitleSegment]) -> list[SubtitleSegment]:
        """执行完整的预处理管线。"""
        if not segments:
            return segments

        segments = self._remove_noise(segments)
        segments = self._merge_fragments(segments)
        segments = self._remove_duplicates(segments)
        segments = self._fix_timestamps(segments)

        console.print(f"[green]✓[/green] 预处理完成，剩余 {len(segments)} 条字幕")
        return segments

    def _remove_noise(self, segments: list[SubtitleSegment]) -> list[SubtitleSegment]:
        """去除杂质标记。"""
        cleaned = []
        for seg in segments:
            text = seg.text
            for pattern in self._noise_re:
                text = pattern.sub("", text)
            text = text.strip()
            if text:
                cleaned.append(SubtitleSegment(
                    index=seg.index, start_time=seg.start_time,
                    end_time=seg.end_time, text=text,
                ))
        return cleaned

    def _merge_fragments(self, segments: list[SubtitleSegment]) -> list[SubtitleSegment]:
        """合并过短的碎片句。"""
        if len(segments) <= 1:
            return segments

        merged = [segments[0]]
        for seg in segments[1:]:
            prev = merged[-1]
            if len(seg.text) < self.config.min_sentence_length and seg.start_time - prev.end_time < 2.0:
                merged[-1] = SubtitleSegment(
                    index=prev.index,
                    start_time=prev.start_time,
                    end_time=seg.end_time,
                    text=prev.text + seg.text,
                )
            else:
                merged.append(seg)
        return merged

    def _remove_duplicates(self, segments: list[SubtitleSegment]) -> list[SubtitleSegment]:
        """去除连续重复字幕。"""
        if len(segments) <= 1:
            return segments
        cleaned = [segments[0]]
        for seg in segments[1:]:
            if seg.text != cleaned[-1].text:
                cleaned.append(seg)
        return cleaned

    def _fix_timestamps(self, segments: list[SubtitleSegment]) -> list[SubtitleSegment]:
        """修正时间戳。"""
        fixed = []
        last_end = 0.0
        for seg in segments:
            start = max(seg.start_time, last_end)
            end = max(seg.end_time, start + 0.1)
            fixed.append(SubtitleSegment(
                index=seg.index, start_time=start, end_time=end, text=seg.text,
            ))
            last_end = end
        return fixed


# ─── 字幕切片 ────────────────────────────────────────────────

def chunk_subtitles(
    segments: list[SubtitleSegment],
    chunk_size: int = 3000,
    chunk_overlap: int = 500,
) -> list[SubtitleBlock]:
    """将字幕按字符数切片，每片带时间范围。"""
    if not segments:
        return []

    full_text = ""
    char_timestamps: list[float] = []
    for seg in segments:
        for char in seg.text:
            char_timestamps.append(seg.start_time)
        full_text += seg.text
        if seg.text:
            full_text += " "
            char_timestamps.append(seg.end_time)

    full_text = full_text.strip()
    if len(full_text) <= chunk_size:
        return [SubtitleBlock(
            start_time=segments[0].start_time,
            end_time=segments[-1].end_time,
            text=full_text,
            segments=segments,
        )]

    blocks = []
    start = 0
    while start < len(full_text):
        end = min(start + chunk_size, len(full_text))
        chunk_text = full_text[start:end].strip()
        if not chunk_text:
            break

        block_start = char_timestamps[start] if start < len(char_timestamps) else 0.0
        last_char_idx = min(end - 1, len(char_timestamps) - 1)
        block_end = char_timestamps[last_char_idx] if last_char_idx >= 0 else 0.0

        blocks.append(SubtitleBlock(
            start_time=block_start,
            end_time=block_end,
            text=chunk_text,
            segments=[],
        ))

        next_start = start + chunk_size - chunk_overlap
        if next_start <= start:
            next_start = start + chunk_size
        start = next_start

    console.print(f"[green]✓[/green] 切片完成，共 {len(blocks)} 个文本块")
    return blocks
