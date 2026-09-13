# Hermes 小鲸鱼余额挂件

![小鲸鱼](assets/whale.png)

一只住在 **Hermes 桌面版**状态栏里的小鲸鱼娘，帮你盯着 DeepSeek 账户余额 😺

移植自 DSH 插件 [`dsh-whale-widget`](https://github.com/MeteorNOX/DeepSeek-Balance-Whale-Widget)（MeteorNOX，MIT）。
上游是 DeepSeek Harness 的宿主插件 + 页面注入脚本；这里按 Hermes 桌面版插件 SDK 重写，
单文件、热重载、无独立进程。鲸鱼立绘与音效沿用上游 MIT 资源。

## 功能

| 功能 | 说明 |
|---|---|
| 🐳 状态栏常驻 | 余额直接显示在状态栏右侧，点击即刷新；余额低时标「低」 |
| 🗂 挂件面板 | 右侧区块的一个 tab（可拖到任意区块）：余额大字、今日已用、本轮消耗、计费时段、设置 |
| 💬 聊天内鲸鱼 | 对话里写 `::whale`（单独一行），鲸鱼卡片就画在消息里 |
| 📊 今日已用 | **余额差值记账**（免令牌）：每次观测余额后按差值累计，只有下降才算消费；跨天归零，充值不计成负支出 |
| 💵 本轮消耗 | 读 Hermes 会话 usage（`cost_usd` + tokens），按会话分桶，不跟子代理串账 |
| 💬 消耗提示 | 可选：每轮对话结束弹一条「本轮 $x.xxxx · N tokens · 今日 ¥y」 |
| ⏰ 峰谷时段 | 工作日 9:00–12:00 / 14:00–18:00 判定为高峰（北京时间），2026-08-23 起周末全天谷价 |
| ⌘K 命令 | `🐳 刷新 DeepSeek 余额`，详情行显示当前余额 |
| 🎛 设置 | key、刷新间隔、低价阈值、状态栏开关、消耗提示开关，全部本地持久化（插件命名空间，不写 config.yaml） |

## 安装

前提：**Hermes 桌面版**（`hermes desktop`）。插件目录是 `$HERMES_HOME/desktop-plugins/<id>/plugin.js`，
Windows 默认 `C:\Users\<你>\AppData\Local\hermes\desktop-plugins\`。

### 一键（Windows PowerShell）

```powershell
git clone https://github.com/K4GuR4-yhz/DeepSeek-Balance-Whale-Widget.git
cd DeepSeek-Balance-Whale-Widget
pwsh -File install.ps1
```

### 一键（Linux / macOS / git-bash）

```bash
git clone https://github.com/K4GuR4-yhz/DeepSeek-Balance-Whale-Widget.git
cd DeepSeek-Balance-Whale-Widget
bash install.sh
```

### 手动

把 `plugin.js` 放进 `desktop-plugins/whale-widget/plugin.js`（**目录名必须等于插件 id `whale-widget`**）：

```bash
mkdir -p "$HERMES_HOME/desktop-plugins/whale-widget"
cp plugin.js "$HERMES_HOME/desktop-plugins/whale-widget/plugin.js"
```

装完后桌面端几秒内自动加载；没出现就 ⌘K / Ctrl+K → **Reload desktop plugins**，
再不行去 **设置 → Capabilities → Plugins** 看 `whale-widget` 是否被关掉了。

## 用起来

1. 打开挂件面板（状态栏鲸鱼点一下只是刷新；面板在右侧区块的 `whale` tab，或被自动放到右侧区域），
2. 设置区点 **从 config.yaml 读取 key** —— 直接拿 Hermes 已配置的 DeepSeek key（不落盘、不新写配置）；
   也可以手动粘 `sk-` key，点保存。
3. 面板顶部鲸鱼头点一下 = 手动刷新。之后每 60 秒自动刷新（间隔可改，最小 15 秒）。

给 agent 用：把 `skills/whale-widget/` 复制到 `$HERMES_HOME/skills/`，agent 就知道可以在回答里插 `::whale` 卡片。

## 设置项

| 设置 | 默认 | 说明 |
|---|---|---|
| API key | 空 | `api.deepseek.com` 的 `sk-` key；只存在插件自己的本地命名空间 |
| 刷新间隔 | 60 秒 | 15–3600；余额下降靠这个节奏记账 |
| 低于此值提醒 | 10 | 状态栏与面板金额转为强调色，并标「低」 |
| 状态栏常驻 | 开 | 关掉后只剩面板 / 聊天卡片 |
| 每轮消耗弹提示 | 关 | 打开后每轮结束弹一条 toast |

## 数据口径

- **余额**：`GET https://api.deepseek.com/user/balance`，`Authorization: Bearer sk-…`（DeepSeek 官方接口）。
  网络抖动时沿用最近一次成功值，不会把 UI 打回空值。
- **今日已用**：本地记账，不是平台用量接口。口径 = 今日余额下降之和，跨天归零；币种变化只重置基准不记差值
  （避免 CNY↔USD 跳变记出假账 —— 上游 issue #13 的同款坑）。
  注意：**中途充值不会抵消已记的已用**，这正是想要的；但如果你今天手工改过账户金额，记账会跟着偏。
- **本轮消耗**：Hermes 上报的会话 usage（`cost_usd`、`total` tokens），按会话 id 分桶，
  以 `busy` 由忙转闲为界结算一轮。金额单位是 Hermes 报的 USD，和账户 CNY 余额不是一套口径，所以分开显示。

## 与原版的差异

| 上游 DSH 版 | 本 Hermes 版 |
|---|---|
| 宿主侧插件：`ctx.webServer.register` 8 条路由 + `ctx.webServer.tapIndex` 注入脚本 | 桌面插件 SDK：状态栏贡献 + pane + 聊天指令 + ⌘K 命令（无服务端、无注入） |
| 需 `DEEPSEEK_PLATFORM_TOKEN` 才能算今日已用（会话令牌，会过期） | 只靠余额差值记账，**不需要任何令牌** |
| 前端脚本轮询 `/dsh-whale/*.json` | 插件内单例轮询，所有挂件面共享同一份状态 |
| 拖拽 + 四边吸附 + 左吸附镜像翻转的浮层 | ❌ 做不了：Hermes 插件只能注册状态栏 / pane / ⌘K / 快捷键 / 主题，没有自由浮层 API |
| 音效（小黄鸭 / 音效1） | 暂未实现（上游 mp3 保留在 `legacy-dsh/assets/`，想要可以加） |
| 随机台词 | 保留了 4 句，按日期+余额轮换（不跑定时器） |
| `dsh plugin add` 安装 | `install.ps1` / `install.sh` 复制到 `desktop-plugins/` |

完整对照（含 API 映射与取舍）见 [`docs/PORTING.md`](docs/PORTING.md)。

## 常见问题

- **状态栏没鲸鱼**：`设置 → Capabilities → Plugins` 里确认 `whale-widget` 是开的；或 ⌘K → Reload desktop plugins。
- **鲸鱼显示「未配 key」**：面板里点「从 config.yaml 读取 key」，或手动粘贴。
- **余额取不到（`HTTP_401`）**：key 不对或已撤销；`HTTP_403` 多为该 key 无权读取余额接口（换成主账号 key）。
- **今日已用是 0**：记账需要两次观测之间的余额下降，刚装上的头一分钟当然是 0。
- **改了 `plugin.js` 不生效**：保存即热重载，不需要重启；如果文件写坏了，桌面端会弹加载失败 toast，按提示改回去。
- **换了鲸鱼图**：把新 PNG 放到 `assets/whale.png` 后 `npm run set-image`（= `node scripts/set-whale-image.mjs`），
  它会重新内联进 `plugin.js`（桌面插件只能加载单文件，图片必须走 data URI）。

## 仓库结构

```
plugin.js                 # 插件本体（单文件，图片已内联）—— 这就是要装的东西
assets/whale.png          # 鲸鱼立绘（上游 DSniang1.png，缩到 320px）
scripts/set-whale-image.mjs  # 换图后重新内联
install.ps1 / install.sh  # 安装到 $HERMES_HOME/desktop-plugins/
skills/whale-widget/      # 给 agent 的 ::whale 用法说明（可选安装）
legacy-dsh/               # 上游 DSH 版原文件（对照 / 同步 upstream 用，不参与 Hermes 运行）
docs/PORTING.md           # 移植笔记：API 映射、取舍、做不了的部分
```

## 上游 & 许可

- 原项目：[MeteorNOX/DeepSeek-Balance-Whale-Widget](https://github.com/MeteorNOX/DeepSeek-Balance-Whale-Widget)（MIT）
- 本仓库是它的 fork + Hermes 桌面版移植，MIT 双版权见 [`LICENSE`](LICENSE)。
- `legacy-dsh/` 下的文件版权归原作者，未做改动。
