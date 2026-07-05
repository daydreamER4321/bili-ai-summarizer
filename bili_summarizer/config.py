"""全局配置管理"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    """项目配置，优先读取环境变量，其次使用默认值。"""

    # LLM 配置
    llm_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    llm_base_url: str = field(default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o-mini"))
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.3

    # 滑动窗口配置
    chunk_size: int = 3000          # 每个chunk的字符数
    chunk_overlap: int = 500        # 相邻chunk重叠字符数

    # 字幕预处理配置
    min_sentence_length: int = 4    # 低于此长度的碎片句合并到前一句
    noise_patterns: list[str] = field(default_factory=lambda: [
        r"\[音乐\]", r"\[掌声\]", r"\[笑声\]", r"\[欢呼\]",
        r"\[画面\]", r"\[音效\]", r"\[广告\]",
        r"——\s*——",                    # 空白分隔线
    ])

    # 输出配置
    output_dir: Path = field(default_factory=lambda: Path(os.getenv("OUTPUT_DIR", "./output")))

    # video-captions 配置
    browser: str = "auto"           # Cookie 读取的浏览器

    # ASR 语音转写配置
    asr_model: str = field(default_factory=lambda: os.getenv("ASR_MODEL", "base"))
    asr_device: str = field(default_factory=lambda: os.getenv("ASR_DEVICE", "auto"))

    # 时间戳切片配置
    timeline_granularity: int = 120  # 时间线颗粒度（秒），每2分钟一个锚点

    def validate(self) -> None:
        """校验必要配置。"""
        if not self.llm_api_key:
            raise ValueError(
                "未配置 OPENAI_API_KEY。请在 .env 文件中设置，或设置环境变量。"
            )
        self.output_dir.mkdir(parents=True, exist_ok=True)


# 全局单例
_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
        _config.validate()
    return _config


def reset_config() -> None:
    global _config
    _config = None
