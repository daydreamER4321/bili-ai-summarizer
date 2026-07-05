"""Prompt 模板注册表。"""

from __future__ import annotations

from enum import Enum
from typing import Protocol


class TemplateType(str, Enum):
    """总结模板类型。"""
    TUTORIAL = "tutorial"      # 教程/技术类
    NARRATIVE = "narrative"    # 剧情/解说类
    ENTITY = "entity"          # 实体提取
    TIMELINE = "timeline"      # 时间线梳理
    CRITIQUE = "critique"      # 观点批判
    COMPARE = "compare"        # 多视频对比


class PromptTemplate(Protocol):
    """模板协议：每个模板必须实现 chunk_prompt 和 global_prompt。"""

    def chunk_prompt(self, text: str, time_range: str) -> str: ...
    def global_prompt(self, chunk_summaries: str, video_title: str) -> str: ...


# ─── 模板注册 ────────────────────────────────────────────────

_TEMPLATES: dict[TemplateType, PromptTemplate] = {}


def register_template(template_type: TemplateType, template: PromptTemplate) -> None:
    _TEMPLATES[template_type] = template


def get_template(template_type: TemplateType) -> PromptTemplate:
    if template_type not in _TEMPLATES:
        raise ValueError(f"未注册的模板类型: {template_type}，可用: {list(_TEMPLATES.keys())}")
    return _TEMPLATES[template_type]


# ─── 延迟导入注册 ────────────────────────────────────────────

def _init_templates() -> None:
    """初始化所有内置模板。仅在首次调用时执行。"""
    if _TEMPLATES:
        return
    from .tutorial import TutorialTemplate
    from .narrative import NarrativeTemplate
    from .entity import EntityTemplate
    from .timeline import TimelineTemplate
    from .critique import CritiqueTemplate
    from .compare import CompareTemplate
    register_template(TemplateType.TUTORIAL, TutorialTemplate())
    register_template(TemplateType.NARRATIVE, NarrativeTemplate())
    register_template(TemplateType.ENTITY, EntityTemplate())
    register_template(TemplateType.TIMELINE, TimelineTemplate())
    register_template(TemplateType.CRITIQUE, CritiqueTemplate())
    register_template(TemplateType.COMPARE, CompareTemplate())


_init_templates()
