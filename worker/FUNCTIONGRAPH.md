# 华为云 FunctionGraph 迁移

代码已上传到华北-北京四（cn-north-4）的 `daily-paper-feishu-callback`。HTTP 函数使用 128MB、按需执行、无预留实例，不开启 VPC、LTS 或其他常驻资源。业务逻辑复用 `index.js`，`functiongraph.mjs` 只做 HTTP 适配；Node.js 20.15 由 `bootstrap` 启动，监听 127.0.0.1:8000。

## 当前阻塞

函数内部健康检查成功，但迁移尚未完成，没有公网回调 URL。当前账号的 HTTP 触发器仅提供 APIG 专享版，未提供函数 URL 入口；专享版网关会独立计费，不符合本项目不创建持续计费资源的要求，因此没有创建。需要先向华为云确认账号是否可开通无需专享网关的函数 URL；否则应重新决定部署平台或明确接受网关成本。

尚未配置敏感环境变量，尚未修改飞书回调地址。不能将函数计算免费额度理解为网关也免费。只有公网入口通过验证、真实卡片按钮测试成功后，才能宣布华为云为主方案、FC 已退役。

## 打包与配置

执行 `npm install`、`npm run build:functiongraph`。ZIP 根目录仅放 `dist/functiongraph/index.mjs` 和 `worker/bootstrap`；bootstrap 采用 LF 换行和可执行权限。勿打包环境变量或凭证。

在平台配置 `GITHUB_REPOSITORY=twyran/Daily-Paper`，由用户输入 `GITHUB_PAT` 和 `FEISHU_OPEN_ID`，可选 `FEISHU_VERIFICATION_TOKEN`。PAT 仅授权本仓库 Issues、Actions 读写。

本地 HTTP 测试验证 GET、顶层/新版 challenge、未知操作。challenge 不调用第三方服务。核心业务模拟测试验证 mark_read 和累计排除列表 dispatch；这些不能代替公网及飞书端到端测试。

Cloudflare 与 FC 适配入口仍保留，推荐 prompt、论文池与工作流逻辑未改动。
