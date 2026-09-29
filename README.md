# Daily-Paper

每天自动从 [llm-paper-daily](https://github.com/xianshang33/llm-paper-daily) 的公开 feed 中读取候选论文，再用 LLM 按个人偏好做第二层筛选，最终推荐 Top 3。

## 默认关注方向

- LLM Reasoning
- Post-training / RLHF / DPO / RL
- Agent / Tool Use
- RAG
- Efficient LLM / Inference

排序会额外考虑：

- 技术新颖性
- 对当前 LLM 技术路线的意义
- 大模型算法实习面试中的讨论价值
- 实验完整度 / 是否有开源实现

## 每日输出

GitHub Actions 默认每天 **08:00（Asia/Singapore / 北京时间）**运行。

每次出现新的 feed 日期时，会创建一个 GitHub Issue，包含最多 3 篇论文：

- 推荐理由
- 核心贡献
- 阅读建议：精读 / 快速读 / 只看摘要
- 面试中可能被追问的问题
- arXiv / PDF / GitHub 链接

如果当天 feed 没更新，不会重复创建同一日期的 Issue。

## 需要你做的一次性配置

进入：

`Settings → Secrets and variables → Actions → New repository secret`

添加：

`OPENAI_API_KEY`

值填写你的 OpenAI API Key。

> 不要把 API Key 写进代码或 README。

可选：在仓库的 Actions Variables 中添加：

- `OPENAI_MODEL`：默认 `gpt-6-luna`
- `TOP_N`：默认 `3`

## 手动测试

进入仓库：

`Actions → Daily LLM Paper Digest → Run workflow`

无需等待第二天定时运行。

## 本地运行

```bash
pip install -r requirements.txt
export OPENAI_API_KEY="..."
python daily_paper.py
```

本地运行时会输出 `daily_digest.md`；只有在 GitHub Actions 且存在 `GITHUB_TOKEN` / `GITHUB_REPOSITORY` 时才会自动创建 Issue。

## 数据源

当前第一层候选来自：

`https://raw.githubusercontent.com/xianshang33/llm-paper-daily/main/feed-papers.json`

第二层由 LLM 根据本仓库内置的个人偏好 prompt 排序。

## 自定义兴趣

修改 `daily_paper.py` 中的 `USER_PROFILE` 即可调整关注方向和筛选标准。
