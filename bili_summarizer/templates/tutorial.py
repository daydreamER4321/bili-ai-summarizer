"""教程/技术类视频的 Prompt 模板。"""

from __future__ import annotations

from . import PromptTemplate, TemplateType, register_template


class TutorialTemplate:
    """教程类总结模板。"""

    def chunk_prompt(self, text: str, time_range: str) -> str:
        return f"""请总结以下视频片段的内容。这是一个教程/技术类视频。

时间范围：{time_range}

字幕文本：
{text}

请按以下格式输出：

**核心内容**：用1-2句话概括这个片段讲了什么

**关键步骤**：（如果涉及操作步骤，按序号列出；如果没有步骤，写"无具体步骤"）
1. ...
2. ...

**要点笔记**：列出关键概念、命令、参数、注意事项等

**补充说明**：任何需要特别留意的地方（如常见错误、替代方案等），没有则省略"""

    def global_prompt(self, chunk_summaries: str, video_title: str) -> str:
        return f"""请基于以下各片段总结，生成完整的视频总结。

视频标题：{video_title}

各片段总结：
{chunk_summaries}

请按以下格式输出：

## 概要
用1-2句话总结整个视频的核心内容和学习价值。

## 时间线
按时间顺序列出视频中的关键节点，格式为：
- [mm:ss] 事件/知识点描述

要求：
- 时间线覆盖视频的主要知识点和转折点
- 每个节点描述简洁（不超过30字）
- 时间戳必须准确，与片段时间范围对应
- 优先列出操作步骤、关键概念和重要转折"""


register_template(TemplateType.TUTORIAL, TutorialTemplate())
