/**
 * Hermes 小鲸鱼余额（状态栏版）
 *
 * 移植自 DSH 插件 dsh-whale-widget（MeteorNOX，MIT）的最小形态：
 *   https://github.com/MeteorNOX/DeepSeek-Balance-Whale-Widget
 *
 * 就一件事：状态栏右侧显示 DeepSeek 余额，点击刷新。
 *   - 余额：GET https://api.deepseek.com/user/balance
 *   - key：首次运行时自动从 Hermes 的 config.yaml 读（custom_providers 里 base_url 含 deepseek 的那个）
 *   - 今日已用：余额差值记账（免令牌，只有下降才算消费，跨天归零，币种切换重置）
 *   - 悬停 tooltip：余额 / 今日已用 / 计费时段 / 更新时间
 *
 * 没有面板、没有浮层、没有桌宠 —— 那些形态在本仓库的历史提交里，需要时再看。
 *
 * 安装：$HERMES_HOME/desktop-plugins/whale-widget/plugin.js（或跑 install.ps1 / install.sh）
 * 加载面：仅 @hermes/plugin-sdk + react/jsx-runtime；文件不编译，用 jsx() 不用 JSX 语法。
 */

import {
  atom,
  cn,
  haptic,
  host,
  PALETTE_AREA,
  STATUSBAR_AREAS,
  Tip,
  usePluginI18n,
  useValue
} from '@hermes/plugin-sdk'
import { jsx } from 'react/jsx-runtime'

const ID = 'whale-widget'

// ── 配置 ────────────────────────────────────────────────────────────────────

const KEY_SETTINGS = 'settings'
const KEY_LEDGER = 'ledger'

const DEFAULT_SETTINGS = {
  apiKey: '',
  baseUrl: 'https://api.deepseek.com',
  refreshSec: 60,
  lowBalance: 10
}

const MIN_REFRESH_SEC = 15
const MAX_REFRESH_SEC = 3600

// DeepSeek 峰谷时段（北京时间）：工作日 9–12 / 14–18 为高峰，其余谷价；
// 2026-08-23 起周末全天谷价。只用于 tooltip 提示，不参与算钱。
const PEAK_HOURS = [
  [9, 12],
  [14, 18]
]
const WEEKEND_VALLEY_FROM_SEC = Math.floor(Date.UTC(2026, 7, 22, 16, 0, 0) / 1000)

function isPeakNow(nowSec = Date.now() / 1000) {
  const n = Number(nowSec)
  if (!isFinite(n)) return false
  const bj = new Date(n * 1000 + 8 * 3600 * 1000) // 按 UTC 读即北京日历时间
  if (n >= WEEKEND_VALLEY_FROM_SEC) {
    const dow = bj.getUTCDay()
    if (dow === 0 || dow === 6) return false
  }
  const hour = bj.getUTCHours()
  for (const [start, end] of PEAK_HOURS) {
    if (hour >= start && hour < end) return true
  }
  return false
}

// ── 状态 ────────────────────────────────────────────────────────────────────

const $settings = atom({ ...DEFAULT_SETTINGS })
const $ledger = atom({ date: '', currency: '', last: null, spent: 0 })
const $status = atom({ state: 'idle', code: '', at: 0 }) // idle | loading | ok | error
const $balance = atom(null)

let save = () => {}
let load = (key, fallback) => fallback

// ── 余额 + 记账 ─────────────────────────────────────────────────────────────

function localDateKey(d = new Date()) {
  const p = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

async function fetchBalance(settings) {
  if (!settings.apiKey) {
    const err = new Error('NO_KEY')
    err.code = 'NO_KEY'
    throw err
  }
  const base = String(settings.baseUrl || DEFAULT_SETTINGS.baseUrl).replace(/\/+$/, '')
  const res = await fetch(`${base}/user/balance`, {
    cache: 'no-store',
    headers: { Authorization: `Bearer ${settings.apiKey}` }
  })
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`)
    err.code = `HTTP_${res.status}`
    throw err
  }
  const data = await res.json()
  const info = Array.isArray(data && data.balance_infos) ? data.balance_infos[0] : null
  if (!info) {
    const err = new Error('NO_BALANCE_INFO')
    err.code = 'NO_BALANCE_INFO'
    throw err
  }
  return {
    currency: String(info.currency || 'CNY'),
    total: Number(info.total_balance),
    available: data.is_available !== false
  }
}

/**
 * 余额差值记账：跨天归零；币种变化整本重置（避免 CNY↔USD 跳变记出假账 —— 上游 #13 的坑）；
 * 只有余额下降才算消费，充值不会记成负支出。
 */
function applyLedger(prev, snapshot) {
  const date = localDateKey()
  let next = prev && typeof prev === 'object' ? { ...prev } : { date: '', currency: '', last: null, spent: 0 }
  if (next.date !== date) {
    next = { date, currency: snapshot.currency, last: snapshot.total, spent: 0 }
  } else if (next.currency !== snapshot.currency || typeof next.last !== 'number') {
    next = { date, currency: snapshot.currency, last: snapshot.total, spent: 0 }
  } else if (snapshot.total < next.last) {
    next.spent = Math.round((next.spent + (next.last - snapshot.total)) * 1e6) / 1e6
    next.last = snapshot.total
  } else {
    next.last = snapshot.total
  }
  return next
}

/** 从 Hermes 的 config.yaml 读 DeepSeek key（只读；手的形状不对就当没读到）。 */
async function keyFromConfig() {
  try {
    const res = await host.request('config.get', { key: 'full' })
    const cfg = (res && res.config) || res || {}
    const providers = Array.isArray(cfg.custom_providers) ? cfg.custom_providers : []
    const hit = providers.find(p => String((p && p.base_url) || '').includes('deepseek'))
    const key = String((hit && hit.api_key) || '').trim()
    return /^sk-/.test(key) ? key : ''
  } catch (_err) {
    return ''
  }
}

async function observe() {
  const settings = $settings.get()
  $status.set({ ...$status.get(), state: 'loading' })
  try {
    const snapshot = await fetchBalance(settings)
    const ledger = applyLedger($ledger.get(), snapshot)
    $ledger.set(ledger)
    save(KEY_LEDGER, ledger)
    const payload = { ...snapshot, today: ledger.spent }
    $balance.set(payload)
    $status.set({ state: 'ok', code: '', at: Date.now() })
    return payload
  } catch (err) {
    // 瞬时抖动沿用最近一次余额，只更新状态
    const status = { state: 'error', code: String((err && err.code) || 'ERROR'), at: Date.now() }
    $status.set(status)
    return null
  }
}

// ── 轮询（单例，跟挂了几个挂件面无关）────────────────────────────────────────

let timer = null
let unlistenSettings = null

function startPolling() {
  const restart = () => {
    if (timer) clearInterval(timer)
    const sec = Math.min(MAX_REFRESH_SEC, Math.max(MIN_REFRESH_SEC, Number($settings.get().refreshSec) || 60))
    timer = setInterval(() => void observe(), sec * 1000)
  }
  restart()
  if (!unlistenSettings) unlistenSettings = $settings.listen(restart)
  void observe()
}

// ── 展示 ────────────────────────────────────────────────────────────────────

function money(value) {
  if (value === null || value === undefined || !isFinite(Number(value))) return '--'
  return Number(value).toFixed(2)
}

function hhmm(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  const p = n => String(n).padStart(2, '0')
  return `${p(d.getHours())}:${p(d.getMinutes())}`
}

function chipLabel(t, settings, balance, status) {
  if (!settings.apiKey) return t('chipNoKey')
  if (status.state === 'error' && !balance) return t('chipError')
  if (!balance) return '🐳 --'
  return `🐳 ${balance.currency === 'CNY' ? '¥' : ''}${money(balance.total)}`
}

// ── 状态栏鲸鱼 ──────────────────────────────────────────────────────────────

function WhaleChip() {
  const t = usePluginI18n(ID)
  const settings = useValue($settings)
  const balance = useValue($balance)
  const status = useValue($status)
  const ledger = useValue($ledger)

  const low = balance && isFinite(balance.total) && balance.total <= Number(settings.lowBalance || 0)
  const tip = [
    balance ? t('tipBalance', balance.currency === 'CNY' ? '¥' : '', money(balance.total)) : t('tipNoBalance'),
    t('tipToday', ledger.currency === 'CNY' ? '¥' : '', money(ledger.spent)),
    t('tipPeak', isPeakNow() ? t('peak') : t('valley')),
    status.at ? t('tipUpdated', hhmm(status.at)) : '',
    status.state === 'error' ? t('tipError', status.code) : '',
    t('tipRefresh')
  ]
    .filter(Boolean)
    .join(' · ')

  return jsx(Tip, {
    label: tip,
    children: jsx('button', {
      type: 'button',
      onClick: () => {
        haptic('tap')
        void observe()
      },
      className: cn(
        'inline-flex h-full items-center gap-1 px-1.5 text-[0.6875rem] transition-colors',
        'text-(--ui-text-tertiary) hover:bg-(--chrome-action-hover) hover:text-foreground'
      ),
      children: [
        jsx('span', { children: chipLabel(t, settings, balance, status) }),
        low ? jsx('span', { className: 'text-(--ui-accent)', children: '低' }) : null,
        status.state === 'loading' ? jsx('span', { children: '…' }) : null
      ].filter(Boolean)
    })
  })
}

// ── 入口 ────────────────────────────────────────────────────────────────────

export default {
  id: ID,
  name: '小鲸鱼余额（状态栏）',
  register(ctx) {
    load = (key, fallback) => {
      try {
        const value = ctx.storage.get(key, fallback)
        return value === undefined || value === null ? fallback : value
      } catch (_err) {
        return fallback
      }
    }
    save = (key, value) => {
      try {
        ctx.storage.set(key, value)
      } catch (_err) {}
    }

    $settings.set({ ...DEFAULT_SETTINGS, ...load(KEY_SETTINGS, {}) })
    $ledger.set({ date: '', currency: '', last: null, spent: 0, ...load(KEY_LEDGER, {}) })

    ctx.i18n.register({
      en: {
        peak: 'peak',
        valley: 'off-peak',
        chipNoKey: '🐳 set key',
        chipError: '🐳 !',
        tipBalance: (sym, v) => `balance ${sym}${v}`,
        tipNoBalance: 'no balance yet',
        tipToday: (sym, v) => `today ${sym}${v}`,
        tipPeak: kind => `rate: ${kind}`,
        tipUpdated: at => `updated ${at}`,
        tipError: code => `error ${code}`,
        tipRefresh: 'click to refresh'
      },
      zh: {
        peak: '高峰',
        valley: '谷价',
        chipNoKey: '🐳 未配 key',
        chipError: '🐳 !',
        tipBalance: (sym, v) => `余额 ${sym}${v}`,
        tipNoBalance: '还没取到余额',
        tipToday: (sym, v) => `今日已用 ${sym}${v}`,
        tipPeak: kind => `时段：${kind}`,
        tipUpdated: at => `更新于 ${at}`,
        tipError: code => `错误 ${code}`,
        tipRefresh: '点击刷新'
      }
    })

    // 状态栏常驻鲸鱼
    ctx.register({
      id: 'chip',
      area: STATUSBAR_AREAS.right,
      order: 140,
      render: () => jsx(WhaleChip, {})
    })

    // ⌘K：刷新余额 / 重新读 key（没有面板，所以用 toast 回话）
    ctx.register({
      id: 'cmd-refresh',
      area: PALETTE_AREA,
      data: {
        id: 'whale-widget-refresh',
        label: '🐳 刷新 DeepSeek 余额',
        keywords: ['whale', 'balance', 'deepseek', '余额', '鲸鱼'],
        detail: () => {
          const balance = $balance.get()
          return balance ? `${balance.currency === 'CNY' ? '¥' : ''}${money(balance.total)}` : '—'
        },
        detailVariant: 'state',
        run: () => {
          void observe().then(result => {
            if (result) {
              host.notify({ kind: 'info', message: `🐳 余额 ${result.currency === 'CNY' ? '¥' : ''}${money(result.total)} · 今日已用 ¥${money(result.today)}` })
            } else {
              host.notify({ kind: 'error', message: `🐳 取余额失败：${$status.get().code || 'ERROR'}` })
            }
          })
        }
      }
    })

    ctx.register({
      id: 'cmd-reload-key',
      area: PALETTE_AREA,
      data: {
        id: 'whale-widget-reload-key',
        label: '🐳 从 config.yaml 重读 DeepSeek key',
        keywords: ['whale', 'key', 'config', 'deepseek', '密钥'],
        run: () => {
          void keyFromConfig().then(key => {
            if (!key) {
              host.notify({ kind: 'error', message: '🐳 没在 config.yaml 里找到 DeepSeek 的 sk- key' })
              return
            }
            const next = { ...$settings.get(), apiKey: key }
            $settings.set(next)
            save(KEY_SETTINGS, next)
            host.notify({ kind: 'info', message: `🐳 已读取 key（${key.slice(0, 6)}…${key.slice(-4)}）` })
            void observe()
          })
        }
      }
    })

    // 首次运行没存过 key：直接从 Hermes 配置里取，省得用户去别处找
    if (!$settings.get().apiKey) {
      void keyFromConfig().then(key => {
        if (!key) return
        const next = { ...$settings.get(), apiKey: key }
        $settings.set(next)
        save(KEY_SETTINGS, next)
        void observe() // 别让用户干等下一个轮询周期
      })
    }

    startPolling()
    ctx.onDispose(() => {
      if (timer) clearInterval(timer)
      timer = null
      if (unlistenSettings) unlistenSettings()
      unlistenSettings = null
    })
  }
}
