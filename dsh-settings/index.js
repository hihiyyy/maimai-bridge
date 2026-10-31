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

/**
 * 从 bot_config.toml 的 [http] 段读 WebUI 端口。
 * 端口用户可能改过，别写死；读不出来才退到麦麦的默认值 8001。
 */
function webuiPort(maibotHome) {
  const fallback = 8001
  if (!maibotHome) return fallback
  try {
    const text = readFileSync(join(maibotHome, 'config', 'bot_config.toml'), 'utf8')
    let inHttp = false
    for (const raw of text.split(/\r?\n/)) {
      const line = raw.trim()
      if (line.startsWith('[')) {
        inHttp = line === '[http]'
        continue
      }
      if (!inHttp) continue
      const match = line.match(/^port\s*=\s*(\d+)/)
      if (match) {
        const port = Number(match[1])
        if (port > 0) return port
      }
    }
  } catch {
    // 配置没读到就用默认端口
  }
  return fallback
}

// ---------------------------------------------------------------- MaiBot 插件配置
// 只做「按行改值」，保留注释与顺序，避免整份 TOML 重写把用户的注释吃掉。

/** 插件源码目录名（`<MaiBot>/plugins/<这里>`）。 */
const PLUGIN_ID = 'maimai_bridge'

/**
 * 插件数据目录名 —— 注意和源码目录**不一样**。
 * 源码目录是 `maimai_bridge`，而可写数据在 `data/plugins/lirick.maimai-bridge/`
 * （插件 id 那一套命名），两者别混。
 */
const PLUGIN_DATA_ID = 'lirick.maimai-bridge'

/** 插件自己的可写数据目录。 */
function pluginDataDir(maibotHome) {
  return join(maibotHome, 'data', 'plugins', PLUGIN_DATA_ID)
}

/** [plugin] 段可写字段：键名 → 期望类型。值按行替换，缺失则追加到 [plugin] 之后。 */
const PLUGIN_KEYS = {
  admin_qq: 'string',
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

/** [taste] 段可写字段：她自己点赞 / 收藏的那套开关。 */
const TASTE_KEYS = {
  enabled: 'boolean',
  auto_like: 'boolean',
  auto_fav: 'boolean',
  fav_folder: 'string',
  daily_limit: 'number',
  cooldown_seconds: 'number',
  require_reason: 'boolean',
  dry_run: 'boolean',
}

/** [outing] 段里只开放「自己想起来」这几个：出门流程的其他参数留给 MaiBot 配置界面。 */
const OUTING_KEYS = {
  auto_enabled: 'boolean',
  auto_stream_id: 'string',
  auto_windows: 'string',
  auto_daily_limit: 'number',
  auto_cooldown_minutes: 'number',
  auto_intent: 'string',
}

/** [relay] 段可写字段：DSH 借她的嘴说话那条通道。 */
const RELAY_KEYS = {
  enabled: 'boolean',
  daily_limit: 'number',
  max_chars: 'number',
}

/** 段名 → 该段能写的键。注意必须按段区分：enabled 在 plugin 和 taste 里都有。 */
const SECTION_FIELDS = {
  plugin: PLUGIN_KEYS,
  taste: TASTE_KEYS,
  outing: OUTING_KEYS,
  relay: RELAY_KEYS,
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
  const config = { file, exists: existsSync(file), values: {}, taste: {}, outing: {}, relay: {}, raw: '' }
  if (!config.exists) return config
  let text = ''
  try {
    text = readFileSync(file, 'utf8')
  } catch {
    return config
  }
  config.raw = text
  let section = 'plugin'
  for (const line of text.split(/\r?\n/)) {
    const head = line.match(/^\s*\[([A-Za-z0-9_.]+)\]\s*$/)
    if (head) {
      section = head[1]
      continue
    }
    const match = line.match(/^\s*([A-Za-z0-9_]+)\s*=\s*(.+?)\s*$/)
    if (!match) continue
    const fields = SECTION_FIELDS[section]
    if (!fields) continue
    const [, key, rawValue] = match
    if (!(key in fields)) continue
    let value = rawValue.replace(/\s+#.*$/, '').trim()
    if (/^".*"$/.test(value)) value = value.slice(1, -1)
    else if (/^'.*'$/.test(value)) value = value.slice(1, -1)
    const bucket = section === 'plugin' ? config.values : config[section]
    bucket[key] = coerceTomlValue(fields[key], value)
  }
  return config
}

function writePluginConfig(maibotHome, patch) {
  const file = pluginConfigPath(maibotHome)
  if (!existsSync(file)) throw new Error(`找不到插件配置：${file}`)

  const pending = new Map()
  const collect = (section, source) => {
    const fields = SECTION_FIELDS[section]
    if (!fields || !source || typeof source !== 'object') return
    for (const [key, type] of Object.entries(fields)) {
      if (!(key in source)) continue
      const value = coerceTomlValue(type, source[key])
      if (value === null) continue
      pending.set(`${section}\u0000${key}`, formatTomlValue(type, value))
    }
  }
  collect('plugin', patch)
  collect('taste', patch.taste)
  collect('outing', patch.outing)
  collect('relay', patch.relay)
  if (!pending.size) return readPluginConfig(maibotHome)

  const lines = readFileSync(file, 'utf8').split(/\r?\n/)
  const seen = new Set()
  let section = 'plugin'
  const next = lines.map((line) => {
    const head = line.match(/^\s*\[([A-Za-z0-9_.]+)\]\s*$/)
    if (head) {
      section = head[1]
      return line
    }
    const match = line.match(/^(\s*)([A-Za-z0-9_]+)(\s*=\s*)(.+?)(\s*)$/)
    if (!match) return line
    const [, indent, key, eq, , trailing] = match
    const id = `${section}\u0000${key}`
    if (!pending.has(id)) return line
    seen.add(id)
    return `${indent}${key}${eq}${pending.get(id)}${trailing}`
  })

  // 缺的键补到各自段里；段本身不存在就先建段
  for (const sectionName of Object.keys(SECTION_FIELDS)) {
    const fields = SECTION_FIELDS[sectionName]
    const missing = Object.keys(fields).filter(
      (key) => pending.has(`${sectionName}\u0000${key}`) && !seen.has(`${sectionName}\u0000${key}`),
    )
    if (!missing.length) continue
    let head = next.findIndex((line) => line.trim() === `[${sectionName}]`)
    if (head < 0) {
      while (next.length && next[next.length - 1].trim() === '') next.pop()
      next.push('', `[${sectionName}]`)
      head = next.length - 1
    }
    const block = missing.map((key) => `${key} = ${pending.get(`${sectionName}\u0000${key}`)}`)
    next.splice(head + 1, 0, ...block)
  }

  writeFileSync(file, next.join('\n'), 'utf8')
  return readPluginConfig(maibotHome)
}

/** 全局管理员：从 [plugin] 的 admin_qq 拆出来。留空 = 谁发起申请就等谁回。 */
function adminInfo(pluginConfig) {
  const raw = String(
    (pluginConfig && pluginConfig.values && pluginConfig.values.admin_qq) || '',
  )
  const ids = raw
    .replace(/，/g, ',')
    .split(',')
    .map((x) => x.trim())
    .filter(Boolean)
  return {
    ids,
    configured: ids.length > 0,
    display: ids.join('、'),
    file: (pluginConfig && pluginConfig.file) || '',
  }
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

// ---------------------------------------------------------------- 喜欢就自己动手

/** 插件按天写的记账文件（点赞/收藏都记在这里）。 */
function tasteStatePath(maibotHome) {
  return join(pluginDataDir(maibotHome), 'taste.json')
}

/** 本地日期。不能用 toISOString()，那是 UTC，会跟插件的 strftime 差 8 小时。 */
function localDate() {
  const now = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

function readTasteState(maibotHome) {
  const file = tasteStatePath(maibotHome)
  let data = {}
  try {
    data = JSON.parse(readFileSync(file, 'utf8'))
  } catch {
    data = {}
  }
  const today = localDate()
  const fresh = data?.date === today
  const liked = fresh && Array.isArray(data.liked) ? data.liked : []
  const faved = fresh && Array.isArray(data.faved) ? data.faved : []
  return {
    file,
    exists: existsSync(file),
    date: fresh ? today : '',
    liked: liked.slice(-8).reverse(),
    faved: faved.slice(-8).reverse(),
    used: liked.length + faved.length,
  }
}

// ---------------------------------------------------------------- 出门 / 自己想起来

/** 出门记录：今天出去几次、有没有在等回、通行证还剩多久、自动叫醒叫过几次。 */
function readOutingState(maibotHome) {
  const file = join(pluginDataDir(maibotHome), 'outing.json')
  let data = {}
  try {
    data = JSON.parse(readFileSync(file, 'utf8'))
  } catch {
    data = {}
  }
  const today = localDate()
  const fresh = data && data.date === today
  const lease = fresh && data.lease && typeof data.lease === 'object' ? data.lease : null
  const pending = fresh && data.pending && typeof data.pending === 'object' ? data.pending : null
  const auto = data && data.auto && typeof data.auto === 'object' ? data.auto : null
  const autoFresh = auto && auto.date === today
  return {
    file,
    exists: existsSync(file),
    date: fresh ? today : '',
    used: fresh ? Number(data.used || 0) : 0,
    waiting: !!pending,
    leaseLeftMs: lease ? Math.max(0, Number(lease.until || 0) * 1000 - Date.now()) : 0,
    autoCount: autoFresh ? Number(auto.count || 0) : 0,
    autoLastAt: autoFresh ? Number(auto.last_at || 0) * 1000 : 0,
  }
}

// ---------------------------------------------------------------- 替她说一句

/** 代发记录：今天替她说了几句、最近几条是什么。 */
function readRelayState(maibotHome) {
  const file = join(pluginDataDir(maibotHome), 'relay.json')
  let data = {}
  try {
    data = JSON.parse(readFileSync(file, 'utf8'))
  } catch {
    data = {}
  }
  const today = localDate()
  const fresh = data && data.date === today
  const sent = fresh && Array.isArray(data.sent) ? data.sent : []
  return {
    file,
    exists: existsSync(file),
    date: fresh ? today : '',
    count: fresh ? Number(data.count || 0) : 0,
    recent: sent.slice(-6).reverse().map((row) => String(row?.text || '')),
  }
}
// ---------------------------------------------------------------- B站登录态

function biliCredentialPath(maibotHome) {
  return join(pluginDataDir(maibotHome), 'bili_credential.json')
}

function readBiliCredential(maibotHome) {
  const file = biliCredentialPath(maibotHome)
  let data = {}
  try {
    data = JSON.parse(readFileSync(file, 'utf8'))
  } catch {
    data = {}
  }
  const sessdata = String(data.sessdata || '')
  const jct = String(data.bili_jct || '')
  let mtime = 0
  try {
    mtime = statSync(file).mtimeMs
  } catch {
    mtime = 0
  }
  return {
    file,
    exists: existsSync(file),
    loggedIn: Boolean(sessdata),
    mask: sessdata ? `${sessdata.slice(0, 6)}……${sessdata.slice(-4)}` : '',
    hasJct: Boolean(jct),
    mtime,
  }
}

function writeBiliCredential(maibotHome, sessdata, biliJct) {
  const file = biliCredentialPath(maibotHome)
  let data = {}
  try {
    data = JSON.parse(readFileSync(file, 'utf8'))
  } catch {
    data = {}
  }
  const text = String(sessdata ?? '').trim()
  if (text) data.sessdata = text
  else delete data.sessdata
  const jct = String(biliJct ?? '').trim()
  if (jct) data.bili_jct = jct
  mkdirSync(dirname(file), { recursive: true })
  writeFileSync(file, JSON.stringify(data, null, 2), 'utf8')
  return readBiliCredential(maibotHome)
}

/** 扫码登录进程状态：一次只许开一个窗口，记着这次登录的是哪个平台。 */
const loginRun = { running: false, site: '', exit: null, output: '' }

function startCookieLogin(settings, site) {
  if (loginRun.running) {
    return { ok: false, error: `上一次（${loginRun.site || '别的平台'}）还开着，先去那个窗口里登录` }
  }
  if (!site) return { ok: false, error: '没说要登录哪个平台' }
  const script = join(settings.bridgeDir || '', 'cookie_login.py')
  if (!existsSync(script)) return { ok: false, error: `找不到 ${script}` }
  if (!settings.pythonExe) return { ok: false, error: '还没填 Python 解释器' }
  loginRun.running = true
  loginRun.site = site
  loginRun.exit = null
  loginRun.output = ''
  let child
  try {
    child = spawn(
      settings.pythonExe,
      [script, '--site', site, '--maibot', settings.maibotHome, '--timeout', '240'],
      {
        env: { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' },
        windowsHide: false,
      },
    )
  } catch (err) {
    loginRun.running = false
    return { ok: false, error: String(err) }
  }
  const collect = (chunk) => {
    loginRun.output = (loginRun.output + chunk.toString()).slice(-4000)
  }
  child.stdout?.on('data', collect)
  child.stderr?.on('data', collect)
  child.on('error', (err) => {
    loginRun.running = false
    loginRun.exit = -1
    loginRun.output += `\n${err}`
  })
  child.on('exit', (code) => {
    loginRun.running = false
    loginRun.exit = code
  })
  return { ok: true }
}

/** 能填登录态的平台（顺序即界面顺序）。 */
const LOGIN_SITES = [
  ['bilibili', 'B站'],
  ['tieba', '贴吧'],
  ['xiaoheihe', '小黑盒'],
  ['steam', 'Steam'],
  ['zhihu', '知乎'],
  ['weibo', '微博'],
  ['douban', '豆瓣'],
  ['xhs', '小红书'],
  ['github', 'GitHub'],
]

/** 登录信息实际存放的位置（插件自己读的那一份）。 */
function loginsPath(maibotHome) {
  return join(pluginDataDir(maibotHome), 'logins.json')
}

/** 读回各平台已保存的 cookie。 */
function readLogins(maibotHome) {
  const file = loginsPath(maibotHome)
  let exists = false
  const values = {}
  try {
    if (existsSync(file)) {
      exists = true
      const parsed = JSON.parse(readFileSync(file, 'utf8'))
      if (parsed && typeof parsed === 'object') {
        for (const [site, entry] of Object.entries(parsed)) {
          if (entry && typeof entry === 'object') {
            values[site] = {
              cookie: String(entry.cookie || ''),
              ua: String(entry.ua || ''),
            }
          }
        }
      }
    }
  } catch {
    /* 文件坏了就当没填过 */
  }
  return { file, exists, values }
}

/** 写入 cookie：传空串表示清掉这个平台。 */
function writeLogins(maibotHome, patch) {
  const current = readLogins(maibotHome).values
  const known = new Set(LOGIN_SITES.map(([key]) => key))
  for (const [site, raw] of Object.entries(patch || {})) {
    if (!known.has(site)) continue
    const text = String(raw ?? '').trim()
    if (text) {
      current[site] = { cookie: text, ua: String(current[site]?.ua || '') }
    } else {
      delete current[site]
    }
  }
  const file = loginsPath(maibotHome)
  mkdirSync(dirname(file), { recursive: true })
  writeFileSync(file, JSON.stringify(current, null, 2), 'utf8')
  return { file, exists: true, values: current }
}

async function route(req, res) {
  const url = new URL(req.url || ROUTE_PREFIX, 'http://localhost')
  const action = url.pathname.slice(ROUTE_PREFIX.length).replace(/^\/+/, '').replace(/\/+$/, '')

  if (action === 'status' && req.method === 'GET') {
    const settings = loadSettings()
    const maibotOnline = await probePort(webuiPort(settings.maibotHome))
    const pluginConfig = readPluginConfig(settings.maibotHome)
    sendJson(res, 200, {
      ok: true,
      settings,
      resolved: settings,
      maibotVersion: projectVersion(settings.maibotHome),
      maibotOnline,
      webuiPort: webuiPort(settings.maibotHome),
      memory: memoryInfo(settings.maibotHome),
      plugin: pluginInfo(settings.maibotHome),
      pluginConfig: {
        file: pluginConfig.file,
        exists: pluginConfig.exists,
        values: pluginConfig.values,
        taste: pluginConfig.taste,
        outing: pluginConfig.outing,
        relay: pluginConfig.relay,
      },
      taste: readTasteState(settings.maibotHome),
      outingState: readOutingState(settings.maibotHome),
      relayState: readRelayState(settings.maibotHome),
      biliCredential: readBiliCredential(settings.maibotHome),
      admin: adminInfo(pluginConfig),
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
      taste: config.taste,
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

  if (action === 'logins' && req.method === 'GET') {
    const settings = loadSettings()
    requireHome(settings)
    const info = readLogins(settings.maibotHome)
    sendJson(res, 200, {
      ok: true,
      file: info.file,
      exists: info.exists,
      values: info.values,
      sites: LOGIN_SITES.map(([key, label]) => ({ key, label })),
    })
    return
  }

  if (action === 'logins' && req.method === 'POST') {
    const settings = loadSettings()
    requireHome(settings)
    const body = await readBody(req)
    const info = writeLogins(settings.maibotHome, body || {})
    sendJson(res, 200, { ok: true, ...info })
    return
  }

  if (action === 'taste' && req.method === 'GET') {
    const settings = loadSettings()
    requireHome(settings)
    sendJson(res, 200, { ok: true, ...readTasteState(settings.maibotHome) })
    return
  }

  if (action === 'bili-credential' && req.method === 'GET') {
    const settings = loadSettings()
    requireHome(settings)
    sendJson(res, 200, { ok: true, ...readBiliCredential(settings.maibotHome) })
    return
  }

  if (action === 'bili-credential' && req.method === 'POST') {
    const settings = loadSettings()
    requireHome(settings)
    const body = await readBody(req)
    const info = writeBiliCredential(settings.maibotHome, body?.sessdata, body?.bili_jct)
    sendJson(res, 200, { ok: true, ...info })
    return
  }

  if (action === 'cookie-login' && req.method === 'GET') {
    sendJson(res, 200, {
      ok: true,
      running: loginRun.running,
      site: loginRun.site,
      exit: loginRun.exit,
      output: loginRun.output,
    })
    return
  }

  if (action === 'cookie-login' && req.method === 'POST') {
    const settings = loadSettings()
    requireHome(settings)
    const body = await readBody(req)
    const site = String(body?.site || '').trim()
    const result = startCookieLogin(settings, site)
    if (!result.ok) {
      sendJson(res, 400, { ok: false, error: result.error })
      return
    }
    sendJson(res, 200, { ok: true, running: true, site })
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
