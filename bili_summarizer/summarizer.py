"""LLM 总结模块。

核心流程：
1. 接收切片后的字幕块
2. 对每个块调用LLM做局部总结（带时间戳）
3. 合并所有局部总结
4. 调用LLM做全局总结
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from openai import OpenAI
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .config import get_config
from .subtitle import SubtitleBlock, VideoInfo, format_timestamp
from .templates import get_template, TemplateType

console = Console()


@dataclass
class ChunkSummary:
    """单个切片的总结。"""
    start_time: float
    end_time: float
    summary: str


@dataclass
class VideoSummary:
    """完整视频总结。"""
    video_info: VideoInfo
    overview: str                       # 一句话概要
    timeline: list[tuple[float, str]]   # [(时间戳, 事件摘要), ...]
    chunk_summaries: list[ChunkSummary] # 各切片详细总结


class LLMSummarizer:
    """LLM 总结器。"""

    def __init__(self) -> None:
        config = get_config()
        self.client = OpenAI(
            api_key=config.llm_api_key,
            base_url=config.llm_base_url,
        )
        self.model = config.llm_model
        self.max_tokens = config.llm_max_tokens
        self.temperature = config.llm_temperature
        self.chunk_size = config.chunk_size
        self.chunk_overlap = config.chunk_overlap

    def summarize(
        self,
        blocks: list[SubtitleBlock],
        video_info: VideoInfo,
        template_type: TemplateType = TemplateType.TUTORIAL,
    ) -> VideoSummary:
        """对视频字幕做完整总结。

        Args:
            blocks: 切片后的字幕块
            video_info: 视频元信息
            template_type: 总结模板类型

        Returns:
            完整视频总结
        """
        template = get_template(template_type)

        # 第一步：逐块总结
        chunk_summaries = self._summarize_chunks(blocks, template)

        # 第二步：全局总结
        overview, timeline = self._global_summarize(chunk_summaries, video_info, template)

        return VideoSummary(
            video_info=video_info,
            overview=overview,
            timeline=timeline,
            chunk_summaries=chunk_summaries,
        )

    def _summarize_chunks(
        self,
        blocks: list[SubtitleBlock],
        template,
    ) -> list[ChunkSummary]:
        """逐块调用LLM做局部总结。"""
        chunk_summaries = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("正在总结各片段...", total=len(blocks))

            for i, block in enumerate(blocks):
                time_label = f"{format_timestamp(block.start_time)} - {format_timestamp(block.end_time)}"
                progress.update(task, description=f"总结片段 [{i+1}/{len(blocks)}] {time_label}")

                prompt = template.chunk_prompt(
                    text=block.text,
                    time_range=time_label,
                )
                response = self._call_llm(prompt)
                chunk_summaries.append(ChunkSummary(
                    start_time=block.start_time,
                    end_time=block.end_time,
                    summary=response,
                ))
                progress.update(task, advance=1)

        console.print(f"[green]✓[/green] 片段总结完成，共 {len(chunk_summaries)} 个")
        return chunk_summaries

    def _global_summarize(
        self,
        chunk_summaries: list[ChunkSummary],
        video_info: VideoInfo,
        template,
    ) -> tuple[str, list[tuple[float, str]]]:
        """全局总结：概要 + 时间线。"""
        # 拼接所有块总结
        all_summaries = ""
        for cs in chunk_summaries:
            time_label = f"{format_timestamp(cs.start_time)} - {format_timestamp(cs.end_time)}"
            all_summaries += f"\n### [{time_label}]\n{cs.summary}\n"

        # 生成概要和时间线
        prompt = template.global_prompt(
            chunk_summaries=all_summaries,
            video_title=video_info.title,
        )
        response = self._call_llm(prompt)

        # 解析结果
        overview, timeline = self._parse_global_response(response, chunk_summaries)
        return overview, timeline

    def _call_llm(self, prompt: str) -> str:
        """调用LLM API。"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的视频内容总结助手。请严格按照要求的格式输出，不要添加多余的解释。"},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            console.print(f"[red]LLM调用失败: {e}[/red]")
            raise

    def _parse_global_response(
        self,
        response: str,
        chunk_summaries: list[ChunkSummary],
    ) -> tuple[str, list[tuple[float, str]]]:
        """解析全局总结响应，提取概要和时间线。

        期望LLM输出格式：
        ## 概要
        一句话总结...

        ## 时间线
        - [mm:ss] 事件描述
        - [mm:ss] 事件描述
        ...
        """
        overview = ""
        timeline: list[tuple[float, str]] = []

        lines = response.split("\n")
        current_section = ""
        overview_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("## 概要") or stripped.startswith("##概述"):
                current_section = "overview"
                continue
            elif stripped.startswith("## 时间线") or stripped.startswith("##时间线"):
                current_section = "timeline"
                continue
            elif stripped.startswith("## "):
                current_section = ""
                continue

            if current_section == "overview" and stripped:
                overview_lines.append(stripped)
            elif current_section == "timeline" and stripped:
                # 解析时间线条目: - [mm:ss] 描述
                time_match = __import__("re").match(
                    r"[-*]\s*\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.+)", stripped
                )
                if time_match:
                    time_str, event = time_match.groups()
                    seconds = self._parse_time_str(time_str)
                    timeline.append((seconds, event.strip()))

        overview = " ".join(overview_lines) if overview_lines else response[:200]

        # 如果LLM没有返回时间线，从chunk_summaries自动生成
        if not timeline:
            for cs in chunk_summaries:
                first_line = cs.summary.split("\n")[0][:80]
                timeline.append((cs.start_time, first_line))

        return overview, timeline

    @staticmethod
    def _parse_time_str(time_str: str) -> float:
        """解析 mm:ss 或 hh:mm:ss 为秒数。"""
        parts = time_str.split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        return 0.0
