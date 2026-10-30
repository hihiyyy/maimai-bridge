/**
 * Host half of the 麦麦 settings page.
 *
 * Registers a same-origin HTTP prefix that the Client half talks to, and runs
 * the three bridge scripts (maimai.py / emit_preset.py) on demand.
 *
 * Everything the UI can change is persisted to
 * $DSH_HOME/maimai-bridge/settings.json so it survives restarts and profile swaps.
 */
import { spawn } from 'node:child_process'
import { appendFileSync, existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { connect } from 'node:net'
import { homedir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

export const name = '@local/dsh-maimai-settings'

/** Declared dependency: the Loader activates this plugin once this service exists. */
export const inject = ['webServer']

const PACKAGE_DIR = dirname(fileURLToPath(import.meta.url))
const ROUTE_PREFIX = '/x-maimai-bridge'
const RUN_TIMEOUT_MS = 180_000
const BODY_LIMIT = 1_000_000

const SETTING_KEYS = ['bridgeDir', 'maibotHome', 'pythonExe', 'presetOut']

function dshHome() {
  return process.env.DSH_HOME || join(homedir(), '.dsh')
}

function settingsFilePath() {
  return join(dshHome(), 'maimai-bridge', 'settings.json')
}

function defaultSettings() {
  const bridgeDir = resolve(PACKAGE_DIR, '..')
  return {
    bridgeDir,
    maibotHome: '',
    pythonExe: process.platform === 'win32' ? 'python.exe' : 'python3',
    presetOut: join(bridgeDir, 'dsh-preset'),
  }
}

function loadSettings() {
  const base = defaultSettings()
  const file = settingsFilePath()
  if (!existsSync(file)) return base
  try {
    const parsed = JSON.parse(readFileSync(file, 'utf8'))
    for (const key of SETTING_KEYS) {
      const value = parsed[key]
      if (typeof value === 'string' && value.trim()) base[key] = value.trim()
    }
  } catch {
    /* a corrupt file must never take the settings page down */
  }
  return base
}

function saveSettings(patch) {
  const next = loadSettings()
  for (const key of SETTING_KEYS) {
    const value = patch[key]
    if (typeof value === 'string') next[key] = value.trim()
  }
  mkdirSync(dirname(settingsFilePath()), { recursive: true })
  writeFileSync(settingsFilePath(), `${JSON.stringify(next, null, 2)}\n`, 'utf8')
  return next
}

function readBody(req) {
  return new Promise((resolvePromise, reject) => {
    let raw = ''
    req.setEncoding('utf8')
    req.on('data', (chunk) => {
      raw += chunk
      if (raw.length > BODY_LIMIT) {
        req.destroy()
        reject(new Error('请求体过大'))
      }
    })
    req.on('end', () => {
      if (!raw.trim()) {
        resolvePromise({})
        return
      }
      try {
        const parsed = JSON.parse(raw)
        resolvePromise(parsed && typeof parsed === 'object' ? parsed : {})
      } catch {
        reject(new Error('请求体不是合法 JSON'))
      }
    })
    req.on('error', reject)
  })
}

function sendJson(res, status, body) {
  const payload = JSON.stringify(body)
  res.statusCode = status
  res.setHeader('content-type', 'application/json; charset=utf-8')
  res.setHeader('cache-control', 'no-store')
  res.end(payload)
}

function runScript(python, script, args) {
  return new Promise((resolvePromise) => {
    let child
    try {
      child = spawn(python, [script, ...args], {
        env: { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' },
        windowsHide: true,
      })
    } catch (error) {
      resolvePromise({ code: -1, stdout: '', stderr: String(error) })
      return
    }
    let stdout = ''
    let stderr = ''
    const timer = setTimeout(() => {
      stderr += `\n[超时] 超过 ${RUN_TIMEOUT_MS / 1000}s 未结束，已终止`
      child.kill()
    }, RUN_TIMEOUT_MS)
    child.stdout.setEncoding('utf8')
    child.stderr.setEncoding('utf8')
    child.stdout.on('data', (chunk) => { stdout += chunk })
    child.stderr.on('data', (chunk) => { stderr += chunk })
    child.on('error', (error) => {
      clearTimeout(timer)
      resolvePromise({ code: -1, stdout, stderr: `${stderr}${String(error)}` })
    })
    child.on('close', (code) => {
      clearTimeout(timer)
      resolvePromise({ code: typeof code === 'number' ? code : -1, stdout, stderr })
    })
  })
}

function projectVersion(maibotHome) {
  if (!maibotHome) return ''
  try {
    const text = readFileSync(join(maibotHome, 'pyproject.toml'), 'utf8')
    const match = text.match(/^\s*version\s*=\s*"([^"]+)"/m)
    return match ? match[1] : ''
  } catch {
    return ''
  }
}

function memoryInfo(maibotHome) {
  if (!maibotHome) return null
  const path = join(maibotHome, 'data', 'a-memorix', 'metadata', 'metadata.db')
  try {
    const stat = statSync(path)
    if (!stat.isFile()) return null
    return { bytes: stat.size, mtime: stat.mtimeMs, path }
  } catch {
    return null
  }
}

function probePort(port, host = '127.0.0.1', timeoutMs = 1200) {
  return new Promise((resolvePromise) => {
    let settled = false
    const done = (value) => {
      if (settled) return
      settled = true
      resolvePromise(value)
    }
    let socket
    try {
      socket = connect({ port, host })
    } catch {
      done(false)
      return
    }
    socket.unref()
    socket.setTimeout(timeoutMs)
    socket.once('connect', () => { socket.destroy(); done(true) })
    socket.once('timeout', () => { socket.destroy(); done(false) })
    socket.once('error', () => { socket.destroy(); done(false) })
  })
}

// ---------------------------------------------------------------- MaiBot 插件配置
// 只做「按行改值」，保留注释与顺序，避免整份 TOML 重写把用户的注释吃掉。

const PLUGIN_ID = 'maimai_bridge'

/** 可写字段：键名 → 期望类型。值按行替换，缺失则追加到 [plugin] 之后。 */
const PLUGIN_KEYS = {
  enabled: 'boolean',
  recall_limit: 'number',
  allow_memory_write: 'boolean',
  dsh_command: 'string',
  dsh_profile: 'string',
  dsh_timeout_seconds: 'number',
  dsh_cwd: 'string',
  dsh_extra_args: 'string',
  speak_model: 'string',
}

function pluginConfigPath(maibotHome) {
  return join(maibotHome, 'plugins', PLUGIN_ID, 'config.toml')
}

function coerceTomlValue(type, raw) {
  if (type === 'boolean') return raw === true || raw === 'true'
  if (type === 'number') {
    const value = Number(raw)
    return Number.isFinite(value) ? value : null
  }
  return typeof raw === 'string' ? raw : String(raw ?? '')
}

function formatTomlValue(type, value) {
  if (type === 'boolean') return value ? 'true' : 'false'
  if (type === 'number') return String(value)
  return JSON.stringify(String(value))
}

function readPluginConfig(maibotHome) {
  const file = pluginConfigPath(maibotHome)
  const config = { file, exists: existsSync(file), values: {}, raw: '' }
  if (!config.exists) return config
  let text = ''
  try {
    text = readFileSync(file, 'utf8')
  } catch {
    return config
  }
  config.raw = text
  for (const line of text.split(/\r?\n/)) {
    const match = line.match(/^\s*([A-Za-z0-9_]+)\s*=\s*(.+?)\s*$/)
    if (!match) continue
    const [, key, rawValue] = match
    if (!(key in PLUGIN_KEYS)) continue
    let value = rawValue.replace(/\s+#.*$/, '').trim()
    if (/^".*"$/.test(value)) value = value.slice(1, -1)
    else if (/^'.*'$/.test(value)) value = value.slice(1, -1)
    config.values[key] = coerceTomlValue(PLUGIN_KEYS[key], value)
  }
  return config
}

function writePluginConfig(maibotHome, patch) {
  const file = pluginConfigPath(maibotHome)
  if (!existsSync(file)) throw new Error(`找不到插件配置：${file}`)
  const lines = readFileSync(file, 'utf8').split(/\r?\n/)
  const pending = new Map()
  for (const [key, type] of Object.entries(PLUGIN_KEYS)) {
    if (!(key in patch)) continue
    const value = coerceTomlValue(type, patch[key])
    if (value === null) continue
    pending.set(key, formatTomlValue(type, value))
  }
  const seen = new Set()
  const next = lines.map((line) => {
    const match = line.match(/^(\s*)([A-Za-z0-9_]+)(\s*=\s*)(.+?)(\s*)$/)
    if (!match) return line
    const [, indent, key, eq, , trailing] = match
    if (!pending.has(key)) return line
    seen.add(key)
    return `${indent}${key}${eq}${pending.get(key)}${trailing}`
  })
  const missing = [...pending.keys()].filter((key) => !seen.has(key))
  if (missing.length) {
    const tail = next.length && next[next.length - 1].trim() === '' ? next.pop() : undefined
    for (const key of missing) next.push(`${key} = ${pending.get(key)}`)
    if (tail !== undefined) next.push(tail)
  }
  writeFileSync(file, next.join('\n'), 'utf8')
  return readPluginConfig(maibotHome)
}

function presetInfo(settings) {
  const file = join(settings.presetOut || '', 'cordis.patch.yml')
  if (!settings.presetOut) return { path: '', exists: false, mtime: 0 }
  try {
    const stat = statSync(file)
    return { path: file, exists: true, mtime: stat.mtimeMs }
  } catch {
    return { path: file, exists: false, mtime: 0 }
  }
}

function pluginInfo(maibotHome) {
  const manifest = join(maibotHome, 'plugins', PLUGIN_ID, '_manifest.json')
  let version = ''
  try {
    version = JSON.parse(readFileSync(manifest, 'utf8')).version || ''
  } catch {
    version = ''
  }
  return { id: PLUGIN_ID, installed: existsSync(manifest), version }
}

function requireHome(settings) {
  if (!settings.maibotHome) {
    throw new Error('还没填 MaiBot 目录，先在「路径」里填好再点保存')
  }
  if (!existsSync(settings.maibotHome)) {
    throw new Error(`MaiBot 目录不存在：${settings.maibotHome}`)
  }
}

async function route(req, res) {
  const url = new URL(req.url || ROUTE_PREFIX, 'http://localhost')
  const action = url.pathname.slice(ROUTE_PREFIX.length).replace(/^\/+/, '').replace(/\/+$/, '')

  if (action === 'status' && req.method === 'GET') {
    const settings = loadSettings()
    const maibotOnline = await probePort(8001)
    const pluginConfig = readPluginConfig(settings.maibotHome)
    sendJson(res, 200, {
      ok: true,
      settings,
      resolved: settings,
      maibotVersion: projectVersion(settings.maibotHome),
      maibotOnline,
      memory: memoryInfo(settings.maibotHome),
      plugin: pluginInfo(settings.maibotHome),
      pluginConfig: {
        file: pluginConfig.file,
        exists: pluginConfig.exists,
        values: pluginConfig.values,
      },
      preset: presetInfo(settings),
      settingsFile: settingsFilePath(),
      dshHome: dshHome(),
      bridgeScript: join(settings.bridgeDir, 'maimai.py'),
    })
    return
  }

  if (action === 'plugin-config' && req.method === 'GET') {
    const settings = loadSettings()
    requireHome(settings)
    const config = readPluginConfig(settings.maibotHome)
    sendJson(res, 200, {
      ok: true,
      file: config.file,
      exists: config.exists,
      values: config.values,
    })
    return
  }

  if (action === 'plugin-config' && req.method === 'POST') {
    const settings = loadSettings()
    requireHome(settings)
    const body = await readBody(req)
    const config = writePluginConfig(settings.maibotHome, body || {})
    sendJson(res, 200, { ok: true, ...config })
    return
  }

  if (action === 'settings' && req.method === 'GET') {
    sendJson(res, 200, { ok: true, settings: loadSettings(), settingsFile: settingsFilePath() })
    return
  }

  if (action === 'settings' && req.method === 'POST') {
    const body = await readBody(req)
    const patch = {}
    for (const key of SETTING_KEYS) {
      if (typeof body[key] === 'string') patch[key] = body[key]
    }
    const settings = saveSettings(patch)
    sendJson(res, 200, { ok: true, settings, settingsFile: settingsFilePath() })
    return
  }

  if (action === 'persona' && req.method === 'GET') {
    const settings = loadSettings()
    requireHome(settings)
    const script = join(settings.bridgeDir, 'maimai.py')
    if (!existsSync(script)) throw new Error(`找不到桥接脚本：${script}`)
    const result = await runScript(settings.pythonExe, script, ['--home', settings.maibotHome, 'persona'])
    sendJson(res, 200, {
      ok: result.code === 0,
      persona: result.stdout.trim(),
      stdout: result.stdout,
      stderr: result.stderr,
      code: result.code,
    })
    return
  }

  if (action === 'recall' && req.method === 'POST') {
    const settings = loadSettings()
    requireHome(settings)
    const script = join(settings.bridgeDir, 'maimai.py')
    if (!existsSync(script)) throw new Error(`找不到桥接脚本：${script}`)
    const body = await readBody(req)
    const query = typeof body.query === 'string' ? body.query.trim() : ''
    if (!query) throw new Error('检索词不能为空')
    let limit = Number(body.limit)
    if (!Number.isFinite(limit)) limit = 5
    limit = Math.min(20, Math.max(1, Math.trunc(limit)))
    const result = await runScript(settings.pythonExe, script, [
      '--home', settings.maibotHome, 'recall', query, '--limit', String(limit),
    ])
    sendJson(res, 200, {
      ok: result.code === 0,
      result: result.stdout.trim(),
      stdout: result.stdout,
      stderr: result.stderr,
      code: result.code,
    })
    return
  }

  if (action === 'remember' && req.method === 'POST') {
    const settings = loadSettings()
    requireHome(settings)
    const script = join(settings.bridgeDir, 'maimai.py')
    if (!existsSync(script)) throw new Error(`找不到桥接脚本：${script}`)
    const body = await readBody(req)
    const text = typeof body.text === 'string' ? body.text.trim() : ''
    if (!text) throw new Error('要写的内容不能为空')
    if (text.length > 8000) throw new Error('一次最多写 8000 字，太长的拆成几条')
    const source = typeof body.source === 'string' && body.source.trim()
      ? body.source.trim().slice(0, 64)
      : 'dsh:settings'
    const result = await runScript(settings.pythonExe, script, [
      '--home', settings.maibotHome, 'remember', text, '--source', source,
    ])
    sendJson(res, 200, {
      ok: result.code === 0,
      result: result.stdout.trim(),
      stdout: result.stdout,
      stderr: result.stderr,
      code: result.code,
      memory: memoryInfo(settings.maibotHome),
    })
    return
  }

  if (action === 'regenerate' && req.method === 'POST') {
    const settings = loadSettings()
    requireHome(settings)
    const script = join(settings.bridgeDir, 'emit_preset.py')
    if (!existsSync(script)) throw new Error(`找不到生成脚本：${script}`)
    const result = await runScript(settings.pythonExe, script, [
      '--home', settings.maibotHome,
      '--python', settings.pythonExe,
      '--out', settings.presetOut,
    ])
    sendJson(res, 200, {
      ok: result.code === 0,
      stdout: result.stdout,
      stderr: result.stderr,
      code: result.code,
      presetOut: settings.presetOut,
    })
    return
  }

  sendJson(res, 404, { ok: false, error: `未知接口：${req.method} ${action}` })
}

function trace(message) {
  try {
    const file = join(dshHome(), 'maimai-bridge', 'boot.log')
    mkdirSync(dirname(file), { recursive: true })
    appendFileSync(file, `[${new Date().toISOString()}] ${message}\n`, 'utf8')
  } catch {
    /* diagnostics must never break activation */
  }
}

export function apply(ctx) {
  trace(`apply: entered (webServer=${typeof ctx.webServer})`)
  const webServer = ctx.webServer ?? (typeof ctx.get === 'function' ? ctx.get('webServer') : undefined)
  if (!webServer || typeof webServer.register !== 'function') {
    trace('apply: webServer unavailable, registration skipped')
    return
  }
  ctx.effect(() => webServer.register({
    kind: 'prefix',
    path: ROUTE_PREFIX,
    handler: async (req, res) => {
      try {
        await route(req, res)
      } catch (error) {
        if (!res.headersSent) {
          const message = String(error && error.message ? error.message : error)
          sendJson(res, message.includes('请求体') ? 400 : 500, { ok: false, error: message })
        } else {
          try { res.end() } catch { /* already finished */ }
        }
      }
    },
  }))
  trace(`apply: registered prefix ${ROUTE_PREFIX}`)
}
