"""B站视频AI总结工具 — Streamlit GUI。

启动方式：streamlit run app.py
"""

from __future__ import annotations

import sys
import os
import re
from pathlib import Path
from datetime import datetime

import streamlit as st

# ─── 项目根目录加入 sys.path ─────────────────────────────────
_APP_DIR = Path(__file__).parent
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from bili_summarizer.config import Config, reset_config
from bili_summarizer.subtitle import (
    SubtitlePreprocessor,
    chunk_subtitles,
    fetch_subtitles,
    format_timestamp,
)
from bili_summarizer.summarizer import LLMSummarizer
from bili_summarizer.output import MarkdownFormatter
from bili_summarizer.templates import TemplateType, get_template

# ─── 页面配置 ────────────────────────────────────────────────
st.set_page_config(
    page_title="B站视频AI总结",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── 模板选项 ────────────────────────────────────────────────
TEMPLATE_OPTIONS = {
    "教程/技术 (tutorial)": TemplateType.TUTORIAL,
    "剧情/解说 (narrative)": TemplateType.NARRATIVE,
    "实体提取 (entity)": TemplateType.ENTITY,
    "时间线梳理 (timeline)": TemplateType.TIMELINE,
    "观点批判 (critique)": TemplateType.CRITIQUE,
    "多视频对比 (compare)": TemplateType.COMPARE,
}

TEMPLATE_DESCRIPTIONS = {
    TemplateType.TUTORIAL: "适合编程教程、技术讲解视频，提取操作步骤和关键概念",
    TemplateType.NARRATIVE: "适合剧情解说、游戏攻略视频，提取情节和人物动态",
    TemplateType.ENTITY: "提取视频中提到的人名、书名、工具、URL、数据等实体信息",
    TemplateType.TIMELINE: "重建历史/事件类视频的时间线和因果链",
    TemplateType.CRITIQUE: "批判性分析视频中的观点、逻辑、论证强度和偏见",
    TemplateType.COMPARE: "对同一主题的多个视频进行交叉对比分析",
}

# ─── 模式选择示例 ────────────────────────────────────────────
TEMPLATE_EXAMPLES = {
    TemplateType.TUTORIAL: (
        "📺 **典型视频**：Python爬虫教程、VSCode配置指南、机器学习入门课\n\n"
        "📝 **输出样例**：\n"
        "> **步骤1** 安装依赖：`pip install httpx openai`\n"
        "> **步骤2** 配置API Key到 `.env` 文件\n"
        "> **要点** B站字幕API需要SESSDATA Cookie认证"
    ),
    TemplateType.NARRATIVE: (
        "📺 **典型视频**：明日方舟剧情解析、电影解说、游戏通关攻略\n\n"
        "📝 **输出样例**：\n"
        "> **情节概要**：阿米娅带领罗德岛深入切尔诺伯格...\n"
        "> **人物动态**：塔露拉从理想主义者逐渐被黑蛇操控\n"
        "> **伏笔**：W的身份暗示在第三章已埋下"
    ),
    TemplateType.ENTITY: (
        "📺 **典型视频**：读书分享、行业分析、工具推荐合集\n\n"
        "📝 **输出样例**：\n"
        "> **人名**：安德烈·卡帕西、杰弗里·辛顿\n"
        "> **工具**：Ollama、LM Studio、vLLM\n"
        "> **数据**：GPT-4参数量1.8万亿、训练成本约1亿美元\n"
        "> **URL**：https://github.com/..."
    ),
    TemplateType.TIMELINE: (
        "📺 **典型视频**：历史事件梳理、公司发展史、技术演进路线\n\n"
        "📝 **输出样例**：\n"
        "> **[2017]** Transformer论文发表，Attention机制诞生\n"
        "> **[2018]** BERT出现，预训练+微调范式确立\n"
        "> **[2020]** GPT-3发布，In-context Learning成为可能\n"
        "> **因果链**：算力增长 → 模型规模扩大 → 涌现能力出现"
    ),
    TemplateType.CRITIQUE: (
        "📺 **典型视频**：社会热点评论、科技趋势预测、投资观点分析\n\n"
        "📝 **输出样例**：\n"
        "> **核心论点**：AI将在5年内取代80%的白领工作\n"
        "> **逻辑谬误**：滑坡谬误——从「部分岗位被替代」直接跳到「80%失业」\n"
        "> **未提及的反例**：历次技术革命中，新岗位创造速度超过旧岗位消失速度\n"
        "> **论证强度**：3/10，依赖单一数据源且忽略反面证据"
    ),
    TemplateType.COMPARE: (
        "📺 **典型场景**：对比3个「Python入门教程」视频、对比不同UP主对同一事件的解读\n\n"
        "📝 **输出样例**：\n"
        "> **共识**：3个视频都认为Transformer是当前最重要的架构\n"
        "> **分歧**：A认为RLHF是关键突破，B强调Scaling Law，C认为是数据质量\n"
        "> **互补**：A提供了代码实现，B提供了理论推导，C提供了行业应用案例"
    ),
}


# ─── 辅助函数 ────────────────────────────────────────────────

def extract_bvid(text: str) -> list[str]:
    """从输入文本中提取所有BV号。"""
    return re.findall(r"BV[\w]+", text)


def init_config(**overrides) -> Config:
    """初始化配置。"""
    reset_config()
    config = Config()
    for k, v in overrides.items():
        if v is not None and hasattr(config, k):
            setattr(config, k, v)
    config.validate()
    # 替换全局配置
    from bili_summarizer import config as config_mod
    config_mod._config = config
    return config


def process_single_video(
    bvid: str,
    template_type: TemplateType,
    config: Config,
    use_asr: bool = True,
    asr_model: str = "base",
) -> tuple[dict, str]:
    """处理单个视频，返回 (summary_data, markdown_text)。

    Returns:
        (video_info_dict, markdown_content)
    """
    from rich.console import Console as RichConsole
    # 抑制 rich 输出（GUI模式下不需要终端输出）
    import bili_summarizer.subtitle as sub_mod
    import bili_summarizer.summarizer as sum_mod
    import bili_summarizer.output as out_mod
    _dummy = RichConsole(file=open(os.devnull, "w"))

    segments, video_info = fetch_subtitles(
        bvid, use_asr=use_asr, asr_model=asr_model,
    )
    preprocessor = SubtitlePreprocessor()
    segments = preprocessor.process(segments)
    blocks = chunk_subtitles(
        segments, chunk_size=config.chunk_size, chunk_overlap=config.chunk_overlap,
    )

    summarizer = LLMSummarizer()
    summary = summarizer.summarize(blocks, video_info, template_type)

    formatter = MarkdownFormatter()
    md_content = formatter.format(summary, template_type.value)

    info = {
        "bvid": video_info.bvid,
        "title": video_info.title,
        "up_name": video_info.up_name,
        "duration": video_info.duration,
        "segments_count": len(segments),
        "blocks_count": len(blocks),
    }
    return info, md_content


def process_compare(
    bvids: list[str],
    config: Config,
    use_asr: bool = True,
    asr_model: str = "base",
) -> str:
    """多视频对比，返回对比分析Markdown。"""
    from bili_summarizer.templates.compare import CompareTemplate

    video_summaries = []
    progress_bar = st.progress(0, text="准备处理视频...")

    for idx, bvid in enumerate(bvids):
        progress_bar.progress(
            (idx) / len(bvids),
            text=f"处理视频 {idx+1}/{len(bvids)}: {bvid}",
        )
        try:
            _, md_content = process_single_video(
                bvid, TemplateType.COMPARE, config, use_asr, asr_model,
            )
            video_summaries.append({
                "title": f"BV{bvid}" if not bvid.startswith("BV") else bvid,
                "summary": md_content,
            })
        except Exception as e:
            st.warning(f"视频 {bvid} 处理失败: {e}")
            video_summaries.append({
                "title": bvid,
                "summary": f"处理失败: {e}",
            })

    progress_bar.progress(0.9, text="正在生成对比分析...")

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

    header = "# 多视频对比分析\n\n"
    header += "> " + " | ".join(v["title"] for v in video_summaries) + "\n"
    header += f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"

    progress_bar.progress(1.0, text="完成！")
    return header + compare_result


# ─── 侧边栏 ────────────────────────────────────────────────

with st.sidebar:
    st.header("⚙️ 设置")

    # API 配置
    with st.expander("API 配置", expanded=True):
        api_key = st.text_input(
            "API Key",
            value=os.getenv("OPENAI_API_KEY", ""),
            type="password",
            help="从 .env 文件读取，也可手动输入覆盖",
        )
        base_url = st.text_input(
            "Base URL",
            value=os.getenv("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1"),
        )
        model = st.text_input(
            "模型",
            value=os.getenv("LLM_MODEL", "deepseek-ai/DeepSeek-V4-Flash"),
        )

    # 字幕配置
    with st.expander("字幕 & ASR"):
        use_asr = st.checkbox("启用 ASR 兜底", value=True, help="CC字幕获取失败时自动使用语音转写")
        asr_model_select = st.selectbox(
            "ASR 模型",
            ["tiny", "base", "small", "medium", "large-v3"],
            index=1,
            help="模型越大越准，但越慢越吃显存",
        )

    # 高级设置
    with st.expander("高级"):
        chunk_size = st.slider("切片大小（字符）", 1000, 8000, 3000, step=500)
        temperature = st.slider("Temperature", 0.0, 1.0, 0.3, step=0.1)
        output_dir = st.text_input("输出目录", value="./output")

    st.divider()
    st.caption("bili-ai-summarizer v0.4.1")
    st.caption("[:github: GitHub](https://github.com/) · MIT License")


# ─── 主界面 ────────────────────────────────────────────────

st.title("🎬 B站视频AI总结")
st.caption("下载字幕 → AI分析 → 结构化Markdown输出")

# 选择模板
col1, col2 = st.columns([1, 2])
with col1:
    template_label = st.selectbox(
        "分析模式",
        list(TEMPLATE_OPTIONS.keys()),
        index=0,
    )
    template_type = TEMPLATE_OPTIONS[template_label]
    st.info(TEMPLATE_DESCRIPTIONS[template_type])
    # 模式示例
    if template_type in TEMPLATE_EXAMPLES:
        with st.expander("💡 这个模式输出什么？"):
            st.markdown(TEMPLATE_EXAMPLES[template_type])

with col2:
    if template_type == TemplateType.COMPARE:
        url_input = st.text_area(
            "输入BV号（每行一个，或用逗号分隔）",
            placeholder="BV1WVfcYFEiX\nBV1D97H64Eqx",
            height=100,
        )
    else:
        url_input = st.text_input(
            "输入BV号或B站链接",
            placeholder="BV1WVfcYFEiX 或 https://www.bilibili.com/video/BV1WVfcYFEiX",
        )

st.divider()

# ─── 运行按钮 ────────────────────────────────────────────────

run_col1, run_col2 = st.columns([1, 5])
with run_col1:
    run_clicked = st.button("🚀 开始分析", type="primary", use_container_width=True)
with run_col2:
    dry_run_clicked = st.button("🔍 仅获取字幕（dry-run）", use_container_width=True)

# ─── 执行逻辑 ────────────────────────────────────────────────

if run_clicked or dry_run_clicked:
    # 提取BV号
    bvids = extract_bvid(url_input)
    if not bvids:
        st.error("请输入有效的BV号或B站视频链接")
        st.stop()

    # 配置初始化
    try:
        overrides = {}
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
        if base_url:
            os.environ["OPENAI_BASE_URL"] = base_url
            overrides["llm_base_url"] = base_url
        if model:
            overrides["llm_model"] = model
        overrides["chunk_size"] = chunk_size
        overrides["llm_temperature"] = temperature
        if output_dir:
            overrides["output_dir"] = Path(output_dir)

        config = init_config(**overrides)
    except ValueError as e:
        st.error(f"配置错误: {e}")
        st.stop()

    is_dry_run = dry_run_clicked

    # ─── 多视频对比 ──────────────────────────────────────────
    if template_type == TemplateType.COMPARE and not is_dry_run:
        if len(bvids) < 2:
            st.error("对比模式需要至少2个BV号")
            st.stop()

        try:
            result_md = process_compare(
                bvids, config,
                use_asr=use_asr,
                asr_model=asr_model_select,
            )

            st.success("✓ 对比分析完成！")

            # 显示结果
            st.markdown(result_md)

            # 下载按钮
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(
                "📥 下载对比结果 (.md)",
                data=result_md,
                file_name=f"compare_{timestamp}.md",
                mime="text/markdown",
            )

            # 同时保存到output目录
            output_path = Path(output_dir) / f"compare_{timestamp}.md"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(result_md, encoding="utf-8")

        except Exception as e:
            st.error(f"处理失败: {e}")

    # ─── 单视频模式 ──────────────────────────────────────────
    else:
        for bvid in bvids:
            with st.expander(f"📹 {bvid}", expanded=True):
                try:
                    # Dry-run 模式
                    if is_dry_run:
                        with st.spinner("获取字幕中..."):
                            segments, video_info = fetch_subtitles(
                                bvid,
                                use_asr=use_asr,
                                asr_model=asr_model_select,
                            )
                            preprocessor = SubtitlePreprocessor()
                            segments = preprocessor.process(segments)

                        st.success(
                            f"✓ 字幕获取成功！"
                            f" — {video_info.title} | {len(segments)} 条字幕"
                        )
                        st.write(f"**UP主**: {video_info.up_name}")
                        st.write(f"**时长**: {format_timestamp(video_info.duration)}")

                        # 显示前几条字幕
                        with st.expander("查看字幕预览"):
                            for seg in segments[:20]:
                                st.write(
                                    f"`[{format_timestamp(seg.start_time)}]` {seg.text}"
                                )
                            if len(segments) > 20:
                                st.caption(f"...共 {len(segments)} 条")
                        continue

                    # 正式分析
                    with st.spinner(f"正在分析 {bvid}..."):
                        info, md_content = process_single_video(
                            bvid, template_type, config,
                            use_asr=use_asr,
                            asr_model=asr_model_select,
                        )

                    st.success(f"✓ 分析完成！ — {info['title']}")

                    # 显示结果
                    st.markdown(md_content)

                    # 下载按钮
                    # 清理文件名
                    title_slug = info["title"][:30] if info["title"] else ""
                    for ch in ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '\n', '\r']:
                        title_slug = title_slug.replace(ch, '_')

                    st.download_button(
                        f"📥 下载 {info['title'][:20]} (.md)",
                        data=md_content,
                        file_name=f"{title_slug}_{bvid}.md",
                        mime="text/markdown",
                        key=f"dl_{bvid}",
                    )

                    # 保存到output目录
                    output_path = Path(output_dir) / f"{title_slug}_{bvid}.md"
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_text(md_content, encoding="utf-8")

                except Exception as e:
                    st.error(f"❌ {bvid} 处理失败: {e}")


# ─── 使用指南 ────────────────────────────────────────────────
with st.expander("📖 使用指南", expanded=False):
    st.markdown("""
### 🎯 这个工具能做什么？

| 能力 | 说明 |
|------|------|
| 批量获取B站字幕 | CC字幕优先，无CC自动ASR语音转写兜底 |
| AI结构化总结 | 6种分析模式，覆盖信息搜集到深度批判 |
| Markdown输出 | 标准格式，可直接用于笔记/博客/RAG知识库 |

### 🤔 根据你的需求选择

**「我只想把视频转成纯文字」**
→ 不需要AI总结，用上方的「仅获取字幕」按钮即可
→ 如果视频没有CC字幕且ASR效果不好，试试 [通义听悟](https://tingwu.aliyun.com/)（免费，上传视频即可生成高质量字幕）

**「我想快速提取视频中的关键信息」**
→ 用 **实体提取** 模式：人名、书名、工具、数据一目了然
→ 用 **时间线梳理** 模式：历史/事件类视频重建时间线

**「我想深度分析某个视频的观点」**
→ 用 **观点批判** 模式：自动识别逻辑谬误、偏见、论证漏洞

**「我想对比不同UP主对同一话题的看法」**
→ 用 **多视频对比** 模式：输入多个BV号，AI自动交叉对比

**「我想把输出做进一步加工」**
→ **思维导图**：把生成的Markdown文件丢给任意AI（ChatGPT/DeepSeek/豆包），让它画思维导图
→ **知识卡片**：用Markdown手动或让AI拆成Anki卡片
→ **RAG知识库**：Markdown格式可直接灌入向量数据库，用于问答检索

### 📋 分析模式详解

| 模式 | 适用视频 | 举例 | 你会得到什么 |
|------|---------|------|------------|
| 教程/技术 | 编程教程、技术讲解 | Python爬虫课、VSCode配置指南 | 分步骤操作笔记 + 关键概念 |
| 剧情/解说 | 影视解说、游戏攻略 | 明日方舟剧情解析、电影解说 | 情节概要 + 人物动态 + 伏笔 |
| 实体提取 | 信息密集型视频 | 读书分享、行业报告 | 人名/书名/工具/数据/URL 清单 |
| 时间线梳理 | 历史/事件类视频 | AI发展史、公司成长史 | 带因果链的事件年表 |
| 观点批判 | 观点输出型视频 | 社会评论、投资分析 | 逻辑谬误 + 偏见检测 + 论证强度评分 |
| 多视频对比 | 同主题多源分析 | 3个Python入门课对比 | 共识/分歧/互补点/综合评估 |

### 💻 命令行方式

```bash
# 激活虚拟环境
.venv\\Scripts\\activate

# 基本用法
bili-summarize BV1WVfcYFEiX

# 选择模板
bili-summarize BV1WVfcYFEiX -t entity
bili-summarize BV1WVfcYFEiX -t critique

# 多视频对比
bili-summarize BV1WVfcYFEiX,BV1D97H64Eqx -t compare

# 仅获取字幕
bili-summarize BV1WVfcYFEiX --dry-run
```

### ⚠️ 常见问题

**获取字幕失败/0条字幕**
→ 大多数视频没有CC字幕，需启用ASR兜底（侧边栏勾选）
→ 确认 `.env` 中的 `BILIBILI_SESSDATA` 已填写且未过期

**ASR很慢**
→ 台式机（无独显）用tiny/base模型，游戏本可用small及以上
→ ASR需要额外安装：`pip install -e ".[asr]"`（CPU）或 `pip install -e ".[cuda]"`（GPU）

**分析结果太短/太长**
→ 侧边栏「高级」调整切片大小，大切片=更多上下文但更贵
""")
