#!/usr/bin/env bash
# 把 Hermes 小鲸鱼余额挂件装进桌面端的 desktop-plugins 目录。
#   bash install.sh              只装插件
#   bash install.sh --with-skill 顺带把 ::whale 用法说明装进 skills/
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

if [ "${1:-}" = "--with-skill" ]; then
  mkdir -p "$home/skills"
  rm -rf "$home/skills/whale-widget"
  cp -r "$here/skills/whale-widget" "$home/skills/whale-widget"
  echo "✓ 技能已装到 $home/skills/whale-widget/"
fi

cat <<'EOF'

下一步：
  1. 桌面端几秒内自动加载；没出现就 ⌘K / Ctrl+K → "Reload desktop plugins"
  2. 点状态栏那只 🐳（或 ⌘K → "打开小鲸鱼挂件面板"）→ 面板 dock 在会话区右侧
  3. 面板设置区点「从 config.yaml 读取 key」（或手填 sk- key）→ 状态栏出现余额
EOF
