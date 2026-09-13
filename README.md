# Hermes 小鲸鱼余额（状态栏版）

![小鲸鱼](assets/whale.png)

一只趴在 **Hermes 状态栏**上的小鲸鱼，帮你盯着 DeepSeek 余额 😺

移植自 DSH 插件 [`dsh-whale-widget`](https://github.com/MeteorNOX/DeepSeek-Balance-Whale-Widget)（MeteorNOX，MIT）。
**当前形态只做一件事**：状态栏右侧常驻余额，点击刷新，悬停看细节。
面板 / 浮层桌宠 / 内置宠物那些形态在历史提交与本仓库 `pet/`、`pets/` 里，**不在当前安装里**。

## 功能

| 功能 | 说明 |
|---|---|
| 🐳 状态栏余额 | `🐳 ¥52.42`，余额低于阈值时标「低」；点击立刻刷新 |
| 悬停细节 | 余额 · 今日已用 · 计费时段（高峰/谷价）· 更新时间 · 出错时的错误码 |
| 🔑 零配置 key | 首次运行自动从你的 `config.yaml` 读 DeepSeek 的 `sk-` key（只读，不写配置） |
| 📊 今日已用 | 余额差值记账（免令牌）：只有余额下降才算消费，充值不计负支出，跨天归零，币种切换整本重置 |
| ⏱ 自动刷新 | 默认 60 秒（15–3600 可调），网络抖动沿用上次余额、不清空 |
| ⌘K | `Ctrl+K` → `🐳 刷新 DeepSeek 余额` / `🐳 从 config.yaml 重读 DeepSeek key` |

## 安装

前提：**Hermes 桌面版**。插件目录是 `$HERMES_HOME/desktop-plugins/<id>/plugin.js`，
Windows 默认 `C:\Users\<你>\AppData\Local\hermes\desktop-plugins\`。

```bash
git clone https://github.com/K4GuR4-yhz/DeepSeek-Balance-Whale-Widget.git
cd DeepSeek-Balance-Whale-Widget
bash install.sh          # Windows: pwsh -File install.ps1
```

装完后桌面端几秒内自动加载（没出现就 `Ctrl+K` → **Reload desktop plugins**）。
状态栏右侧应该出现 `🐳 ¥…`；如果显示 `🐳 未配 key`，说明 `config.yaml` 里没有 DeepSeek 的 key，
见下面的「设置」。

## 设置

设置只有四个值，没有设置界面（保持状态栏这一个面）—— 存在插件自己的本地命名空间里，
默认值是：`apiKey`（自动从 config.yaml 读）、`baseUrl` = `https://api.deepseek.com`、
`refreshSec` = 60、`lowBalance` = 10。

- **换 key**：改 `config.yaml` 里 `custom_providers` 的 DeepSeek `api_key`，然后 `Ctrl+K` →
  `🐳 从 config.yaml 重读 DeepSeek key`。
- **改刷新间隔/阈值**：想改就直接改 `plugin.js` 顶部的 `DEFAULT_SETTINGS`（保存即热重载）。
  已经存进本地状态的值优先于默认值，要让它回默认就把插件在 **设置 → Capabilities → Plugins** 里关掉重开，
  或用 `Ctrl+K` 的 ⌘K 命令重新读一次 key。

## 数据口径

- **余额**：`GET https://api.deepseek.com/user/balance`，`Authorization: Bearer sk-…`（官方接口）。
- **今日已用**：本地记账 = 今日余额下降之和，跨天归零；中途充值不会抵消已用。
  口径是"钱少了多少"，不是平台用量接口的数字。
- **失败语义**：网络抖动沿用最近一次成功值，只在 tooltip 里标错误码（`HTTP_401` = key 不对/撤销）。

## 验证

```bash
npm run check        # node --check plugin.js —— 语法
npm run selfcheck    # 离线 17 项：SDK 导出名、register 贡献点、自动读 key、记账边界、状态栏渲染、⌘K 行
WHALE_REAL_KEY=sk-… npm run selfcheck   # 再多打一次真实 /user/balance
```

`selfcheck` 不需要装 Hermes、不碰你的真实配置：它在临时目录造一套最小 SDK 桩，
把 `plugin.js` 当 ESM 载进来跑，连渲染文案和 tooltip 都检查。退出码非 0 就是坏了。

## 仓库结构

```
plugin.js                 # ← 唯一要装的东西（单文件，13KB，无外部资源）
install.ps1 / install.sh  # 复制到 $HERMES_HOME/desktop-plugins/whale-widget/
scripts/selfcheck.mjs     # 离线自检（npm run selfcheck）
skills/whale-widget/      # 可选：给 agent 的 ::whale 用法说明（当前插件没注册这个指令）
docs/PORTING.md           # 移植笔记：上游 API 映射、取舍、踩过的坑

# —— 以下是历史形态，未安装，留着备用 ——
pet/whale-pet.pyw + 启动小鲸鱼.vbs   # 桌宠 A：原版复刻的独立浮层窗口（Tk，可拖拽/吸附/气泡）
pets/whale/               # 桌宠 B：petdex 精灵图（Hermes 内置宠物用）
scripts/make-pet.py       # 用立绘合成精灵图（Pillow，逐帧校验）
assets/whale.png          # 鲸鱼立绘（上游 DSniang1.png）
legacy-dsh/               # 上游 DSH 版原文件（对照 / 同步 upstream 用）
```

> `install.sh --with-pet` / `install.ps1 -WithPet` 仍可把桌宠 B 装上（会启用宠物层），
> `pet\启动小鲸鱼.vbs` 双击可跑桌宠 A。当前都不需要，故未启用。

## 常见问题

- **状态栏没有鲸鱼**：`设置 → Capabilities → Plugins` 里确认 `whale-widget` 是开的；或 `Ctrl+K` → Reload desktop plugins。
- **显示「未配 key」**：`config.yaml` 里没有 `custom_providers` 的 DeepSeek 条目，或 key 不是 `sk-` 开头。
- **tooltip 里是 `HTTP_401`**：key 失效/被撤销；`HTTP_403` 多为该 key 无权读余额接口。
- **今日已用一直是 0**：它靠两次观测之间的余额下降，刚装上那会儿当然是 0。
- **改了 `plugin.js` 不生效**：保存即热重载；写坏了桌面端会弹加载失败 toast，按提示改回来。

## 上游 & 许可

- 原项目：[MeteorNOX/DeepSeek-Balance-Whale-Widget](https://github.com/MeteorNOX/DeepSeek-Balance-Whale-Widget)（MIT）
- 本仓库是它的 fork + Hermes 移植，MIT 双版权见 [`LICENSE`](LICENSE)；`legacy-dsh/` 下文件版权归原作者。
