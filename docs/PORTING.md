# 移植笔记：DSH 插件 → Hermes 桌面插件

上游 [`dsh-whale-widget`](https://github.com/MeteorNOX/DeepSeek-Balance-Whale-Widget) 是
DeepSeek Harness 的 bundle 插件（cordis 契约：`export { name, inject, apply }`，
`package.json` 的 `dsh.bundle.patch` 把 `cordis.patch.yml` 插进 web profile 的配置树）。
Hermes 没有 cordis 配置树、没有 `ctx.webServer` / `ctx.credentials` / `session/event` 这些宿主 API，
也没有 `dsh` CLI，所以**原包在 Hermes 里到不了加载那一步**，只能按能力重新实现。

## API 映射

| 上游做的事 | 上游 API | Hermes 对应 |
|---|---|---|
| 注册 `/dsh-whale/balance.json` 等 8 条 HTTP 路由 | `ctx.webServer.register` | 无（渲染层直接 `fetch` DeepSeek 官方接口；CORS 可用） |
| 往 DSH 的 index.html 注入 `<script src="/dsh-whale/widget.js">` | `ctx.webServer.tapIndex` | 无 → 改为 SDK 贡献点：状态栏 / pane / 聊天指令 |
| 取 key | `ctx.credentials.resolve('DEEPSEEK_API_KEY')` | `host.request('config.get', {key:'full'})` 读 `custom_providers[].api_key`，或用户手填 → `ctx.storage` |
| 监听会话事件结算每轮消耗 | `ctx.on('session/event')` | `host.state.focusedUsage`（实时 UsageStats，含 `cost_usd` / `total`）+ `host.state.busy` 忙转闲结算 |
| 记账落盘 `.dshw-usage.json` | 宿主 fs | `ctx.storage.get/set`（插件命名空间 `hermes.plugin.whale-widget.*`） |
| 卸载时清理 | `ctx.effect(() => () => disposers)` | `ctx.onDispose(fn)`（贡献/socket 之外的定时器、订阅清理口） |
| 前端轮询 60s / 1s | 注入脚本里的 `setInterval` | 插件内单例 `setInterval`（15s 起，默认 60s），所有挂件面共享原子状态 |
| 拖拽 + 四边吸附 + 左吸附镜像翻转的浮层 | DSH 页面里的自由 DOM | ❌ 做不了。Hermes 插件的贡献区域只有 statusBar / panes / palette / keybinds / themes / routes / 聊天指令，没有自由浮层 |
| 音效 | `/dsh-whale/sound/*.mp3` | 未实现（上游 mp3 在 `legacy-dsh/assets/`，要加就在按压处理器里 `new Audio(dataURI)`，注意默认静音） |

## 保持了上游行为的几处细节

1. **余额抖动沿用最近值**：取数失败不清空 UI，只记状态（对应上游「瞬时网络抖动自动沿用最近余额不报错」）。
2. **币种感知记账**：币种变化只重置基准、不记差值 —— 上游 issue #13 的假账根因（CNY↔USD 随机切换时
   单日记出数千元）。这里同样只认「同币种内的连续下降」。
3. **按会话分桶**：上游用 `Map` 分桶避免主会话与多子代理并行时串账；这里按 `focusedSessionId` 分桶，
   并只在 `busy` 由忙转闲时结算一轮。
4. **峰谷时段**：沿用上游的判定（工作日 9–12 / 14–18 为高峰，北京时间；2026-08-23 起周末全天谷价）。
   上游用它换算金额，这里只用于显示当前处在哪一档；金额用 Hermes 报的 `cost_usd`，比按 token 重算更准。
5. **免令牌**：上游「实时·令牌」模式需要平台会话令牌（会过期）；Hermes 侧只保留记账模式，
   今日已用 = 今日余额下降之和，零凭据依赖。

## 有意不做的事

- **不给渲染层塞 key 到源码里**：key 只走 `ctx.storage`（插件自己的本地命名空间）。
- **不写任何 Hermes 核心配置**：不动 `config.yaml`、不动 `.env`；「从 config.yaml 读取 key」只是**读**。
- **不加后台常驻进程**：插件随桌面端启停（进程内模型）；要脱离 Hermes 常驻得另做独立托盘程序，那是另一个项目。

## 文件布局

```
plugin.js        # 单文件插件：所有挂件面 + 轮询 + 记账 + i18n（en/zh）
                 # WHALE_PNG 常量为内联 data URI，由 scripts/set-whale-image.mjs 生成
legacy-dsh/      # 上游 DSH 版原文件（lib/index.js、cordis.patch.yml、package.json、README、资源）
                 # 保留用于对照与同步 upstream：git fetch upstream && git merge upstream/main
```
