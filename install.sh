#!/usr/bin/env bash
# 把 Hermes 小鲸鱼余额挂件装进桌面端的 desktop-plugins 目录。
#   bash install.sh              只装插件
#   bash install.sh --with-skill 顺带把 ::whale 用法说明装进 skills/
#   bash install.sh --with-pet   顺带把小鲸鱼装成桌宠（petdex 规格精灵图）并设为当前桌宠
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

home="${HERMES_HOME:-}"
if [ -z "$home" ]; then
  case "$(uname -s)" in
    MINGW* | MSYS* | CYGWIN*) home="${LOCALAPPDATA:-$HOME/AppData/Local}/hermes" ;;
    *) home="$HOME/.hermes" ;;
  esac
fi

dest="$home/desktop-plugins/whale-widget"
mkdir -p "$dest"
cp "$here/plugin.js" "$dest/plugin.js"
echo "✓ 插件已装到 $dest/plugin.js"

for flag in "$@"; do
  case "$flag" in
    --with-skill)
      mkdir -p "$home/skills"
      rm -rf "$home/skills/whale-widget"
      cp -r "$here/skills/whale-widget" "$home/skills/whale-widget"
      echo "✓ 技能已装到 $home/skills/whale-widget/"
      ;;
    --with-pet)
      pet_dir="$home/pets/whale"
      mkdir -p "$pet_dir"
      if [ ! -f "$here/pets/whale/spritesheet.webp" ]; then
        echo "… 精灵图不在，试着生成（需要 Pillow）"
        python "$here/scripts/make-pet.py" >/dev/null
      fi
      cp "$here/pets/whale/pet.json" "$here/pets/whale/spritesheet.webp" "$pet_dir/"
      echo "✓ 桌宠已装到 $pet_dir/"
      if command -v hermes >/dev/null 2>&1; then
        hermes pets select whale || echo "  （自动设为当前桌宠失败，手动跑：hermes pets select whale）"
      else
        echo "  手动设为当前桌宠：hermes pets select whale"
      fi
      ;;
  esac
done

cat <<'EOF'

下一步：
  1. 桌面端几秒内自动加载；没出现就 Ctrl+K → "Reload desktop plugins"
  2. 点状态栏那只 🐳（或 Ctrl+K → "打开小鲸鱼挂件面板"）→ 面板 dock 在会话区右侧
  3. 面板设置区点「从 config.yaml 读取 key」（或手填 sk- key）→ 状态栏出现余额
  4. 桌宠模式：Shift+点击宠物 → 弹成悬浮桌宠，拖到任意位置；`hermes pets off` 关掉
EOF
