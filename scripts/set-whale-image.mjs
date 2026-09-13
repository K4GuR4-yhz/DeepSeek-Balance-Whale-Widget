/**
 * 把一张 PNG 内联进 plugin.js 的 WHALE_PNG 常量（桌面插件只能加载单文件，
 * 资源必须走 data URI）。
 *
 *   node scripts/set-whale-image.mjs [图片路径]
 *
 * 不传路径时用 assets/whale.png。换图建议先缩到 ~320px 宽（base64 会膨胀 ~33%）。
 */
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const repo = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const imagePath = resolve(process.argv[2] || resolve(repo, 'assets', 'whale.png'))
const pluginPath = resolve(repo, 'plugin.js')

const base64 = readFileSync(imagePath).toString('base64')
const source = readFileSync(pluginPath, 'utf8')
const marker = /(const WHALE_PNG = 'data:image\/png;base64,)[^']*(')/

if (!marker.test(source)) {
  console.error('plugin.js 里找不到 WHALE_PNG 常量，先确认文件没被改坏。')
  process.exit(1)
}

writeFileSync(pluginPath, source.replace(marker, `$1${base64}$2`))
console.log(`已内联 ${imagePath}（${base64.length} 字符 base64）→ plugin.js`)
