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


## Foundation Track（每周经典 / 基础论文）

除了每天的前沿论文，本仓库还维护一条 Foundation Track，用来补齐与当前就业方向相关的经典与基础工作。

默认每周六 **10:00（Asia/Singapore / 北京时间）**运行：

`Hugging Face 前沿阅读记录 → 最近 7 天 Daily Digest → GPT-6 Luna 匹配基础缺口 → 推荐 2 篇 Foundation Papers → 飞书私聊 + GitHub Issue`

Foundation Track 当前覆盖：

- Transformer / Scaling / Pretraining
- Instruction Tuning / RLHF / DPO / Alignment
- Reasoning / CoT / PRM / Test-time Search
- Agent / Tool Use / Reflection / Long-horizon Agent
- RAG / Retrieval / Agent Memory / Long Context
- LLM Serving / KV Cache / FlashAttention / Speculative Decoding

基础论文池保存在：

`foundation_papers.json`

目前包含约 30 篇核心论文，并标注：

- track
- priority
- 为什么和就业相关
- 常见面试知识点
- 论文链接

每周选择时会读取最近 7 天的 Daily Digest，因此如果这一周前沿推荐集中在 Agent Memory / Context Management，Foundation Track 会更倾向补 ReAct、MemGPT、Generative Agents、RAG 等地基；如果最近集中在 RLVR / Reward / Verifier，则会优先补 InstructGPT、DPO、Let's Verify Step by Step 等。

Foundation Track 不再把“推荐过”当成“读完了”。

每周 Foundation Issue 中，每篇论文前都会有一个 GitHub task checkbox：

- 未勾选：仍属于未完成 backlog，以后可以再次推荐
- 勾选为 [x]：才视为已完成，并从后续候选池排除

因此即使某周忙，没有读推荐的 Foundation Paper，也不会永久错过。飞书卡片里会提供“读完后勾选进度”的按钮，跳转到对应 GitHub Issue。

论文池目前扩充到 **77 篇**，并统一分为三级：

- **必须掌握（must_know）**：求职前应能讲清核心方法、动机、关键公式或系统设计，并能回答常见追问
- **推荐精读（recommended）**：与目标岗位高度相关，应理解问题、方法、实验结论及和相邻工作的区别
- **知道即可（awareness）**：用于建立技术地图和历史脉络，通常快速读摘要、主图和结论即可

可选 Actions Variable：

- `FOUNDATION_TOP_N`：每周推荐数量，默认 `2`

手动测试：

`Actions → Weekly Foundation Papers → Run workflow`

## 飞书卡片内交互

Foundation 卡片支持：

- **✅ 标记已读**：直接在飞书中标记完成，后台更新 Foundation Issue 进度。
- **🔄 换一批**：触发新的 Foundation 推荐，并排除当前这批论文。

交互按钮需要一个公网 HTTPS 回调地址。现在使用 **Cloudflare Workers**，不再依赖 Vercel。

### Cloudflare Worker 文件

- `worker/index.js`：飞书卡片回调处理逻辑
- `wrangler.toml`：Worker 配置
- `package.json`：Wrangler 部署命令

Worker 自身不保存数据库状态：

`飞书按钮 → Cloudflare Worker → GitHub API → 更新 Issue / 触发 Foundation workflow`

### 需要的 Worker Secrets

部署后在 Cloudflare Worker 中配置：

- `GITHUB_PAT`：GitHub fine-grained token，只授权 `twyran/Daily-Paper`
  - Issues: Read and write
  - Actions: Read and write
- `FEISHU_OPEN_ID`：你的飞书 open_id，用于限制操作人
- `FEISHU_VERIFICATION_TOKEN`：可选；若飞书回调配置使用 verification token，则填写

`GITHUB_REPOSITORY=twyran/Daily-Paper` 已写在 `wrangler.toml` 中，无需作为 Secret。

### 部署方式

安装 Node.js 后，在仓库目录执行：

```bash
npm install
npx wrangler login
npx wrangler secret put GITHUB_PAT
npx wrangler secret put FEISHU_OPEN_ID
# 如果飞书启用了 verification token：
npx wrangler secret put FEISHU_VERIFICATION_TOKEN
npm run deploy
```

Wrangler 会给出类似：

`https://daily-paper-feishu-callback.<你的子域>.workers.dev`

的公网地址。

先浏览器打开该地址，应看到：

```json
{"ok":true,"service":"Daily-Paper Feishu callback"}
```

然后把这个 Worker URL 填入飞书自建应用的**消息卡片回调地址**。飞书验证 URL 后，卡片中的“标记已读”和“换一批”即可在飞书内直接生效。

### 安全说明

不要把 `GITHUB_PAT`、`FEISHU_OPEN_ID` 或 verification token 写进公开仓库。Worker 代码只从 Cloudflare Secrets 读取敏感值。
