"""剧情/解说类视频的 Prompt 模板。"""

from __future__ import annotations

from . import PromptTemplate, TemplateType, register_template


class NarrativeTemplate:
    """剧情/解说类总结模板。"""

    def chunk_prompt(self, text: str, time_range: str) -> str:
        return f"""请总结以下视频片段的内容。这是一个剧情/解说类视频。

时间范围：{time_range}

字幕文本：
{text}

请按以下格式输出：

**情节概要**：用2-3句话描述这个片段发生了什么

**关键事件**：（列出该片段中的重要事件或转折点）
- ...

**人物动态**：（涉及的角色及其行为/关系变化，没有则省略）

**氛围/情绪**：片段的整体情感基调（如紧张、温馨、悬疑等），用1-2个词概括"""

    def global_prompt(self, chunk_summaries: str, video_title: str) -> str:
        return f"""请基于以下各片段总结，生成完整的视频总结。

视频标题：{video_title}

各片段总结：
{chunk_summaries}

请按以下格式输出：

## 概要
用1-2句话概括整个视频的核心叙事/主题。

## 时间线
按时间顺序列出剧情关键节点，格式为：
- [mm:ss] 事件描述

要求：
- 时间线覆盖主要剧情转折和关键事件
- 每个节点描述简洁（不超过30字）
- 时间戳必须准确，与片段时间范围对应
- 突出转折点和高潮
- 如果是解说类内容，突出核心论点和论据"""


register_template(TemplateType.NARRATIVE, NarrativeTemplate())
