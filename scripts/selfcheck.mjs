#!/usr/bin/env node
/**
 * 离线自检：在 node 里加载 plugin.js（用最小 SDK 桩），跑通 register、记账数学、
 * 各挂件面渲染、每轮消耗结算；顺手核对 import 的 SDK 名字是否真实存在。
 *
 *   npm run selfcheck                 # 全离线
 *   WHALE_REAL_KEY=sk-… npm run selfcheck   # 额外打一次真实 /user/balance
 *
 * 装不上、改坏了、想确认要不要 commit 之前都跑一下。退出码 0 = 全过。
 */
import { cpSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const repo = resolve(dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')), '..')

// ── 找 Hermes 源码（只用来核对 SDK 导出名；找不到就跳过那两项）─────────────────
function findSdkSource() {
  const candidates = [
    process.env.HERMES_SRC && join(process.env.HERMES_SRC, 'apps/desktop/src/sdk/index.ts'),
    process.env.HERMES_HOME && join(process.env.HERMES_HOME, 'hermes-agent/apps/desktop/src/sdk/index.ts'),
    process.env.LOCALAPPDATA && join(process.env.LOCALAPPDATA, 'hermes/hermes-agent/apps/desktop/src/sdk/index.ts'),
    join(process.env.HOME ?? '', '.hermes/hermes-agent/apps/desktop/src/sdk/index.ts')
  ].filter(Boolean)
  for (const path of candidates) {
    try {
      readFileSync(path)
      return path
    } catch (_err) {}
  }
  return null
}

// ── 工作目录 + SDK 桩 ───────────────────────────────────────────────────────
const work = mkdtempSync(join(tmpdir(), 'whale-selfcheck-'))

const SDK_STUB = `
export const BUNDLES = {}
export function atom(initial) {
  let value = initial
  const subs = new Set()
  return {
    get: () => value,
    set: next => { value = next; for (const fn of subs) { try { fn(next) } catch (_e) {} } },
    listen: fn => { subs.add(fn); return () => subs.delete(fn) },
    subscribe: fn => { subs.add(fn); return () => subs.delete(fn) }
  }
}
export const computed = fn => ({ get: fn })
export const host = {
  state: { focusedSessionId: atom('sess-1'), focusedUsage: atom(null), busy: atom(false) },
  notify: msg => { (globalThis.__WHALE_NOTIFS__ ??= []).push(msg) },
  request: async () => ({ config: globalThis.__WHALE_CONFIG__ ?? {} }),
  onEvent: () => () => {},
  logs: () => {},
  openWorkspace: (id, options) => {
    ;(globalThis.__WHALE_OPENED__ ??= []).push({ id, options })
    return () => {}
  }
}
export const useValue = a => (a && typeof a.get === 'function' ? a.get() : a)
export const usePluginI18n = () => (key, ...args) => {
  const bundle = BUNDLES[globalThis.__WHALE_LOCALE__ ?? 'zh'] ?? BUNDLES.en ?? {}
  const value = bundle[key]
  if (typeof value === 'function') return value(...args)
  return value === undefined ? key : value
}
export const cn = (...parts) => parts.filter(Boolean).join(' ')
export const haptic = () => {}
export const Badge = 'Badge'
export const Button = 'Button'
export const Input = 'Input'
export const Switch = 'Switch'
export const Separator = 'Separator'
export const Tip = 'Tip'
export const Tooltip = 'Tooltip'
export const STATUSBAR_AREAS = { left: 'statusBar.left', right: 'statusBar.right' }
export const PANES_AREA = 'panes'
export const PALETTE_AREA = 'palette'
export const TRANSCRIPT_DIRECTIVE_AREA = 'transcript-directive'
`

const REACT_STUB = `
export const useState = initial => [typeof initial === 'function' ? initial() : initial, () => {}]
export const useEffect = () => {}
export const useMemo = fn => fn()
export const useCallback = fn => fn
export const useRef = value => ({ current: value })
`

const JSX_STUB = `
export const jsx = (type, props) => ({ type, props: props ?? {} })
export const jsxs = jsx
export const Fragment = 'Fragment'
`

mkdirSync(join(work, 'node_modules/@hermes/plugin-sdk'), { recursive: true })
mkdirSync(join(work, 'node_modules/react'), { recursive: true })
writeFileSync(join(work, 'node_modules/@hermes/plugin-sdk/package.json'), JSON.stringify({ name: '@hermes/plugin-sdk', type: 'module', main: 'index.js' }))
writeFileSync(join(work, 'node_modules/@hermes/plugin-sdk/index.js'), SDK_STUB)
writeFileSync(
  join(work, 'node_modules/react/package.json'),
  JSON.stringify({ name: 'react', type: 'module', exports: { '.': './index.js', './jsx-runtime': './jsx-runtime.js', './jsx-dev-runtime': './jsx-runtime.js' } })
)
writeFileSync(join(work, 'node_modules/react/index.js'), REACT_STUB)
writeFileSync(join(work, 'node_modules/react/jsx-runtime.js'), JSX_STUB)
cpSync(join(repo, 'plugin.js'), join(work, 'plugin-under-test.mjs'))

const results = []
const nativeFetch = globalThis.fetch
const check = (name, ok, detail = '') => {
  results.push({ name, ok: Boolean(ok) })
  console.log(`${ok ? '✅' : '❌'} ${name}${detail ? `  → ${detail}` : ''}`)
}

const pluginSrc = readFileSync(join(repo, 'plugin.js'), 'utf8')

// ── 1. 静态检查 ─────────────────────────────────────────────────────────────
const sdkPath = findSdkSource()
const ALLOWED = new Set(['@hermes/plugin-sdk', 'react', 'react/jsx-runtime', 'react/jsx-dev-runtime'])
const specifiers = [...pluginSrc.matchAll(/from\s*'([^']+)'/g)].map(m => m[1])
check('import 只用允许的模块', specifiers.every(s => ALLOWED.has(s)), [...new Set(specifiers)].join(', '))

if (sdkPath) {
  const sdkSrc = readFileSync(sdkPath, 'utf8')
  const exported = new Set()
  for (const m of sdkSrc.matchAll(/^export\s+(?:const|function|class|async function)\s+([A-Za-z0-9_$]+)/gm)) exported.add(m[1])
  for (const m of sdkSrc.matchAll(/^export\s*\{([\s\S]*?)\}\s*from/gm)) {
    for (const raw of m[1].split(',')) {
      const name = raw.trim().replace(/^type\s+/, '').split(/\s+as\s+/).pop().trim()
      if (/^[A-Za-z_$][\w$]*$/.test(name)) exported.add(name)
    }
  }
  const names = [...pluginSrc.matchAll(/^import\s*\{([\s\S]*?)\}\s*from\s*'@hermes\/plugin-sdk'/gm)]
    .flatMap(m => m[1].split(','))
    .map(s => s.trim())
    .filter(Boolean)
  const missing = names.filter(n => !exported.has(n))
  check(`SDK import 全是真实导出（${names.length} 个）`, missing.length === 0, missing.join(', ') || 'all present')
} else {
  console.log('⏭  跳过 SDK 导出名核对：没找到 Hermes 源码（设 HERMES_SRC 指向 hermes-agent 目录）')
}

// ── 2. 载入插件 ─────────────────────────────────────────────────────────────
const sdk = await import(pathToFileURL(join(work, 'node_modules/@hermes/plugin-sdk/index.js')).href)

const balanceFixture = (currency, total) => ({
  is_available: true,
  balance_infos: [{ currency, total_balance: String(total), granted_balance: '0.00', topped_up_balance: String(total) }]
})

function makeCtx() {
  const store = {}
  const contribs = []
  const disposers = []
  return {
    store,
    contribs,
    disposers,
    ctx: {
      source: 'plugin:whale-widget',
      register: c => {
        contribs.push(c)
        return () => {}
      },
      registerMany: cs => {
        contribs.push(...cs)
        return () => {}
      },
      onDispose: fn => disposers.push(fn),
      rest: async () => ({}),
      socket: () => () => {},
      os: {},
      storage: {
        get: (k, fallback) => (k in store ? store[k] : fallback),
        set: (k, v) => {
          store[k] = v
        },
        remove: k => {
          delete store[k]
        }
      },
      i18n: {
        register: bundles => {
          for (const [locale, table] of Object.entries(bundles)) sdk.BUNDLES[locale] = table
        }
      }
    }
  }
}

const freshPlugin = async () => (await import(`${pathToFileURL(join(work, 'plugin-under-test.mjs')).href}?v=${Date.now()}${Math.random()}`)).default

function treeText(node, depth = 0) {
  if (node === null || node === undefined || depth > 12) return ''
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(n => treeText(n, depth + 1)).join(' ')
  if (typeof node === 'object') {
    const own = node.props ? treeText(node.props.children, depth + 1) : ''
    if (typeof node.type === 'function') {
      try {
        return [own, treeText(node.type(node.props ?? {}), depth + 1)].join(' ')
      } catch (err) {
        return `${own} [render-error:${err.message}]`
      }
    }
    return own
  }
  return ''
}

function findHandler(node, key, depth = 0) {
  if (!node || typeof node !== 'object' || depth > 12) return null
  if (Array.isArray(node)) {
    for (const child of node) {
      const hit = findHandler(child, key, depth + 1)
      if (hit) return hit
    }
    return null
  }
  if (node.props && typeof node.props[key] === 'function') return node.props[key]
  if (typeof node.type === 'function') {
    try {
      const hit = findHandler(node.type(node.props ?? {}), key, depth + 1)
      if (hit) return hit
    } catch (_err) {
      return null
    }
  }
  return node.props ? findHandler(node.props.children, key, depth + 1) : null
}

async function scenario({ fixtures, presetStore = {} }) {
  let call = 0
  globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => fixtures[Math.min(call++, fixtures.length - 1)] })
  const bag = makeCtx()
  if (presetStore.ledger) bag.ctx.storage.set('ledger', presetStore.ledger)
  bag.ctx.storage.set('settings', { apiKey: 'sk-selfcheck', ...(presetStore.settings || {}) })
  const plugin = await freshPlugin()
  plugin.register(bag.ctx)
  bag.wait = () => new Promise(r => setTimeout(r, 30))
  await bag.wait()
  return bag
}

// ── 3. 运行期检查 ───────────────────────────────────────────────────────────
globalThis.__WHALE_LOCALE__ = 'zh'

let bag = await scenario({ fixtures: [balanceFixture('CNY', 53.22)] })
check('register() 跑通并注册贡献点', bag.contribs.length === 4, bag.contribs.map(c => c.id).join(', '))
check('初始观测写入账本', bag.store.ledger?.currency === 'CNY' && bag.store.ledger?.spent === 0, JSON.stringify(bag.store.ledger))

// 同一天：下降 → 持平 → 充值 → 再下降
{
  const chip = bag.contribs.find(c => c.id === 'chip')
  const onClick = findHandler(chip.render(), 'onClick')
  check('状态栏鲸鱼带点击刷新处理器', typeof onClick === 'function')

  let call = 0
  const seq = [53.22, 52.22, 52.22, 60.0, 59.5]
  globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => balanceFixture('CNY', seq[Math.min(call++, seq.length - 1)]) })
  for (let i = 0; i < seq.length; i++) {
    onClick()
    await bag.wait()
  }
  check('记账：只累计下降、充值不记负支出', Math.abs(bag.store.ledger.spent - 1.5) < 1e-9, `今日已用 = ${bag.store.ledger.spent}`)
  const chipText = treeText(chip.render())
  check('状态栏渲染出鲸鱼与余额', chipText.includes('🐳') && chipText.includes('59.50'), chipText.trim().slice(0, 60))
}

// 币种切换：整本重置，不串币种
{
  bag = await scenario({
    fixtures: [balanceFixture('CNY', 38.82)],
    presetStore: { ledger: { date: new Date().toISOString().slice(0, 10), currency: 'CNY', last: 40.0, spent: 1.18 } }
  })
  const chip = bag.contribs.find(c => c.id === 'chip')
  const onClick = findHandler(chip.render(), 'onClick')
  let call = 0
  const currencies = ['CNY', 'CNY', 'USD', 'USD']
  const amounts = [38.82, 38.82, 5.0, 4.0]
  globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => balanceFixture(currencies[call], amounts[call++]) })
  onClick()
  await bag.wait()
  onClick()
  await bag.wait()
  onClick()
  await bag.wait()
  const afterSwitch = bag.store.ledger
  onClick()
  await bag.wait()
  check(
    '币种切换不虚记（上游 #13 的坑）',
    afterSwitch.currency === 'USD' && afterSwitch.spent === 0 && Math.abs(bag.store.ledger.spent - 1.0) < 1e-9,
    `切换后 spent=${afterSwitch.spent}，切后消费=${bag.store.ledger.spent}`
  )
}

// 跨天归零
{
  bag = await scenario({
    fixtures: [balanceFixture('CNY', 30.0)],
    presetStore: { ledger: { date: '2020-01-01', currency: 'CNY', last: 99.0, spent: 42.0 } }
  })
  check('跨天账本归零', bag.store.ledger.spent === 0 && bag.store.ledger.date !== '2020-01-01', JSON.stringify(bag.store.ledger))
}

// 面板入口 / 聊天卡片 / ⌘K
{
  bag = await scenario({ fixtures: [balanceFixture('CNY', 53.22)] })
  globalThis.__WHALE_OPENED__ = []
  findHandler(bag.contribs.find(c => c.id === 'chip').render(), 'onClick')()
  const opened = globalThis.__WHALE_OPENED__[0]
  check(
    '点鲸鱼以右侧 workspace 标签页打开面板',
    opened?.id === 'whale-widget:panel' && opened.options.dock?.pos === 'right' && typeof opened.options.render === 'function',
    opened ? `${opened.id} dock=${opened.options.dock?.pos}` : 'not opened'
  )
  const paneText = treeText(opened.options.render()).replace(/\s+/g, ' ')
  check(
    '面板渲染中文标签与余额',
    paneText.includes('今日已用') && paneText.includes('本轮消耗') && paneText.includes('53.22') && !paneText.includes('render-error'),
    paneText.slice(0, 90)
  )
  const directive = bag.contribs.find(c => c.id === 'directive')
  check('::whale 指令已注册且能渲染', directive.data?.name === 'whale' && treeText(directive.data.render()).includes('余额 ¥53.22'))
  const palette = bag.contribs.find(c => c.id === 'cmd-refresh')
  check('⌘K 命令带实时详情', typeof palette.data.detail === 'function' && palette.data.detail().includes('53.22'), palette.data.detail())

  // 每轮消耗：先有上一轮累计做基准，busy 拉高，usage 上升，busy 落下结算
  bag = await scenario({ fixtures: [balanceFixture('CNY', 53.22)], presetStore: { settings: { turnToast: true } } })
  sdk.host.state.focusedUsage.set({ calls: 1, input: 3000, output: 800, total: 5000, cost_usd: 0.05 })
  sdk.host.state.busy.set(true)
  await bag.wait()
  sdk.host.state.focusedUsage.set({ calls: 2, input: 4000, output: 1000, total: 6200, cost_usd: 0.06 })
  await bag.wait()
  sdk.host.state.busy.set(false)
  await bag.wait()
  const notifs = globalThis.__WHALE_NOTIFS__ ?? []
  check(
    '每轮消耗结算并弹提示',
    notifs.some(n => String(n.message).includes('本轮消耗') && String(n.message).includes('1,200')),
    notifs.map(n => n.message).join(' | ') || 'no toast'
  )

  let threw = null
  try {
    for (const fn of bag.disposers) fn()
  } catch (err) {
    threw = err
  }
  check('onDispose 清理不抛错', !threw, threw ? String(threw) : 'ok')
}

// ── 4. 真实接口（可选）──────────────────────────────────────────────────────
if (process.env.WHALE_REAL_KEY) {
  globalThis.fetch = nativeFetch
  const bag2 = makeCtx()
  bag2.ctx.storage.set('settings', { apiKey: process.env.WHALE_REAL_KEY })
  const plugin = await freshPlugin()
  plugin.register(bag2.ctx)
  await new Promise(r => setTimeout(r, 2000))
  const text = treeText(bag2.contribs.find(c => c.id === 'chip').render()).replace(/\s+/g, ' ').trim()
  check('真实接口取到余额', /¥\d/.test(text), `${text.slice(0, 40)} | ledger=${JSON.stringify(bag2.store.ledger)}`)
}

// ── 收工 ────────────────────────────────────────────────────────────────────
try {
  rmSync(work, { recursive: true, force: true })
} catch (_err) {}

const passed = results.filter(r => r.ok).length
console.log(`\n${passed}/${results.length} 通过${passed === results.length ? ' 🐳' : ''}`)
process.exit(passed === results.length ? 0 : 1)
