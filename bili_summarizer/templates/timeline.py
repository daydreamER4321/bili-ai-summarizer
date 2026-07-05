"""时间线梳理模板：从历史/事件类视频中重建精确时间线和因果链。"""

from __future__ import annotations

from . import PromptTemplate, TemplateType, register_template


class TimelineTemplate:
    """时间线梳理模板——事件脉络重建专用。"""

    def chunk_prompt(self, text: str, time_range: str) -> str:
        return f"""请从以下视频片段中提取所有时间相关的事件节点。

时间范围：{time_range}

字幕文本：
{text}

请按以下格式提取：

**事件节点**：（按时间顺序列出）
- [日期/时段] 事件：简述（1-2句）

**因果链**：（识别事件之间的因果关系）
- A → B：A如何导致B

**关键转折**：（标注改变走向的关键节点）
- 转折点：描述及原因

**背景信息**：（影响事件走向的背景、前因）

要求：
- 日期尽量精确到年月日，字幕中模糊的标注"约XX年"
- 区分确定事实和推测
- 因果关系必须有明确文本支撑，不要推测"""

    def global_prompt(self, chunk_summaries: str, video_title: str) -> str:
        return f"""请基于以下各片段的事件提取，整合生成完整的时间线。

视频标题：{video_title}

各片段提取结果：
{chunk_summaries}

请按以下格式输出：

## 📋 完整时间线

### 事件年表
按时间顺序列出所有事件节点：
| 时间 | 事件 | 重要程度 | 确定性 |
|------|------|---------|--------|

（重要程度：⭐核心 / 🔵重要 / ⚪次要；确定性：✓确认 / ⚠存疑）

### 因果关系图
用文字描述事件间的因果关系链：
```
事件A ──→ 事件B ──→ 事件C
  │                    │
  └──→ 事件D          └──→ 事件E
```

### 关键转折点
1. **[时间] 转折点描述**
   - 原因：...
   - 影响：...
   - 如果没有这个转折，可能走向：...

### 争议与存疑
- 标注视频中说法不一致或证据不足的地方

要求：
- 时间线必须严格按时间顺序
- 因果箭头必须有文本依据
- 争议点必须标注，不要强行定论"""


register_template(TemplateType.TIMELINE, TimelineTemplate())
