.PHONY: install run test clean lint

# 安装依赖
install:
	pip install -e ".[dev]"

# 安装 ASR 支持（可选，需要 CUDA 环境）
install-asr:
	pip install -e ".[dev,asr]"

# 单视频总结
run:
	bili-summarize $(URL) -t $(TYPE)

# 干跑（仅获取字幕，不调用LLM）
dry-run:
	bili-summarize $(URL) --dry-run

# 运行测试
test:
	pytest tests/ -v

# 代码检查
lint:
	ruff check bili_summarizer/

# 清理
clean:
	rm -rf build/ dist/ *.egg-info output/ __pycache__/
	find . -name "*.pyc" -delete
