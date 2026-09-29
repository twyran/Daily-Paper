# Daily-Paper

每天自动从 Hugging Face Daily Papers 获取候选论文，再用 LLM 按个人偏好做第二层筛选，最终推荐 Top 3，并推送到飞书。

## 流程

Hugging Face Daily Papers
→ GPT-6 Luna 二次筛选
→ Top 3
→ 飞书群机器人
→ GitHub Issue 归档

GitHub Actions 默认每天 **08:00（Asia/Singapore / 北京时间）**运行。

## 默认关注方向

- LLM Reasoning
- Post-training / RLHF / DPO / RL
- Agent / Tool Use
- RAG
- Efficient LLM / Inference

排序额外考虑技术新颖性、当前 LLM 技术路线价值、算法实习面试讨论价值、实验完整度、开源实现，以及 Hugging Face 社区热度。HF upvotes 只是辅助信号，不会单纯按热度排序。

## 必需配置

进入：

Settings → Secrets and variables → Actions → New repository secret

添加以下 Secrets：

- `OPENAI_API_KEY`：智增增 API Key
- `FEISHU_APP_ID`：飞书自建应用 App ID\n- `FEISHU_APP_SECRET`：飞书自建应用 App Secret\n- `FEISHU_OPEN_ID`：接收私聊消息的用户 open_id

可选：

- `HF_TOKEN`：Hugging Face Access Token。当前接口通常可公开读取，但配置 Token 能提高兼容性。
- Actions Variable `OPENAI_MODEL`：默认 `gpt-6-luna`
- Actions Variable `OPENAI_BASE_URL`：默认 `https://api.zhizengzeng.com/v1`
- Actions Variable `TOP_N`：默认 `3`
- Actions Variable `HF_LIMIT`：每日最多取多少篇 HF 候选，默认 `100`

## 飞书机器人配置

使用企业自建应用机器人主动给指定用户发送私聊消息，不再使用群 Webhook。

需要在 GitHub Secrets 中配置：

- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_OPEN_ID`

运行时脚本会先用 App ID + App Secret 获取 `tenant_access_token`，再通过 `open_id` 调用飞书消息接口发送私聊。

## Hugging Face 数据源

使用官方接口：

`https://huggingface.co/api/daily_papers`

脚本优先请求当天 Daily Papers；如果当天列表暂时为空，会自动退回最近一期，避免早上 08:00 没有任何内容。

## GitHub Issue

除了飞书推送，每期结果仍然会创建一个 GitHub Issue 做历史归档。同一日期不会重复创建 Issue。

## 手动测试

进入：

Actions → Daily LLM Paper Digest → Run workflow

即可立即跑一次。

## 本地运行

```bash
pip install -r requirements.txt
export OPENAI_API_KEY="..."
export FEISHU_WEBHOOK_URL="..."
python daily_paper.py
```

## 自定义兴趣

修改 `daily_paper.py` 中的 `USER_PROFILE` 即可调整关注方向和筛选标准。
