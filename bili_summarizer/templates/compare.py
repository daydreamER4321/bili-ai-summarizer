"""多视频对比模板：对同一主题的多个视频进行交叉对比分析。"""

from __future__ import annotations

from . import PromptTemplate, TemplateType, register_template


class CompareTemplate:
    """多视频对比模板——信息搜集专用。"""

    def chunk_prompt(self, text: str, time_range: str) -> str:
        return f"""请总结以下视频片段的核心内容，重点关注观点、论据和立场。

时间范围：{time_range}

字幕文本：
{text}

请按以下格式输出：

**核心观点**：用1-2句话概括这个片段的核心主张

**关键论据**：列出支撑观点的事实、数据、案例

**立场倾向**：作者对这个话题的立场（支持/反对/中立/复杂）

**独有信息**：这个片段提供了其他来源可能没有的独特信息"""

    def global_prompt(self, chunk_summaries: str, video_title: str) -> str:
        return f"""请基于以下各片段总结，生成完整的视频内容总结。

视频标题：{video_title}

各片段总结：
{chunk_summaries}

请按以下格式输出：

## 📋 视频总结

### 核心立场
用2-3句话概括这个视频对该主题的整体立场。

### 主要论点与论据
1. **论点1**
   - 论据：...
   - 立场：...

2. **论点2**
   - 论据：...

### 独有贡献
这个视频提供了哪些独特的信息或视角？"""

    @staticmethod
    def compare_prompt(video_summaries: list[dict]) -> str:
        """生成多视频对比的prompt。

        Args:
            video_summaries: 每个视频的摘要信息列表，每项包含:
                - title: 视频标题
                - summary: 视频总结文本
        """
        videos_text = ""
        for i, v in enumerate(video_summaries, 1):
            videos_text += f"\n### 视频 {i}：{v['title']}\n{v['summary']}\n"

        return f"""请对以下多个视频进行交叉对比分析。这些视频讨论的是同一主题或相关主题。

{videos_text}

请按以下格式输出对比分析报告：

## 📋 多视频对比分析

### 主题共识
所有视频都认同的核心观点或事实：
- ...

### 关键分歧
视频之间观点不一致的地方：
| 分歧点 | 视频1立场 | 视频2立场 | ... | 分析 |
|--------|----------|----------|-----|------|

### 互补信息
每个视频独有的、其他视频未提及的重要信息：
| 视频 | 独有信息 | 信息价值 |
|------|---------|---------|

### 论证强度对比
| 视频 | 论据充分度 | 逻辑严密度 | 客观性 | 综合评价 |
|------|-----------|-----------|--------|---------|

### 信息拼图
综合所有视频的信息，还原出更完整的事实图景：
1. 确定的事实：...
2. 大概率成立：...
3. 存在争议：...
4. 信息不足：...

### 推荐深入方向
- 如果要深入了解这个主题，应该看什么/查什么
- 哪个视频的论证最值得采信，为什么

要求：
- 对比要客观，不要预设某个视频更正确
- 分歧点要标注各方原文依据
- 信息拼图要区分确定性和不确定性"""


register_template(TemplateType.COMPARE, CompareTemplate())
