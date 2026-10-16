# Daily-Paper

每天自动从 Hugging Face Daily Papers 获取候选论文，再用 LLM 按个人偏好做第二层筛选，最终推荐 Top 3，并推送到飞书。

## 流程

Hugging Face Daily Papers
→ GPT-6 Luna 二次筛选
→ Top 3
→ 飞书自建应用私聊
→ GitHub Issue 归档

GitHub Actions 每天安排四次定时尝试（Asia/Singapore / 北京时间，UTC+8）：

| cron（UTC） | UTC+8 时间 |
| --- | --- |
| `7 21 * * *` | 次日 05:07 |
| `27 22 * * *` | 次日 06:27 |
| `47 23 * * *` | 次日 07:47 |
| `7 1 * * *` | 当日 09:07 |

四次尝试用于缓解 GitHub Actions 定时任务延迟或漏触发，并非每天推送四份日报，也不保证准点送达。脚本以 UTC+8 推送日期对应的 Issue 标题检查是否已归档；若已存在，则跳过重复推送。该检查依赖 `GITHUB_REPOSITORY` 和 `GITHUB_TOKEN`。

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
- `FEISHU_APP_ID`：飞书自建应用 App ID
- `FEISHU_APP_SECRET`：飞书自建应用 App Secret
- `FEISHU_OPEN_ID`：接收私聊消息的用户 open_id

以上四项是正常生成并推送日报 / Foundation 的必填配置。当前脚本不读取 `FEISHU_WEBHOOK_URL`。

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

脚本按 Asia/Singapore 日期优先请求两天前（D-2）的 Daily Papers；若列表为空，最多再向前查找 7 天，使用最近一期非空列表。

## GitHub Issue

除了飞书推送，工作流还会创建 GitHub Issue 做历史归档。同一日期不会重复创建 Issue。

Actions 自动提供 `GITHUB_REPOSITORY`，工作流通过 `secrets.GITHUB_TOKEN` 注入自动生成的令牌，并声明 `issues: write` 权限，无需手动添加这两项 Secret。本地运行日报时，两项可选，但必须同时设置才能启用 Issue 归档与重复推送检查；缺少任一项仍会推送飞书。本地运行 Foundation 时，两项均必填，用于读取近期日报、阅读进度及创建或更新 Issue。

## 手动测试

进入：

Actions → Daily LLM Paper Digest → Run workflow

即可立即跑一次。

## 本地运行

在仓库根目录使用 Python 3.11（与工作流一致）。替换下列占位值后执行；命令会实际调用 API 并发送飞书私聊。

```bash
python -m pip install -r requirements.txt

# 必填：日报与 Foundation 共用
export OPENAI_API_KEY='替换为 API Key'
export FEISHU_APP_ID='替换为飞书自建应用 App ID'
export FEISHU_APP_SECRET='替换为飞书自建应用 App Secret'
export FEISHU_OPEN_ID='替换为接收用户的 open_id'

# 可选：以下均为当前脚本默认值
export OPENAI_MODEL='gpt-6-luna'
export OPENAI_BASE_URL='https://api.zhizengzeng.com/v1'
export TOP_N='3'                 # 日报每组推荐数量
export HF_LIMIT='100'            # 日报候选数量上限
export FOUNDATION_TOP_N='2'      # Foundation 推荐数量
# export HF_TOKEN='替换为 Hugging Face Access Token'  # 可选，仅日报使用

python daily_paper.py
```

如需日报 Issue 归档及重复推送检查，先设置下面两项，再执行日报命令。Foundation 必须设置这两项：

```bash
export GITHUB_REPOSITORY='twyran/Daily-Paper'
export GITHUB_TOKEN='替换为具有目标仓库 Issues 读写权限的令牌'

python daily_paper.py
# 或运行每周基础论文（读取当前目录下的 foundation_papers.json）
python foundation_paper.py
```

Foundation 另有两个可选环境变量：`FOUNDATION_EXCLUDE_IDS`（逗号分隔的论文 ID，默认空）和 `FOUNDATION_REROLL`（默认 `0`；设为 `1` 且未显式指定排除 ID 时，自动排除当天 Issue 已推荐的论文）。本地需要换批时可执行：

```bash
FOUNDATION_REROLL=1 python foundation_paper.py
```

Actions 手动运行 Foundation 时，工作流自动设置 `FOUNDATION_REROLL=1`，并将可选输入 `exclude_ids` 传给 `FOUNDATION_EXCLUDE_IDS`。

## 自定义兴趣

修改 `daily_paper.py` 中的 `USER_PROFILE` 即可调整关注方向和筛选标准。


## Foundation Track（每周经典 / 基础论文）

除了每天的前沿论文，本仓库还维护一条 Foundation Track，用来补齐与当前就业方向相关的经典与基础工作。

默认每周六 **10:17（Asia/Singapore / 北京时间，UTC+8）**定时尝试运行，对应 cron `17 2 * * 6`（UTC 每周六 02:17）；实际启动可能延迟：

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

## 飞书卡片操作（无额外云服务）

Foundation 卡片不再依赖阿里云 FC、Cloudflare Workers 或其他公网回调服务。

现在使用纯跳转模式：

- **✅ 读完后标记**：跳转到对应 Foundation GitHub Issue，在论文前的任务框中手工勾选已读。
- **🔄 换一批**：跳转到 GitHub Actions 的 `Weekly Foundation Papers` 页面，点击 `Run workflow` 即可重新推荐。

手动触发 `Weekly Foundation Papers` 时，脚本会自动把**当天 Foundation Issue 中已经推荐过的所有论文**加入临时排除集合，因此连续换批不会马上重复今天已经出现过的论文。

这种模式不需要任何额外云服务，也不会产生阿里云 / Cloudflare 回调费用。



## Daily 推荐策略（D-2 + 双榜单）

Daily Track 现在优先读取 **两天前（D-2）** 的 Hugging Face Daily Papers，而不是当天早晨刚形成的列表。

原因：

- 给当天论文留出更完整的收录时间
- 给 Hugging Face upvotes 留出约 48 小时沉淀
- 仍然保持每天早晨固定推送

每天飞书会推两组，共尽量 **6 篇不同论文**：

- **🎯 就业相关 Top 3**：由 GPT-6 Luna 按 LLM 算法岗位 / JD 相关性筛选
- **🔥 HF 热度 Top 3**：按 Hugging Face upvotes 从高到低选取，并与就业 Top 3 去重

热度 Top 3 的排序由 upvotes 决定，LLM 只负责补充中文技术说明、核心贡献和阅读建议，不参与改变热度排序。

如果 D-2 当天没有 Daily Papers，脚本会继续向前查找最近一期有数据的日期。

