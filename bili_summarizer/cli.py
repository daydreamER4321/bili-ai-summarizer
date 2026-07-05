"""CLI 入口：bili-summarize 命令行工具。"""

from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.panel import Panel

from .config import Config, get_config, reset_config
from .subtitle import (
    SubtitlePreprocessor,
    chunk_subtitles,
    fetch_subtitles,
    format_timestamp,
)
from .summarizer import LLMSummarizer
from .output import MarkdownFormatter
from .templates import TemplateType

console = Console()


def _resolve_template_type(template_str: str) -> TemplateType:
    """将字符串映射为 TemplateType。"""
    mapping = {
        "tutorial": TemplateType.TUTORIAL,
        "narrative": TemplateType.NARRATIVE,
        "entity": TemplateType.ENTITY,
        "timeline": TemplateType.TIMELINE,
        "critique": TemplateType.CRITIQUE,
        "compare": TemplateType.COMPARE,
        # 别名
        "tech": TemplateType.TUTORIAL,
        "story": TemplateType.NARRATIVE,
        "extract": TemplateType.ENTITY,
        "entities": TemplateType.ENTITY,
        "事件": TemplateType.TIMELINE,
        "批判": TemplateType.CRITIQUE,
        "对比": TemplateType.COMPARE,
    }
    key = template_str.lower().strip()
    if key not in mapping:
        console.print(f"[yellow]未知模板类型 '{template_str}'，使用默认 'tutorial'[/yellow]")
        return TemplateType.TUTORIAL
    return mapping[key]


@click.command()
@click.argument("url", required=True)
@click.option(
    "-t", "--type", "template_type",
    default="tutorial",
    help="总结模板类型: tutorial(教程), narrative(剧情), entity(实体提取), timeline(时间线), critique(观点批判), compare(多视频对比)",
)
@click.option(
    "-o", "--output-dir",
    default=None,
    help="输出目录（默认: ./output）",
)
@click.option(
    "--model",
    default=None,
    help="LLM 模型名称（覆盖环境变量）",
)
@click.option(
    "--chunk-size",
    default=3000,
    type=int,
    help="每个文本块的字符数（默认: 3000）",
)
@click.option(
    "--browser",
    default="auto",
    help="Cookie读取的浏览器: auto/chrome/edge/firefox/brave/arc",
)
@click.option(
    "--no-asr",
    is_flag=True,
    help="禁用ASR兜底（仅使用CC字幕）",
)
@click.option(
    "--asr-model",
    default="base",
    help="ASR模型大小: tiny/base/small/medium/large-v3（默认: base）",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="仅获取和预处理字幕，不调用LLM",
)
def main(
    url: str,
    template_type: str,
    output_dir: str | None,
    model: str | None,
    chunk_size: int,
    browser: str,
    no_asr: bool,
    asr_model: str,
    dry_run: bool,
) -> None:
    """B站视频AI总结工具。

    URL 可以是B站视频链接或BV号。

    模板类型：
      tutorial  - 教程/技术类（默认）
      narrative - 剧情/解说类
      entity    - 实体提取（人名/书名/工具/URL）
      timeline  - 时间线梳理（历史/事件脉络）
      critique  - 观点批判（逻辑分析/偏见检测）
      compare   - 多视频对比（需多个BV号，用逗号分隔）

    示例：

    \b
      bili-summarize BV16YC3BrEDz
      bili-summarize BV16YC3BrEDz -t narrative
      bili-summarize BV16YC3BrEDz -t entity
      bili-summarize BV16YC3BrEDz -t critique
      bili-summarize BV16YC3BrEDz,BV1WVfcYFEiX -t compare
      bili-summarize BV16YC3BrEDz --dry-run
    """
    console.print(Panel(
        "[bold]B站视频AI总结工具[/bold] v0.4.0",
        style="blue",
    ))

    # ─── 配置 ───
    reset_config()
    config = Config()
    if output_dir:
        from pathlib import Path
        config.output_dir = Path(output_dir)
    if model:
        config.llm_model = model
    config.chunk_size = chunk_size
    config.validate()

    # 替换全局配置
    from . import config as config_mod
    config_mod._config = config

    resolved_type = _resolve_template_type(template_type)

    # ─── 多视频对比模式 ───
    if resolved_type == TemplateType.COMPARE:
        bvids = [u.strip() for u in url.split(",") if u.strip()]
        if len(bvids) < 2:
            console.print("[red]对比模式需要至少2个BV号，用逗号分隔[/red]")
            sys.exit(1)
        _run_compare(bvids, config, browser, no_asr, asr_model)
        return

    # ─── 单视频模式 ───
    try:
        # ─── Step 1: 获取字幕 ───
        console.print("\n[bold cyan]Step 1/4[/bold cyan] 获取字幕...")
        segments, video_info = fetch_subtitles(
            url,
            browser=browser,
            use_asr=not no_asr,
            asr_model=asr_model,
        )
        console.print(f"  视频标题: [bold]{video_info.title}[/bold]")
        console.print(f"  字幕片段: {len(segments)} 条")

        # ─── Step 2: 预处理 ───
        console.print("\n[bold cyan]Step 2/4[/bold cyan] 预处理字幕...")
        preprocessor = SubtitlePreprocessor()
        segments = preprocessor.process(segments)

        # ─── Step 3: 切片 ───
        console.print("\n[bold cyan]Step 3/4[/bold cyan] 切片...")
        blocks = chunk_subtitles(
            segments,
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
        )

        if dry_run:
            console.print("\n[yellow]--dry-run 模式，跳过LLM总结[/yellow]")
            for i, block in enumerate(blocks):
                time_label = f"{format_timestamp(block.start_time)} - {format_timestamp(block.end_time)}"
                console.print(f"\n  Block {i+1} [{time_label}] ({len(block.text)} chars):")
                console.print(f"  {block.text[:100]}...")
            return

        # ─── Step 4: LLM 总结 ───
        console.print("\n[bold cyan]Step 4/4[/bold cyan] LLM 总结...")
        summarizer = LLMSummarizer()
        summary = summarizer.summarize(blocks, video_info, resolved_type)

        # ─── 输出 ───
        console.print("\n[bold cyan]生成 Markdown...[/bold cyan]")
        formatter = MarkdownFormatter()
        output_path = formatter.save(summary, template_type)

        console.print(Panel(
            f"[bold green]✓ 完成！[/bold green]\n\n"
            f"视频: {video_info.title}\n"
            f"概要: {summary.overview[:80]}...\n"
            f"时间线: {len(summary.timeline)} 个节点\n"
            f"输出: {output_path}",
            title="总结结果",
        ))

    except RuntimeError as e:
        console.print(f"\n[bold red]错误:[/bold red] {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]已取消[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[bold red]未预期的错误:[/bold red] {e}")
        raise


def _run_compare(
    bvids: list[str],
    config: Config,
    browser: str,
    no_asr: bool,
    asr_model: str,
) -> None:
    """多视频对比模式。"""
    from .templates.compare import CompareTemplate

    console.print(f"[bold cyan]多视频对比模式[/bold cyan]，共 {len(bvids)} 个视频")

    # 逐个处理每个视频
    video_summaries = []
    summarizer = LLMSummarizer()
    formatter = MarkdownFormatter()

    for idx, bvid in enumerate(bvids, 1):
        console.print(f"\n[bold]--- 视频 {idx}/{len(bvids)}: {bvid} ---[/bold]")
        try:
            segments, video_info = fetch_subtitles(
                bvid, browser=browser, use_asr=not no_asr, asr_model=asr_model,
            )
            preprocessor = SubtitlePreprocessor()
            segments = preprocessor.process(segments)
            blocks = chunk_subtitles(
                segments, chunk_size=config.chunk_size, chunk_overlap=config.chunk_overlap,
            )
            summary = summarizer.summarize(blocks, video_info, TemplateType.COMPARE)

            # 单独保存每个视频的总结
            formatter.save(summary, f"compare_{idx}")

            video_summaries.append({
                "title": video_info.title,
                "summary": formatter.format(summary, "compare"),
            })
            console.print(f"[green]✓[/green] 视频 {idx} 处理完成")
        except Exception as e:
            console.print(f"[red]✗[/red] 视频 {idx} ({bvid}) 处理失败: {e}")
            video_summaries.append({
                "title": bvid,
                "summary": f"处理失败: {e}",
            })

    if len(video_summaries) < 2:
        console.print("[red]至少需要2个视频成功处理才能进行对比[/red]")
        sys.exit(1)

    # 生成对比分析
    console.print("\n[bold cyan]生成对比分析...[/bold cyan]")
    compare_template = CompareTemplate()
    compare_prompt = compare_template.compare_prompt(video_summaries)

    from openai import OpenAI
    client = OpenAI(api_key=config.llm_api_key, base_url=config.llm_base_url)
    response = client.chat.completions.create(
        model=config.llm_model,
        messages=[
            {"role": "system", "content": "你是一个专业的信息对比分析助手。请严格按照要求的格式输出对比分析。"},
            {"role": "user", "content": compare_prompt},
        ],
        max_tokens=config.llm_max_tokens,
        temperature=0.3,
    )
    compare_result = response.choices[0].message.content.strip()

    # 保存对比结果
    from pathlib import Path
    from datetime import datetime

    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"compare_{now}.md"

    header = f"# 多视频对比分析\n\n"
    header += "> " + " | ".join(v["title"] for v in video_summaries) + "\n"
    header += f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"

    output_path.write_text(header + compare_result, encoding="utf-8")
    console.print(Panel(
        f"[bold green]✓ 对比完成！[/bold green]\n\n"
        f"对比视频: {len(video_summaries)} 个\n"
        f"输出: {output_path}",
        title="对比结果",
    ))


if __name__ == "__main__":
    main()
