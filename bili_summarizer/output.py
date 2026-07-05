"""Markdown 输出格式化模块。

将 VideoSummary 渲染为带时间戳的结构化 Markdown 文档。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rich.console import Console

from .config import get_config
from .subtitle import format_timestamp
from .summarizer import VideoSummary

console = Console()


class MarkdownFormatter:
    """Markdown 格式化器。"""

    def format(self, summary: VideoSummary, template_type: str = "tutorial") -> str:
        """将视频总结格式化为 Markdown。

        Args:
            summary: 视频总结数据
            template_type: 使用的模板类型

        Returns:
            格式化后的 Markdown 文本
        """
        info = summary.video_info
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        parts = []

        # ─── 标题 ───
        title = info.title or f"B站视频 {info.bvid}"
        parts.append(f"# {title}")
        parts.append("")

        # ─── 元信息 ───
        meta_items = []
        if info.up_name:
            meta_items.append(f"UP主: {info.up_name}")
        meta_items.append(f"生成时间: {now}")
        meta_items.append(f"总结模式: {template_type}")
        if info.bvid:
            meta_items.append(f"BV号: {info.bvid}")
        parts.append("> " + " | ".join(meta_items))
        parts.append("")

        # ─── 概要 ───
        parts.append("## 📋 概要")
        parts.append("")
        parts.append(summary.overview)
        parts.append("")

        # ─── 时间线 ───
        parts.append("## ⏱ 时间线")
        parts.append("")
        for timestamp, event in summary.timeline:
            parts.append(f"- **[{format_timestamp(timestamp)}]** {event}")
        parts.append("")

        # ─── 详细总结 ───
        parts.append("## 📝 详细总结")
        parts.append("")
        for cs in summary.chunk_summaries:
            time_label = f"{format_timestamp(cs.start_time)} - {format_timestamp(cs.end_time)}"
            parts.append(f"### [{time_label}]")
            parts.append("")
            parts.append(cs.summary)
            parts.append("")

        # ─── 页脚 ───
        parts.append("---")
        parts.append(f"*由 bili-ai-summarizer 自动生成 · {now}*")

        return "\n".join(parts)

    def save(self, summary: VideoSummary, template_type: str = "tutorial") -> Path:
        """格式化并保存到文件。

        Args:
            summary: 视频总结数据
            template_type: 模板类型

        Returns:
            保存的文件路径
        """
        config = get_config()
        content = self.format(summary, template_type)

        # 文件名：BV号_标题摘要.md
        bvid = summary.video_info.bvid or "unknown"
        # 清理标题中的文件系统不安全字符
        title_slug = summary.video_info.title[:30] if summary.video_info.title else ""
        for ch in ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '\n', '\r']:
            title_slug = title_slug.replace(ch, '_')
        filename = f"{title_slug}_{bvid}.md" if title_slug else f"{bvid}.md"

        output_path = config.output_dir / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")

        console.print(f"[green]✓[/green] 已保存到: {output_path}")
        return output_path
