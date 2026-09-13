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
| 往 DSH 的 index.html 注入 `<script src="/dsh-whale/widget.js">` | `ctx.webServer.tapIndex` | 无 → 改用 SDK 贡献点：状态栏 chip + 聊天 `::whale` 指令 + ⌘K；面板走 `host.openWorkspace`（会话区右侧标签页，按需打开） |
| 取 key | `ctx.credentials.resolve('DEEPSEEK_API_KEY')` | `host.request('config.get', {key:'full'})` 读 `custom_providers[].api_key`，或用户手填 → `ctx.storage` |
| 监听会话事件结算每轮消耗 | `ctx.on('session/event')` | `host.state.focusedUsage`（实时 UsageStats，含 `cost_usd` / `total`）+ `host.state.busy` 忙转闲结算 |
| 记账落盘 `.dshw-usage.json` | 宿主 fs | `ctx.storage.get/set`（插件命名空间 `hermes.plugin.whale-widget.*`） |
| 卸载时清理 | `ctx.effect(() => () => disposers)` | `ctx.onDispose(fn)`（贡献/socket 之外的定时器、订阅清理口） |
| 前端轮询 60s / 1s | 注入脚本里的 `setInterval` | 插件内单例 `setInterval`（15s 起，默认 60s），所有挂件面共享原子状态 |
| 拖拽的浮层挂件 | DSH 页面里的自由 DOM | 插件的贡献区域里没有自由浮层（只有 statusBar / panes / palette / keybinds / themes / routes / 聊天指令）。**但 Hermes 的桌宠层有**：把立绘做成 petdex 宠物后，Shift+点击即弹出透明置顶、可拖到屏幕任意位置、位置持久化的窗口（见下节）。四边吸附 / 左吸附镜像翻转没有对应物 |
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
- **不常驻占位面板**：`panes` 贡献点在插件手里没有"显示"入口 —— core 的 `files`/`review` 各自绑了 ⌘B/⌘G，插件注册的 pane 只能靠拖布局找到，用户实际看到的是"什么都没有"（第一版就这么翻的车）。
  所以面板改成按需用 `host.openWorkspace` 打开：dock 在会话区右侧、重复调用只前置；只在没有该 API 的老桌面上才退回注册 pane。

## 桌宠：两条路，别混为一谈

原版最抓人的是"右下角一只可拖拽、点一下会说话的鲸鱼"。Hermes 里有两个都能落地的形态，
但它们的能力边界完全不同，移植时踩过：

**A. Hermes 内置宠物（petdex）** —— `agent/pet/*` + `apps/desktop/src/app/pet-overlay/*`。
宠物是 petdex 规格精灵图，住在应用窗口里，**Shift+点击** 弹出透明置顶窗口、可拖到屏幕任意位置、
位置持久化，还有单击迷你输入框 / 双击切窗口 / Alt+滚轮缩放。但：
- 气泡文案是写死在 `pet-bubble.tsx` 的 `SPECS` 里的（按状态给台词），**插件和外部都塞不进自定义文字**，
  所以"点一下显示余额"做不到；
- 应用内拖动被 `clamp()` 限制在窗口内，只有弹出来的那个窗口才自由；
- 插件上下文里**没有**任何驱动桌宠的接口（`ctx` 只有贡献点 / storage / os / i18n …）。

所以内置宠物适合"要一只跟着 agent 状态卖萌的角色"，不适合当"余额挂件"。

**B. 独立小部件窗口（`pet/whale-pet.pyw`）** —— 原版交互的复刻：Tk 起一个透明、无边框、置顶进程，
自己做拖拽 / 四边吸附 / 左吸附镜像 / 5 秒台词与余额气泡 / 60 秒刷新 / 右键大小与音效菜单，
数据只读 Hermes 的 `config.yaml`，状态写 `$HERMES_HOME/cache/whale-pet/state.json`。
它**不是插件**（插件 API 给不了自由浮层），而是一个普通 GUI 小工具 —— 想要"跟原版几乎一样"，
这条路才对。

内置宠物的精灵图由 `scripts/make-pet.py` 从同一张立绘合成；规格 8 列 × 9 行、格子 192×208、
每状态 6 帧，行序必须对齐 `agent/pet/constants.py` 的 `CODEX_STATE_ROWS`（桌面端的行序来自网关的
`pet.info.stateRows`，两者不一致动作就会串行 —— 脚本逐帧校验就是为了这个）。注意 `state_row_index()` 在
**没传行数**时按旧的 8 行分类回退，只有行数 ≥ 9 才用现行分类，调试时别被这个默认值骗了。

## 文件布局

```
plugin.js        # 单文件插件：所有挂件面 + 轮询 + 记账 + i18n（en/zh）
                 # WHALE_PNG 常量为内联 data URI，由 scripts/set-whale-image.mjs 生成
legacy-dsh/      # 上游 DSH 版原文件（lib/index.js、cordis.patch.yml、package.json、README、资源）
                 # 保留用于对照与同步 upstream：git fetch upstream && git merge upstream/main
```
