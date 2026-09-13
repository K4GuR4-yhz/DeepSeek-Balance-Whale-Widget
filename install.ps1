# Hermes 小鲸鱼余额挂件 — Windows 安装脚本
#   pwsh -File install.ps1                只装插件
#   pwsh -File install.ps1 -WithSkill     顺带把 ::whale 用法说明装进 skills/
#   pwsh -File install.ps1 -WithPet       顺带把小鲸鱼装成桌宠并设为当前桌宠
param([switch]$WithSkill, [switch]$WithPet)

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

if ($WithPet) {
  $petDir = Join-Path $home_ 'pets\whale'
  New-Item -ItemType Directory -Force -Path $petDir | Out-Null
  $sheet = Join-Path $here 'pets\whale\spritesheet.webp'
  if (-not (Test-Path $sheet)) {
    Write-Host "… 精灵图不在，试着生成（需要 Pillow）"
    python (Join-Path $here 'scripts\make-pet.py') | Out-Null
  }
  Copy-Item -Force (Join-Path $here 'pets\whale\pet.json'), $sheet $petDir
  Write-Host "✓ 桌宠已装到 $petDir\"
  try { hermes pets select whale } catch { Write-Host "  手动设为当前桌宠：hermes pets select whale" }
}

@'

下一步：
  1. 桌面端几秒内自动加载；没出现就 Ctrl+K → "Reload desktop plugins"
  2. 状态栏右侧应出现 🐳 余额：点击刷新，悬停看今日已用 / 计费时段 / 更新时间
  3. 显示「未配 key」时：确认 config.yaml 里有 DeepSeek 的 custom_providers.api_key，
     然后 Ctrl+K → "从 config.yaml 重读 DeepSeek key"
'@ | Write-Host
