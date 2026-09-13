---
name: whale-widget
description: "Use when showing DeepSeek balance/usage in chat. Emits the ::whale card."
version: 1.0.0
author: K4GuR4-yhz (Hermes port of MeteorNOX/dsh-whale-widget)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [deepseek, balance, widget, desktop-plugin, cost]
    related_skills: [hermes-token-cost-audit]
---

# 小鲸鱼余额挂件（hermes-whale-widget）

桌面端装了 `whale-widget` 插件时，可以在回答里插入一张鲸鱼卡片，显示当前 DeepSeek 余额、
今日已用和计费时段。**只有插件在跑的时候才有意义**——没装就是一行普通文字，不会报错。

## 怎么用

在回答里单独占一行写：

```
::whale
```

规则（宿主强制）：

- 这些指令必须**独占一个段落**，混在句子里就是普通文本。
- 卡片内容由插件实时渲染，你不用也不能传参数。
- 一次回答最多放一张，放在相关结论旁边，别当装饰。

## 何时用

- 用户问余额 / 花了多少 / 还能撑多久。
- 长任务收尾时顺带报一眼余额（用户明确表示关心的时候）。

## 何时别用

- 用户没问余额，也没在跑长任务 —— 别硬塞。
- 每轮都插：那是噪音。

## 数据口径（回答用户时照这个说）

- **余额**：DeepSeek 官方 `GET /user/balance`，插件每 60 秒刷一次（状态栏点击可手动刷）。
- **今日已用**：本地记账 = 今日余额下降之和，跨天归零；中途充值不会抵消已用。
- **本轮消耗**：Hermes 上报的会话 `cost_usd`（USD）与 tokens，和账户 CNY 余额不是一套口径。
- 想算更细的 token/成本账，配 `hermes-token-cost-audit` 技能一起用。
