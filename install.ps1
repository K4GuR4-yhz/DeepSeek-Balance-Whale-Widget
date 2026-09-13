# Hermes 小鲸鱼余额挂件 — Windows 安装脚本
#   pwsh -File install.ps1              只装插件
#   pwsh -File install.ps1 -WithSkill   顺带把 ::whale 用法说明装进 skills/
param([switch]$WithSkill)

$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$home_ = $env:HERMES_HOME
if (-not $home_) { $home_ = Join-Path $env:LOCALAPPDATA 'hermes' }

$dest = Join-Path $home_ 'desktop-plugins\whale-widget'
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item -Force (Join-Path $here 'plugin.js') (Join-Path $dest 'plugin.js')
Write-Host "✓ 插件已装到 $dest\plugin.js"

if ($WithSkill) {
  $skills = Join-Path $home_ 'skills'
  New-Item -ItemType Directory -Force -Path $skills | Out-Null
  $target = Join-Path $skills 'whale-widget'
  if (Test-Path $target) { Remove-Item -Recurse -Force $target }
  Copy-Item -Recurse -Force (Join-Path $here 'skills\whale-widget') $target
  Write-Host "✓ 技能已装到 $target\"
}

@'

下一步：
  1. 桌面端几秒内自动加载；没出现就 Ctrl+K → "Reload desktop plugins"
  2. 点状态栏那只 🐳（或 Ctrl+K → "打开小鲸鱼挂件面板"）→ 面板 dock 在会话区右侧
  3. 面板设置区点「从 config.yaml 读取 key」（或手填 sk- key）→ 状态栏出现余额
'@ | Write-Host
