# bili-ai-summarizer

B站视频AI总结工具：字幕提取 → 预处理 → LLM结构化总结 → Markdown输出

输入一个BV号，输出一份带时间戳的结构化总结。支持6种分析模式、Streamlit GUI、桌面APP。

## 特性

- **B站字幕提取**：CC字幕优先，无CC自动ASR语音转写兜底
- **6种分析模式**：教程、剧情、实体提取、时间线、观点批判、多视频对比
- **Streamlit GUI**：浏览器界面，选模式→输BV号→出结果
- **桌面APP**：双击图标直接打开，无命令行黑框（pywebview）
- **字幕预处理**：合并碎片句、去杂质标记、去重、时间戳修正
- **滑动窗口长文本**：自动切片+重叠，长视频总结也连贯
- **Markdown输出**：标准格式，可直接用于笔记/博客/RAG知识库
- **纯Python**：无Node.js/Rust依赖，pip install即可用

## 快速开始

### 安装

```bash
git clone https://github.com/your-username/bili-ai-summarizer.git
cd bili-ai-summarizer

# 基础安装
pip install -e .

# 带GUI支持
pip install -e ".[gui]"

# 带桌面APP支持（Windows）
pip install -e ".[desktop]"

# 带ASR兜底（CPU）
pip install -e ".[asr]"

# 带ASR兜底（NVIDIA GPU）
pip install -e ".[cuda]"
```

### 配置

```bash
cp .env.example .env
# 编辑 .env，填入你的配置
```

`.env` 配置说明：

| 变量 | 必填 | 说明 |
|------|------|------|
| `OPENAI_API_KEY` | ✅ | LLM API密钥 |
| `OPENAI_BASE_URL` | ❌ | API地址（默认 `https://api.siliconflow.cn/v1`） |
| `LLM_MODEL` | ❌ | 模型名（默认 `deepseek-ai/DeepSeek-V4-Flash`） |
| `BILIBILI_SESSDATA` | ✅ | B站登录Cookie，获取CC字幕必须 |
| `OUTPUT_DIR` | ❌ | 输出目录（默认 `./output`） |

> **SESSDATA获取**：浏览器登录B站 → F12开发者工具 → Application → Cookies → 找到 `SESSDATA` 的值

### 使用方式

#### 方式1：桌面APP（推荐）

```bash
# 首次：创建桌面快捷方式
python create_shortcut.py

# 之后双击桌面「B站视频AI总结」图标即可
```

#### 方式2：Web界面

```bash
streamlit run app.py
# 浏览器自动打开 http://localhost:8501
```

#### 方式3：命令行

```bash
# 基础用法
bili-summarize BV1WVfcYFEiX

# 选择分析模式
bili-summarize BV1WVfcYFEiX -t entity      # 实体提取
bili-summarize BV1WVfcYFEiX -t timeline     # 时间线梳理
bili-summarize BV1WVfcYFEiX -t critique     # 观点批判

# 多视频对比
bili-summarize BV1WVfcYFEiX,BV1D97H64Eqx -t compare

# 仅获取字幕（不调用LLM）
bili-summarize BV1WVfcYFEiX --dry-run

# 指定输出目录
bili-summarize BV1WVfcYFEiX -o ./my-summaries
```

## 分析模式

| 模式 | CLI参数 | 适用视频 | 输出内容 |
|------|---------|---------|---------|
| 教程/技术 | `-t tutorial` | 编程教程、技术讲解 | 分步骤操作笔记 + 关键概念 |
| 剧情/解说 | `-t narrative` | 影视解说、游戏攻略 | 情节概要 + 人物动态 + 伏笔 |
| 实体提取 | `-t entity` | 读书分享、行业报告、信息搜集 | 人名/书名/工具/数据/URL 清单 |
| 时间线梳理 | `-t timeline` | 历史事件、技术演进 | 带因果链的事件年表 |
| 观点批判 | `-t critique` | 社会评论、投资分析、深度解读 | 逻辑谬误 + 偏见检测 + 论证强度 |
| 多视频对比 | `-t compare` | 同主题多源对比 | 共识/分歧/互补/综合评估 |

### 输出示例

```markdown
# Python装饰器从入门到精通
> UP主: 某某UP | 生成时间: 2026-06-28 12:00 | 总结模式: tutorial | BV号: BV1xx

## 📋 概要
系统讲解了Python装饰器的概念、用法和常见模式，从函数装饰器到类装饰器逐步深入。

## ⏱ 时间线
- **[00:00]** 装饰器基本概念引入
- **[03:24]** 函数装饰器语法糖 @
- **[07:15]** 带参数的装饰器
- **[12:40]** functools.wraps 的作用
- **[18:02]** 类装饰器
- **[22:30]** 常见应用场景总结

## 📝 详细总结
### [00:00 - 03:24]
**核心内容**：介绍装饰器的定义和基本思想...

---
*由 bili-ai-summarizer 自动生成 · 2026-06-28 12:00*
```

## 根据需求选择工具

| 你的需求 | 推荐方案 |
|---------|---------|
| 纯字幕转文字 | 本工具「仅获取字幕」模式，或 [通义听悟](https://tingwu.aliyun.com/)（免费，支持上传视频） |
| 快速提取关键信息 | 实体提取 / 时间线梳理模式 |
| 深度分析观点 | 观点批判模式 |
| 对比多个视频 | 多视频对比模式 |
| 生成思维导图 | 把输出的Markdown丢给AI，让它画思维导图 |
| 灌入RAG知识库 | Markdown格式可直接切分为向量检索的chunk |

## 项目结构

```
bili-ai-summarizer/
├── app.py                    # Streamlit GUI
├── start.pyw                 # 桌面APP启动器（pywebview）
├── create_shortcut.py        # 创建桌面快捷方式
├── assets/
│   ├── icon.ico              # 应用图标
│   └── icon.png
├── bili_summarizer/
│   ├── __init__.py
│   ├── cli.py                # CLI入口（click）
│   ├── config.py             # 全局配置
│   ├── subtitle.py           # 字幕获取+预处理+切片
│   ├── asr.py                # ASR语音转写（faster-whisper）
│   ├── summarizer.py         # LLM总结（滑动窗口）
│   ├── output.py             # Markdown格式化输出
│   └── templates/            # Prompt模板
│       ├── __init__.py       # 模板注册表
│       ├── tutorial.py       # 教程/技术
│       ├── narrative.py      # 剧情/解说
│       ├── entity.py         # 实体提取
│       ├── timeline.py       # 时间线梳理
│       ├── critique.py       # 观点批判
│       └── compare.py        # 多视频对比
├── .env.example
├── .gitignore
├── Makefile
├── pyproject.toml
└── README.md
```

## 常见问题

**Q：获取字幕失败/0条字幕？**
A：大多数视频没有CC字幕，需启用ASR兜底。确认 `.env` 中的 `BILIBILI_SESSDATA` 已填写且未过期。

**Q：ASR很慢？**
A：无独显用tiny/base模型，有NVIDIA显卡用small及以上。ASR需额外安装：`pip install -e ".[asr]"`（CPU）或 `pip install -e ".[cuda]"`（GPU）。还需安装 [ffmpeg](https://ffmpeg.org/)。

**Q：双击桌面图标没反应？**
A：确认已安装pywebview：`pip install pywebview pywin32`。然后重新运行 `python create_shortcut.py`。

**Q：想用其他LLM？**
A：修改 `.env` 中的 `OPENAI_BASE_URL` 和 `LLM_MODEL` 即可，支持任何兼容OpenAI API的服务（硅基流动、DeepSeek官方、Ollama本地等）。

## 后续规划

- [ ] 多平台支持（YouTube、抖音）
- [ ] 缓存机制（BV号+字幕hash，避免重复调用LLM）
- [ ] 批量处理（UP主主页、收藏夹）
- [ ] PyInstaller打包为独立.exe
- [ ] Docker 一键部署
- [ ] 成本统计（token用量+费用估算）
- [ ] 关键帧截图+VLM视觉描述

## 许可证

MIT
