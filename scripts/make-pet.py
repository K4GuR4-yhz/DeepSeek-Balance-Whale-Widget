#!/usr/bin/env python3
"""把小鲸鱼立绘做成 Hermes / petdex 规格的宠物精灵图（桌面桌宠）。

产物：pets/whale/spritesheet.png（1536x1872，8 列 x 9 行，格子 192x208，每状态 6 帧）
      pets/whale/pet.json

行序（自上而下，agent/pet/constants.py 的 CODEX_STATE_ROWS）：
  idle, running-right, running-left, waving, jumping, failed, waiting, running, review

用法：  python scripts/make-pet.py [--art 图片] [--out 目录]
需要 Pillow（Hermes 自带的 venv 里就有）。
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps

FRAME_W, FRAME_H = 192, 208
COLS, ROWS, FRAMES = 8, 9, 6          # 6 帧真用，后 2 列留透明（渲染器按空列提前停）
STATE_ROWS = ["idle", "running-right", "running-left", "waving", "jumping", "failed", "waiting", "running", "review"]
ART_H = 164                            # 立绘在格子里的高度，余量留给浮动/旋转（±7° 也不出格）
FLOOR = 6                              # 底边留白，别贴死格子底

REPO = Path(__file__).resolve().parents[1]


def load_art(path: Path):
    image = Image.open(path).convert("RGBA")
    if box := image.getbbox():
        image = image.crop(box)
    scale = ART_H / image.height
    return image.resize((max(1, round(image.width * scale)), ART_H), Image.LANCZOS)


def transform(art: Image.Image, *, angle=0.0, sx=1.0, sy=1.0, mirror=False, desat=None):
    image = art.transpose(Image.FLIP_LEFT_RIGHT) if mirror else art
    if sx != 1.0 or sy != 1.0:
        image = image.resize((max(1, round(image.width * sx)), max(1, round(image.height * sy))), Image.LANCZOS)
    if angle:
        # expand=True：返回紧贴旋转后图形的画布。千万别用 pad+rotate(expand=False) ——
        # 那样画布被撑大，底部对齐就会把鲸鱼顶到格子外面去（第一版就是这么翻的）。
        image = image.rotate(angle, resample=Image.BICUBIC, expand=True)
    if desat:
        grey = ImageOps.grayscale(image.convert("RGB")).convert("RGBA")
        grey.putalpha(image.getchannel("A"))
        image = Image.blend(image, grey, desat)
    return image


def composite_at(frame: Image.Image, image: Image.Image, x: int, y: int) -> None:
    """把 image 贴到 frame 的 (x, y)，越界部分裁掉（PIL 的 alpha_composite 不吃负坐标）。"""
    sx, sy = max(0, -x), max(0, -y)
    dx, dy = max(0, x), max(0, y)
    w = min(image.width - sx, frame.width - dx)
    h = min(image.height - sy, frame.height - dy)
    if w <= 0 or h <= 0:
        return
    frame.alpha_composite(image.crop((sx, sy, sx + w, sy + h)), (dx, dy))


def cell(art: Image.Image, *, dy=0, dx=0, **kwargs) -> Image.Image:
    frame = Image.new("RGBA", (FRAME_W, FRAME_H), (0, 0, 0, 0))
    image = transform(art, **kwargs)
    composite_at(frame, image, (FRAME_W - image.width) // 2 + dx, FRAME_H - image.height - FLOOR + dy)
    return frame


def wave(i, n, amp, phase=0.0):
    """一圈正弦，取 n 个采样点。"""
    return amp * math.sin((i / n) * 2 * math.pi + phase)


def animations():
    """每个状态 6 帧的参数。用同一张立绘做出「会呼吸的桌宠」是靠位移/挤压/旋转。"""
    out: dict[str, list[dict]] = {}

    # 待机：上下呼吸 + 极轻微挤压
    out["idle"] = [
        {"dy": round(wave(i, 6, 4)), "sy": 1 - 0.012 * abs(math.sin(i / 6 * 2 * math.pi))} for i in range(6)
    ]
    # 跑动：上下颠 + 前后倾
    run = [{"dy": -abs(round(wave(i, 6, 6))), "dx": round(wave(i, 6, 2)), "angle": wave(i, 6, 5)} for i in range(6)]
    out["running-right"] = run
    out["running-left"] = [dict(params, mirror=True) for params in run]
    out["running"] = run
    # 招手：左右摇摆
    out["waving"] = [{"dy": round(wave(i, 6, 3)), "angle": wave(i, 6, 7)} for i in range(6)]
    # 跳跃：起跳-腾空-落地，带挤压拉伸
    out["jumping"] = [
        {"dy": 4, "sy": 0.94, "sx": 1.06},
        {"dy": -10, "sy": 1.06, "sx": 0.96},
        {"dy": -22, "sy": 1.02},
        {"dy": -14, "sy": 1.0, "angle": -6},
        {"dy": 0, "sy": 0.92, "sx": 1.08},
        {"dy": 0},
    ]
    # 失败：左右抖 + 掉色
    out["failed"] = [
        {"dx": -4, "angle": -4, "desat": 0.75},
        {"dx": 4, "angle": 4, "desat": 0.75},
        {"dx": -3, "angle": -3, "desat": 0.6},
        {"dx": 3, "angle": 3, "desat": 0.6},
        {"dx": -1, "desat": 0.45},
        {"dx": 0, "desat": 0.35},
    ]
    # 等待：慢悠悠地晃
    out["waiting"] = [{"dy": round(wave(i, 6, 2)), "angle": wave(i, 6, 4, math.pi / 3)} for i in range(6)]
    # 思考/复查：点头
    out["review"] = [{"angle": max(0.0, wave(i, 6, 7, math.pi)) - 3.5, "dy": round(wave(i, 6, 2, math.pi))} for i in range(6)]

    return out


def build(art: Image.Image) -> tuple[Image.Image, dict[str, int], list[str]]:
    sheet = Image.new("RGBA", (FRAME_W * COLS, FRAME_H * ROWS), (0, 0, 0, 0))
    anims = animations()
    stats: dict[str, int] = {}
    problems: list[str] = []
    for row, state in enumerate(STATE_ROWS):
        frames = anims.get(state, anims["idle"])
        drawn = 0
        for col in range(min(FRAMES, len(frames))):
            frame = cell(art, **frames[col])
            # 每一帧都验：不为空、没被格子切顶、落点在格子下半部分
            box = frame.getchannel("A").getbbox()
            if box is None:
                problems.append(f"{state}[{col}] 空白帧")
                continue
            if box[1] <= 0:
                problems.append(f"{state}[{col}] 顶部被切 box={box}")
            if box[3] < 150 or (box[3] - box[1]) < 60:
                problems.append(f"{state}[{col}] 落点异常 box={box}")
            sheet.alpha_composite(frame, (col * FRAME_W, row * FRAME_H))
            drawn += 1
        stats[state] = drawn
    return sheet, stats, problems


def main() -> int:
    parser = argparse.ArgumentParser(description="生成小鲸鱼桌宠精灵图")
    parser.add_argument("--art", default=str(REPO / "legacy-dsh/assets/DSniang1.png"), help="鲸鱼立绘（透明背景 PNG）")
    parser.add_argument("--out", default=str(REPO / "pets/whale"), help="输出目录")
    args = parser.parse_args()

    art_path, out_dir = Path(args.art), Path(args.out)
    if not art_path.is_file():
        print(f"✗ 找不到立绘：{art_path}")
        return 1

    art = load_art(art_path)
    sheet, stats, problems = build(art)
    out_dir.mkdir(parents=True, exist_ok=True)
    # petdex 用 webp：无损、体积约 PNG 的 1/3，store 两种都认
    sheet_path = out_dir / "spritesheet.webp"
    sheet.save(sheet_path, format="WEBP", lossless=True, quality=100, method=6)
    (out_dir / "pet.json").write_text(
        json.dumps(
            {
                "id": "whale",
                "displayName": "小鲸鱼",
                "description": "一只帮你盯着 DeepSeek 余额的小鲸鱼娘（来自 DeepSeek-Balance-Whale-Widget，MIT）",
                "spritesheetPath": sheet_path.name,
                "createdBy": "hermes-whale-widget",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    size = sheet_path.stat().st_size
    print(f"✓ {sheet_path}  {sheet.width}x{sheet.height}  {size/1024:.0f} KB")
    for state, drawn in stats.items():
        print(f"   {state:15s} {drawn}/{FRAMES} 帧非空")
    empty = [s for s, n in stats.items() if n == 0]
    if empty:
        print(f"✗ 这些行是空的（渲染时只会回退到 idle）：{', '.join(empty)}")
    if problems:
        print(f"✗ {len(problems)} 帧有问题：")
        for problem in problems[:12]:
            print(f"   {problem}")
    return 1 if (empty or problems) else 0


if __name__ == "__main__":
    raise SystemExit(main())
