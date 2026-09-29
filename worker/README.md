# 飞书交互回调

业务逻辑位于 `index.js`，`fc.mjs` 仅将阿里云 FC 3.0 的 HTTP 事件转换为相同处理逻辑使用的 Request/Response。

目前测试部署：阿里云 FC，杭州地域，函数 `daily-paper-feishu-callback`，Node.js 20，入口 `index.handler`。

回调地址：`https://daily-pcallback-jmxxwrgaat.cn-hangzhou.fcapp.run`。已在飞书保存验证并发布；真实卡片点击已确认可以更新 Issue 和触发带排除列表的 workflow_dispatch。

同一天换批复用当天 Issue。`foundation_paper.py` 在发送卡片前补齐新论文的 checkbox，保留已有阅读状态；回归检查：`python -m unittest test_foundation_progress`。

```sh
npm install
npm run build:fc
```

将 `dist/fc/index.mjs` 放在 ZIP 根目录上传。不要把环境变量、密钥或整个工作目录打包。

函数环境变量：`GITHUB_REPOSITORY=twyran/Daily-Paper`；`GITHUB_PAT`、`FEISHU_OPEN_ID` 由用户在平台配置；可选 `FEISHU_VERIFICATION_TOKEN` 校验实际交互回调。PAT 仅授权本仓库的 Issues、Actions 读写权限。

使用无需平台鉴权的公网 HTTP 触发器，由业务代码限制操作人。challenge 优先直接返回 200 JSON，不做 GitHub 请求；支持顶层 `challenge` 和 `event.challenge`。

飞书配置入口：事件与回调 → 回调配置 → 将回调发送至开发者服务器；订阅 `card.action.trigger`，修改后发布版本。

Cloudflare 旧部署保留。迁移原因：实时日志可见对照 GET/challenge 请求，但飞书保存地址超时时没有 POST 到达 Worker。

FC 默认 `fcapp.run` 域名仅供测试，长期使用需绑定自定义域名；当前用户尚无域名。加密回调解密尚未实现，不要启用 Encrypt Key 后直接沿用本处理程序。
