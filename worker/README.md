# 飞书交互回调

当前正在迁移华为云，函数代码已上传，但公网入口被独立计费的 APIG 专享网关要求阻塞，尚未切换飞书配置。继续工作参见 [FunctionGraph 迁移状态](FUNCTIONGRAPH.md)。下文保留原部署背景，不代表当前交互可用。

业务逻辑位于 `index.js`，`fc.mjs` 仅将阿里云 FC 3.0 的 HTTP 事件转换为相同处理逻辑使用的 Request/Response。

当前目标部署：Cloudflare Workers Free，`daily-paper-feishu-callback`。执行 `npm install`、`npx wrangler login`、`npm run deploy`，用 Wrangler Secrets 配置凭证。

Worker 地址：`https://daily-paper-feishu-callback.twyran.workers.dev`。本地及线上 challenge 正常；飞书保存两次均超时且 tail 未收到对应请求，迁移仍被网络可达性阻塞。账号没有托管域名或 Worker 自定义域名，下一步需取得可绑定域名后再次验证，不能宣称已切换成功。

飞书已发布配置仍指向原 FC 地址；用户报告 FC 因欠费停止服务。FC 适配代码保留作为历史部署入口，下述打包命令仅用于该入口。

同一天换批复用当天 Issue。`foundation_paper.py` 在发送卡片前补齐新论文的 checkbox，保留已有阅读状态；回归检查：`python -m unittest test_foundation_progress`。

新卡片的 reroll 按钮累积本次工作流的 `FOUNDATION_EXCLUDE_IDS` 和当前论文 ID，并去重传给下一次 workflow_dispatch；推荐 prompt 和论文池不变。

```sh
npm install
npm run build:fc
```

将 `dist/fc/index.mjs` 放在 ZIP 根目录上传。不要把环境变量、密钥或整个工作目录打包。

函数环境变量：`GITHUB_REPOSITORY=twyran/Daily-Paper`；`GITHUB_PAT`、`FEISHU_OPEN_ID` 由用户在平台配置；可选 `FEISHU_VERIFICATION_TOKEN` 校验实际交互回调。PAT 仅授权本仓库的 Issues、Actions 读写权限。

使用无需平台鉴权的公网 HTTP 触发器，由业务代码限制操作人。challenge 优先直接返回 200 JSON，不做 GitHub 请求；支持顶层 `challenge` 和 `event.challenge`。

飞书配置入口：事件与回调 → 回调配置 → 将回调发送至开发者服务器；订阅 `card.action.trigger`，修改后发布版本。

Cloudflare challenge 在任何 GitHub 请求之前直接返回，不存在顶层网络请求、重定向或自动重试。

FC 默认 `fcapp.run` 域名仅供测试，长期使用需绑定自定义域名；当前用户尚无域名。加密回调解密尚未实现，不要启用 Encrypt Key 后直接沿用本处理程序。
