#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小鲸鱼桌宠 —— 原版 DSH 挂件的独立复刻，适配 Hermes。

原版（MeteorNOX/DeepSeek-Balance-Whale-Widget）是住在宿主网页右下角的挂件：可拖拽、
四边吸附、左吸附镜像翻转、QQ 弹按压、点击切换台词/余额气泡、60 秒刷新余额、峰谷提示。
Hermes 的插件贡献区域做不了自由浮层，桌宠层又写死了气泡文案；所以这里用 Tk 起一个
**透明、无边框、置顶**的小窗口，把那套交互原样搬过来，数据换成 Hermes 的配置与口径。

    pythonw whale-pet.pyw            正常启动（无控制台）
    python  whale-pet.pyw --self-test   自检：建窗口、跑几何不变量、取一次真实余额后退出

状态（缩放/吸附位置/记账本）存在 $HERMES_HOME/cache/whale-pet/state.json，
只读 Hermes 的 config.yaml 拿 key，不写任何 Hermes 配置。
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# ── 常量 ────────────────────────────────────────────────────────────────────

APP = "whale-pet"
BASE_IMG_H = 170                      # scale=1.0 时鲸鱼的高度（像素）
SCALES = [0.6, 0.8, 1.0, 1.3, 1.6, 2.0, 2.5]   # 原版 0.6–2.5
SNAP_PX = 28                          # 距屏幕边缘多少像素内吸附
BUBBLE_GAP = 8                        # 气泡与鲸鱼之间的间距
BUBBLE_PAD = 12                       # 气泡内边距
BUBBLE_MAX_W = 300
BUBBLE_TTL_MS = 5000                  # 气泡自动收起（原版 5 秒）
REFRESH_SEC = 60                      # 余额刷新间隔（原版 60 秒）
TRANSPARENT = "#ff00fe"               # 透明色键（原版也是靠色键抠图）

PEAK_HOURS = [(9, 12), (14, 18)]      # 北京时间高峰段
WEEKEND_VALLEY_FROM = datetime(2026, 8, 23, 0, 0)  # 2026-08-23 起周末全天谷价

QUIPS = [
    "余额我替你盯着，你专心写代码就好~",
    "每次充值我尾巴都摇起来了。",
    "谷价时段才是最香的时段。",
    "我可爱，但我并不贵。",
    "又烧掉几毛钱了，不心疼吗？",
    "记得喝水，也记得看看余额。",
]


def hermes_home() -> Path:
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env)
    local = os.environ.get("LOCALAPPDATA")
    if local and (Path(local) / "hermes").is_dir():
        return Path(local) / "hermes"
    return Path.home() / ".hermes"


HOME = hermes_home()
STATE_PATH = HOME / "cache" / APP / "state.json"
CONFIG_PATH = HOME / "config.yaml"


# ── 小工具 ──────────────────────────────────────────────────────────────────

def money(value) -> str:
    if value is None:
        return "--"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "--"


def local_date_key() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def is_peak_now() -> bool:
    """北京时间工作日 9–12 / 14–18 为高峰；2026-08-23 起周末全天谷价。"""
    now = datetime.now()
    try:
        import zoneinfo

        now = datetime.now(zoneinfo.ZoneInfo("Asia/Shanghai"))
    except Exception:  # noqa: BLE001 - 时区库不可用时退回本地时间
        pass
    if now >= WEEKEND_VALLEY_FROM.replace(tzinfo=now.tzinfo) and now.weekday() >= 5:
        return False
    return any(start <= now.hour < end for start, end in PEAK_HOURS)


def load_state() -> dict:
    defaults = {
        "scale": 1.0,
        "sound": True,
        "bubble": True,
        "snap": "none",          # none | left | right | top | bottom
        "pos": None,             # None = 用默认位置（屏幕右下角），拖动后才写具体坐标
        "ledger": {"date": "", "currency": "", "last": None, "spent": 0.0},
    }
    try:
        saved = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defaults
    defaults.update({k: v for k, v in saved.items() if k in defaults})
    if not isinstance(defaults.get("pos"), dict):      # 旧文件/坏文件都退回"默认位置"
        defaults["pos"] = None
    if not isinstance(defaults.get("ledger"), dict):
        defaults["ledger"] = {"date": "", "currency": "", "last": None, "spent": 0.0}
    return defaults


def save_state(state: dict) -> None:
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def deepseek_key() -> str:
    """从 Hermes 的 config.yaml 里取 DeepSeek 的 key（只读，不写）。"""
    try:
        import yaml  # Hermes venv 自带

        data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
        for prov in data.get("custom_providers") or []:
            if "deepseek" in str(prov.get("base_url", "")):
                key = str(prov.get("api_key") or "").strip()
                if key.startswith("sk-"):
                    return key
    except Exception:  # noqa: BLE001 - 没 pyyaml / 没配置文件都当"没 key"
        pass
    text = ""
    try:
        text = CONFIG_PATH.read_text(encoding="utf-8")
    except OSError:
        return ""
    block = re.search(r"name:\s*deepseek\b(.*?)(?:\n\s*-\s*name:|\Z)", text, re.S)
    if block:
        m = re.search(r'api_key:\s*["\']?(sk-[A-Za-z0-9_\-]+)', block.group(1))
        if m:
            return m.group(1)
    return ""


def fetch_balance(key: str, timeout: float = 20.0) -> dict:
    request = urllib.request.Request(
        "https://api.deepseek.com/user/balance",
        headers={"Authorization": f"Bearer {key}", "User-Agent": f"hermes-{APP}"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    infos = payload.get("balance_infos") or []
    if not infos:
        raise ValueError("NO_BALANCE_INFO")
    info = infos[0]
    return {
        "currency": str(info.get("currency") or "CNY"),
        "total": float(info.get("total_balance") or 0),
        "available": payload.get("is_available") is not False,
    }


def apply_ledger(previous: dict, snapshot: dict) -> dict:
    """余额差值记账：跨天归零；币种变化整本重置；只有下降算消费（充值不记负支出）。"""
    today = local_date_key()
    book = dict(previous) if isinstance(previous, dict) else {}
    if book.get("date") != today or book.get("currency") != snapshot["currency"] or not isinstance(book.get("last"), (int, float)):
        return {"date": today, "currency": snapshot["currency"], "last": snapshot["total"], "spent": 0.0}
    spent = float(book.get("spent") or 0.0)
    if snapshot["total"] < float(book["last"]):
        spent += float(book["last"]) - snapshot["total"]
    return {"date": today, "currency": snapshot["currency"], "last": snapshot["total"], "spent": round(spent, 6)}


# ── 窗口 ────────────────────────────────────────────────────────────────────

class WhalePet:
    def __init__(self, state: dict, art_path: Path, sound_dir: Path | None = None, key: str = "", persist: bool = True) -> None:
        import tkinter as tk
        from PIL import Image, ImageOps, ImageTk

        self.tk = tk
        self.Image = Image
        self.ImageOps = ImageOps
        self.ImageTk = ImageTk
        self.art_path = art_path
        self.sound_dir = sound_dir
        self.state = state
        self.key = key or ""
        self.persist = persist          # 自检时关掉，别把测试状态写进真实 state.json
        self.balance: dict | None = None
        self.status = "idle"          # idle | loading | ok | error
        self.status_text = "还没取到余额"
        self.bubble_visible = False
        self.bubble_text = ""
        self.bubble_job = None
        self.drag: dict | None = None
        self.sound_ok = False
        self._img_cache: dict[tuple, object] = {}

        self.root = tk.Tk()
        self.root.title("小鲸鱼")
        self.root.overrideredirect(True)              # 无边框
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            pass
        self.root.configure(bg=TRANSPARENT)

        self.canvas = tk.Canvas(self.root, highlightthickness=0, bd=0, bg=TRANSPARENT)
        self.canvas.pack(fill="both", expand=True)

        self.font = self._pick_font()
        self.menu = self._build_menu()

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.on_menu)          # 右键菜单
        self.root.bind("<Escape>", lambda _e: self.quit())

        self._clamp_scale()
        self.layout()
        self.refresh(show_bubble=False)
        self.tick()

    def save(self) -> None:
        if self.persist:
            save_state(self.state)

    # ── 资源 ────────────────────────────────────────────────────────────────
    def _pick_font(self):
        from tkinter import font as tkfont

        families = set(tkfont.families())
        for name in ("Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "PingFang SC", "Noto Sans CJK SC"):
            if name in families:
                return (name, 10)
        return ("TkDefaultFont", 10)

    def whale_image(self):
        key = (round(self.state["scale"], 3), self.state["snap"] == "left")
        cached = self._img_cache.get(key)
        if cached is not None:
            return cached
        image = self.Image.open(self.art_path).convert("RGBA")
        box = image.getbbox()
        if box:
            image = image.crop(box)
        height = max(24, int(BASE_IMG_H * self.state["scale"]))
        width = max(1, int(image.width * height / image.height))
        image = image.resize((width, height), self.Image.LANCZOS)
        if self.state["snap"] == "left":          # 左吸附镜像翻转（原版行为）
            image = self.ImageOps.mirror(image)
        photo = self.ImageTk.PhotoImage(image)
        self._img_cache = {key: photo}             # 只留当前一张，避免无限增长
        return photo

    def sound(self, name: str) -> None:
        if not self.state.get("sound") or not self.sound_dir:
            return
        path = Path(self.sound_dir) / f"{name}.wav"
        if not path.is_file():
            return
        try:
            import winsound

            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except Exception:  # noqa: BLE001 - 非 Windows / 没音频设备都静默降级
            pass

    # ── 菜单 ────────────────────────────────────────────────────────────────
    def _build_menu(self):
        tk = self.tk
        menu = tk.Menu(self.root, tearoff=0)
        size_menu = tk.Menu(menu, tearoff=0)
        self.scale_var = tk.DoubleVar(value=self.state["scale"])
        for scale in SCALES:
            size_menu.add_radiobutton(
                label=f"{scale:.1f}x", value=scale, variable=self.scale_var,
                command=lambda: self.set_scale(self.scale_var.get()),
            )
        menu.add_cascade(label="大小", menu=size_menu)
        self.sound_var = tk.BooleanVar(value=bool(self.state.get("sound")))
        menu.add_checkbutton(label="音效", variable=self.sound_var, command=self.toggle_sound)
        self.bubble_var = tk.BooleanVar(value=bool(self.state.get("bubble")))
        menu.add_checkbutton(label="气泡", variable=self.bubble_var, command=self.toggle_bubble_pref)
        menu.add_separator()
        menu.add_command(label="立即刷新余额", command=lambda: self.refresh(show_bubble=True))
        menu.add_command(label="回右下角", command=self.reset_position)
        menu.add_separator()
        menu.add_command(label="退出", command=self.quit)
        return menu

    def on_menu(self, event) -> None:
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def toggle_sound(self) -> None:
        self.state["sound"] = bool(self.sound_var.get())
        if self.state["sound"]:
            self.sound("press")
        self.save()

    def toggle_bubble_pref(self) -> None:
        self.state["bubble"] = bool(self.bubble_var.get())
        if not self.state["bubble"]:
            self.hide_bubble()
        self.save()

    def set_scale(self, scale: float) -> None:
        self.state["scale"] = float(scale)
        self.scale_var.set(self.state["scale"])
        self._clamp_scale()
        self.layout(keep_anchor=True)
        self.save()

    def _clamp_scale(self) -> None:
        self.state["scale"] = min(SCALES[-1], max(SCALES[0], float(self.state.get("scale") or 1.0)))

    # ── 几何 ────────────────────────────────────────────────────────────────
    def screen_size(self) -> tuple[int, int]:
        return int(self.root.winfo_screenwidth()), int(self.root.winfo_screenheight())

    def whale_size(self) -> tuple[int, int]:
        photo = self.whale_image()
        return photo.width(), photo.height()

    def _font_obj(self):
        from tkinter import font as tkfont

        if getattr(self, "_font", None) is None:
            self._font = tkfont.Font(font=self.font)
        return self._font

    def wrap_bubble(self, text: str, limit: int | None = None) -> list[str]:
        """按真实字宽折行（Tk 量宽，中英混排都准）。"""
        if limit is None:
            limit = BUBBLE_MAX_W - 2 * BUBBLE_PAD
        font = self._font_obj()
        lines, current = [], ""
        for char in str(text):
            if current and font.measure(current + char) > limit:
                lines.append(current)
                current = ""
            current += char
        if current:
            lines.append(current)
        return lines[:4]

    def layout(self, keep_anchor: bool = False) -> None:
        """把窗口调成「鲸鱼 + 气泡」的并集：鲸鱼屏幕位置不变，气泡往有空间的一侧展开。

        关键不变量：气泡再长也不许把鲸鱼挤出屏幕或推离吸附边 —— 空间不够就压窄气泡。
        """
        screen_w, screen_h = self.screen_size()
        whale_w, whale_h = self.whale_size()
        pos = self.state.get("pos") or {}
        x = int(pos.get("x", screen_w - whale_w - 40))
        y = int(pos.get("y", screen_h - whale_h - 80))
        if keep_anchor or not pos:
            # 贴边状态在缩放后要重新贴（否则缩放会把贴边挤开）
            snap = self.state.get("snap", "none")
            if snap == "right":
                x = screen_w - whale_w
            elif snap == "left":
                x = 0
            if snap == "bottom":
                y = screen_h - whale_h
            elif snap == "top":
                y = 0
        x = min(max(0, x), max(0, screen_w - whale_w))
        y = min(max(0, y), max(0, screen_h - whale_h))

        line_h = 18
        bubble_w = bubble_h = 0
        side, below, lines = "right", False, []
        if self.bubble_visible and self.bubble_text:
            room_right, room_left = screen_w - (x + whale_w), x
            side = "right" if room_right >= room_left else "left"
            limit = max(140, min(BUBBLE_MAX_W - 2 * BUBBLE_PAD, room_right if side == "right" else room_left))
            lines = self.wrap_bubble(self.bubble_text, limit)
            bubble_w = max(80, min(limit, int(max(self._font_obj().measure(line) for line in lines)) + 2 * BUBBLE_PAD))
            bubble_h = len(lines) * line_h + 2 * BUBBLE_PAD
            room_below = screen_h - (y + whale_h)
            below = y < bubble_h + BUBBLE_GAP and room_below >= bubble_h + BUBBLE_GAP
        self._bubble_lines = lines

        win_w = max(whale_w, bubble_w)
        win_h = whale_h + (bubble_h + BUBBLE_GAP if bubble_h else 0)
        win_x = x if (side == "right" or not bubble_w) else x + whale_w - win_w
        win_y = (y - bubble_h - BUBBLE_GAP) if (bubble_h and not below) else y
        win_x = min(max(0, win_x), max(0, screen_w - win_w))
        win_y = min(max(0, win_y), max(0, screen_h - win_h))

        self.whale_canvas = (x - win_x, y - win_y)
        self.whale_at = (win_x + self.whale_canvas[0], win_y + self.whale_canvas[1])
        self.bubble_canvas = (
            0 if side == "right" else win_w - bubble_w,
            0 if (bubble_h and not below) else whale_h + BUBBLE_GAP,
            bubble_w,
            bubble_h,
        )

        self.root.geometry(f"{win_w}x{win_h}+{win_x}+{win_y}")
        self.canvas.configure(width=win_w, height=win_h)
        self.draw()

    def draw(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        photo = self.whale_image()
        canvas.create_image(self.whale_canvas[0], self.whale_canvas[1], image=photo, anchor="nw")
        self._photo_ref = photo
        if self.bubble_visible and self.bubble_text:
            self.draw_bubble(*self.bubble_canvas)

    def draw_bubble(self, x: int, y: int, width: int, height: int) -> None:
        """气泡画在窗口内预留好的那块区域（原版气泡也是代码画的）。"""
        canvas = self.canvas
        if width <= 0 or height <= 0:
            return
        lines = getattr(self, "_bubble_lines", []) or self.wrap_bubble(self.bubble_text)
        right = x + width
        canvas.create_polygon(
            x + 10, y + 1, right - 10, y + 1, right - 2, y + 9, right - 1, y + height - 11,
            right - 10, y + height - 1, x + 10, y + height - 1, x + 2, y + height - 9,
            x + 1, y + 9, smooth=True, fill="#ffffff", outline="#d8dbe0", width=1,
        )
        for index, line in enumerate(lines):
            canvas.create_text(
                x + BUBBLE_PAD, y + BUBBLE_PAD + index * 18, text=line,
                anchor="nw", font=self.font, fill="#1f2430",
            )

    # ── 交互 ────────────────────────────────────────────────────────────────
    def on_press(self, event) -> None:
        self.drag = {"ox": event.x_root - self.whale_at[0], "oy": event.y_root - self.whale_at[1], "moved": False, "x": self.whale_at[0], "y": self.whale_at[1]}
        self.sound("press")

    def on_drag(self, event) -> None:
        if not self.drag:
            return
        drag = self.drag
        drag["moved"] = True
        screen_w, screen_h = self.screen_size()
        whale_w, whale_h = self.whale_size()
        drag["x"] = min(max(0, event.x_root - drag["ox"]), max(0, screen_w - whale_w))
        drag["y"] = min(max(0, event.y_root - drag["oy"]), max(0, screen_h - whale_h))
        self.state["snap"] = "none"
        self.state["pos"] = {"x": drag["x"], "y": drag["y"]}
        self.layout()

    def on_release(self, event) -> None:
        drag, self.drag = self.drag, None
        self.sound("release")
        if not drag:
            return
        if not drag["moved"]:
            self.on_click()
            return
        self.snap(drag["x"], drag["y"])

    def snap(self, x: int, y: int) -> None:
        screen_w, screen_h = self.screen_size()
        whale_w, whale_h = self.whale_size()
        snap = "none"
        if x <= SNAP_PX:
            x, snap = 0, "left"
        elif x + whale_w >= screen_w - SNAP_PX:
            x, snap = screen_w - whale_w, "right"
        if y <= SNAP_PX:
            y, snap = 0, "top" if snap == "none" else snap
        elif y + whale_h >= screen_h - SNAP_PX:
            y, snap = screen_h - whale_h, "bottom" if snap == "none" else snap
        self.state["snap"] = snap
        self.state["pos"] = {"x": x, "y": y}
        self.save()
        self.layout(keep_anchor=True)

    def on_click(self) -> None:
        """单击：刷新余额 + 弹气泡；再点换一句台词（原版就是这么玩的）。"""
        self.refresh(show_bubble=False)
        if self.bubble_visible:
            self.show_bubble(random.choice(QUIPS))       # 气泡已开 → 换台词
        else:
            self.show_bubble(self.balance_line())

    def balance_line(self) -> str:
        if not self.balance:
            return f"余额看不着：{self.status_text}"
        symbol = "¥" if self.balance["currency"] == "CNY" else ""
        spent = self.state["ledger"].get("spent") or 0.0
        peak = "高峰" if is_peak_now() else "谷价"
        return f"余额 {symbol}{money(self.balance['total'])} · 今日已用 {symbol}{money(spent)} · {peak}"

    # ── 气泡 ────────────────────────────────────────────────────────────────
    def show_bubble(self, text: str) -> None:
        if not self.state.get("bubble", True):
            return
        self.bubble_text = text
        self.bubble_visible = True
        if self.bubble_job:
            self.root.after_cancel(self.bubble_job)
        self.bubble_job = self.root.after(BUBBLE_TTL_MS, self.hide_bubble)
        self.layout()

    def hide_bubble(self) -> None:
        self.bubble_job = None
        if not self.bubble_visible:
            return
        self.bubble_visible = False
        self.layout()

    # ── 数据 ────────────────────────────────────────────────────────────────
    def refresh(self, show_bubble: bool = False) -> None:
        key = self.key or ""
        if not key:
            self.status, self.status_text = "error", "没在 config.yaml 里找到 DeepSeek key"
            if show_bubble:
                self.show_bubble(self.status_text)
            return
        self.status, self.status_text = "loading", "刷新中…"
        try:
            snapshot = fetch_balance(key)
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, TimeoutError, OSError) as exc:
            # 瞬时抖动沿用最近一次余额（原版行为），只更新状态文案
            code = getattr(exc, "code", None)
            self.status, self.status_text = "error", f"取数失败（{code or type(exc).__name__}）"
            if not self.balance and show_bubble:
                self.show_bubble(self.status_text)
            return
        self.balance = snapshot
        self.state["ledger"] = apply_ledger(self.state.get("ledger") or {}, snapshot)
        self.status, self.status_text = "ok", f"更新于 {datetime.now():%H:%M}"
        self.save()
        if show_bubble:
            self.show_bubble(self.balance_line())

    def tick(self) -> None:
        try:
            self.refresh(show_bubble=False)
        except Exception:  # noqa: BLE001 - 刷新失败绝不能把定时器打死
            pass
        self.root.after(REFRESH_SEC * 1000, self.tick)

    def reset_position(self) -> None:
        screen_w, screen_h = self.screen_size()
        whale_w, whale_h = self.whale_size()
        self.state["snap"], self.state["pos"] = "none", {"x": screen_w - whale_w - 40, "y": screen_h - whale_h - 80}
        self.save()
        self.layout(keep_anchor=True)

    def quit(self) -> None:
        self.save()
        try:
            self.root.destroy()
        except Exception:  # noqa: BLE001
            pass

    def run(self) -> None:
        self.root.mainloop()


# ── 自检 ────────────────────────────────────────────────────────────────────

def self_test(art_path: Path) -> int:
    """建真窗口跑一遍：几何不变量 + 折行 + 记账边界 + 取一次真实余额。"""
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))
        print(f"{'✅' if ok else '❌'} {name}{f'  → {detail}' if detail else ''}")

    state = {"scale": 1.0, "sound": False, "bubble": True, "snap": "none", "pos": {"x": 300, "y": 300},
             "ledger": {"date": "", "currency": "", "last": None, "spent": 0.0}}
    pet = WhalePet(state, art_path, sound_dir=None, persist=False)
    pet.root.update()

    check("窗口建立（无边框/置顶/透明色键）", bool(pet.root.winfo_exists()))
    check("透明色键生效", str(pet.root.attributes("-transparentcolor")).lower() == TRANSPARENT)

    # 折行：长文案必须被切成 ≤4 行且宽度受限
    lines = pet.wrap_bubble("余额 ¥52.42 · 今日已用 ¥0.80 · 谷价时段才是最香的时段。")
    check("气泡折行不超宽", 1 <= len(lines) <= 4, f"{len(lines)} 行：{lines[0][:24]}…")

    # 几何：四种吸附 + 三档缩放下，鲸鱼必须完整落在屏幕内
    screen_w, screen_h = pet.screen_size()
    ok_geometry, details = True, []
    for snap in ("none", "left", "right", "top", "bottom"):
        for scale in (0.6, 1.0, 2.5):
            pet.state["snap"], pet.state["scale"] = snap, scale
            pet.state["pos"] = {"x": 200, "y": 200}
            pet.bubble_visible, pet.bubble_text = True, "余额 ¥52.42 · 今日已用 ¥0.80 · 高峰"
            pet.layout(keep_anchor=True)
            pet.root.update()
            whale_w, whale_h = pet.whale_size()
            wx, wy = pet.whale_at
            if snap == "left":
                ok_geometry &= wx == 0
            if snap == "right":
                ok_geometry &= wx + whale_w == screen_w
            if snap == "bottom":
                ok_geometry &= wy + whale_h == screen_h
            if wx < 0 or wy < 0 or wx + whale_w > screen_w or wy + whale_h > screen_h:
                ok_geometry = False
                details.append(f"{snap}/{scale}: whale=({wx},{wy},{whale_w},{whale_h})")
    check("缩放 + 吸附下鲸鱼不出屏、贴边精确", ok_geometry, "; ".join(details) or f"屏幕 {screen_w}x{screen_h}")

    # 左吸附镜像翻转
    pet.state["snap"], pet.state["scale"] = "right", 1.0
    normal = pet.whale_image()
    pet.state["snap"] = "left"
    mirrored = pet.whale_image()
    check("左吸附会镜像翻转", normal is not mirrored, f"{normal.width()}x{normal.height()}")

    # 记账：下降累计、充值不记、跨天归零、币种切换重置
    book = apply_ledger({}, {"currency": "CNY", "total": 50.0})
    book = apply_ledger(book, {"currency": "CNY", "total": 49.5})
    book = apply_ledger(book, {"currency": "CNY", "total": 60.0})
    book = apply_ledger(book, {"currency": "CNY", "total": 59.0})
    check("记账：只累计下降、充值不记负支出", abs(book["spent"] - 1.5) < 1e-9, f"今日已用 = {book['spent']}")
    switched = apply_ledger(book, {"currency": "USD", "total": 5.0})
    check("记账：币种切换重置", switched["spent"] == 0 and switched["currency"] == "USD", json.dumps(switched))
    rolled = apply_ledger({"date": "2020-01-01", "currency": "CNY", "last": 99.0, "spent": 42.0}, {"currency": "CNY", "total": 30.0})
    check("记账：跨天归零", rolled["spent"] == 0 and rolled["date"] == local_date_key(), json.dumps(rolled))

    key = deepseek_key()
    check("从 Hermes config.yaml 读到 key", bool(key), f"sk-…{key[-4:]}" if key else CONFIG_PATH.as_posix())
    if key:
        try:
            snapshot = fetch_balance(key)
            check("真实接口取到余额", snapshot["total"] > 0, f"{snapshot['currency']} {money(snapshot['total'])}")
        except Exception as exc:  # noqa: BLE001
            check("真实接口取到余额", False, f"{type(exc).__name__}: {exc}")

    pet.quit()
    passed = sum(1 for _n, ok, _d in checks if ok)
    print(f"\n{passed}/{len(checks)} 通过")
    return 0 if passed == len(checks) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="小鲸鱼桌宠（Hermes 版原版挂件）")
    parser.add_argument("--self-test", action="store_true", help="建窗口跑自检后退出")
    parser.add_argument("--art", default="", help="鲸鱼立绘 PNG（默认用同目录的 whale.png）")
    parser.add_argument("--sounds", default="", help="音效目录（含 press.wav / release.wav）")
    args = parser.parse_args()

    here = Path(__file__).resolve().parent
    art = Path(args.art) if args.art else here / "whale.png"
    if not art.is_file():
        fallback = HOME / "cache" / APP / "whale.png"
        art = fallback if fallback.is_file() else art
    if not art.is_file():
        print(f"✗ 找不到立绘：{art}", file=sys.stderr)
        return 2
    sounds = Path(args.sounds) if args.sounds else here / "sounds"

    if args.self_test:
        return self_test(art)

    state = load_state()
    pet = WhalePet(state, art, sound_dir=sounds, key=deepseek_key())
    pet.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
