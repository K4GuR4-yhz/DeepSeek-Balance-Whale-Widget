---
name: whale-widget
description: "Use when asked about DeepSeek balance inside Hermes. Reads the statusbar whale."
version: 1.1.0
author: K4GuR4-yhz (Hermes port of MeteorNOX/dsh-whale-widget)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [deepseek, balance, widget, desktop-plugin, cost]
    related_skills: [hermes-token-cost-audit]
---

# 小鲸鱼余额（Hermes 状态栏）

`whale-widget` 插件在 Hermes 桌面端状态栏右侧常驻一只 🐳 显示 DeepSeek 余额。
**它只有这一个面**：没有面板、没有浮层桌宠、也没有 `::whale` 聊天指令
（那些形态做过但已按用户要求卸载）—— 所以**不要**在回答里写 `::whale`，那只会显示成一行普通文字。

## 用户问余额时怎么答

- 看状态栏的 `🐳 ¥xx.xx`；鼠标悬停给出**今日已用 / 计费时段 / 更新时间**。
- 点击鲸鱼 = 立刻刷新；`Ctrl+K` 里有 `🐳 刷新 DeepSeek 余额`（详情行就是当前余额）和
  `🐳 从 config.yaml 重读 DeepSeek key`。
- 需要精确数字时不要靠肉眼抄：用 `hermes-token-cost-audit` 技能查会话用量/成本，
  或用 terminal 直接打接口（key 在 `config.yaml` 的 `custom_providers` 里）。

## 口径（回答用户时照这个说）

- **余额**：DeepSeek 官方 `GET /user/balance`，插件默认每 60 秒刷一次。
- **今日已用**：本地记账 = 今日余额下降之和，跨天归零；中途充值不会抵消已用，
  所以它反映"钱少了多少"，不是平台用量接口的数字。
- 网络抖动时界面沿用最近一次成功的余额，只在 tooltip 里标错误码（`HTTP_401` = key 失效）。
- 想算更细的 token/成本账，配 `hermes-token-cost-audit` 一起用。
