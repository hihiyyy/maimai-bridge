/**
 * Client half: the Maibot互联DSH settings page inside Settings → Maibot互联DSH.
 *
 * Talks to the Host half over the same-origin HTTP prefix
 * /x-maimai-bridge/ registered by index.js.
 */
window.__ModuleLoader__.load({
  id: '@local/dsh-maimai-settings',
  factory(require) {
    const React = require('react')
    const h = React.createElement
    const { useState, useEffect, useCallback } = React

    const API = '/x-maimai-bridge/'

    const card = {
      background: 'var(--dsw-alias-bg-layer-1)',
      border: '1px solid var(--dsw-alias-border-l1)',
      borderRadius: 12,
      padding: '16px 18px',
      marginBottom: 14,
    }
    const cardTitle = {
      margin: '0 0 12px',
      fontSize: 13,
      fontWeight: 600,
      color: 'var(--dsw-alias-label-primary)',
    }
    const muted = {
      margin: '0 0 10px',
      fontSize: 12,
      lineHeight: 1.6,
      color: 'var(--dsw-alias-label-secondary)',
    }
    const fieldRow = {
      display: 'grid',
      gridTemplateColumns: '150px 1fr',
      alignItems: 'center',
      gap: 10,
      marginBottom: 10,
    }
    const labelStyle = {
      fontSize: 12,
      color: 'var(--dsw-alias-label-secondary)',
    }
    const inputStyle = {
      width: '100%',
      boxSizing: 'border-box',
      padding: '7px 10px',
      borderRadius: 8,
      border: '1px solid var(--dsw-alias-border-l1)',
      background: 'var(--dsw-alias-bg-base)',
      color: 'var(--dsw-alias-label-primary)',
      fontSize: 12,
      fontFamily: 'inherit',
      outline: 'none',
    }
    const buttonStyle = {
      padding: '7px 14px',
      borderRadius: 8,
      border: '1px solid var(--dsw-alias-border-l2)',
      background: 'var(--dsw-alias-bg-layer-2)',
      color: 'var(--dsw-alias-label-primary)',
      fontSize: 12,
      cursor: 'pointer',
      fontFamily: 'inherit',
    }
    const primaryButtonStyle = {
      ...buttonStyle,
      background: 'var(--dsw-alias-brand-primary)',
      borderColor: 'var(--dsw-alias-brand-primary)',
      color: '#fff',
    }
    const buttonRow = {
      display: 'flex',
      gap: 8,
      flexWrap: 'wrap',
      alignItems: 'center',
    }
    const preStyle = {
      margin: '10px 0 0',
      padding: '10px 12px',
      borderRadius: 8,
      background: 'var(--dsw-alias-bg-base)',
      border: '1px solid var(--dsw-alias-border-l1)',
      color: 'var(--dsw-alias-label-secondary)',
      fontSize: 12,
      lineHeight: 1.65,
      whiteSpace: 'pre-wrap',
      wordBreak: 'break-word',
      maxHeight: 280,
      overflow: 'auto',
    }
    const kvRow = {
      display: 'flex',
      justifyContent: 'space-between',
      gap: 12,
      padding: '5px 0',
      fontSize: 12,
      borderBottom: '1px solid var(--dsw-alias-border-l1)',
    }
    const statusDot = (ok) => ({
      display: 'inline-block',
      width: 7,
      height: 7,
      borderRadius: '50%',
      marginRight: 7,
      background: ok
        ? 'var(--dsw-alias-state-success-primary)'
        : 'var(--dsw-alias-state-warn-primary)',
    })

    function formatBytes(bytes) {
      if (!Number.isFinite(bytes) || bytes <= 0) return '—'
      if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(1)} MB`
      if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`
      return `${bytes} B`
    }

    /** 插件配置里可编辑的字段：键名 → 展示名 + 类型 + 说明。 */
    const PLUGIN_FIELDS = [
      { key: 'admin_qq', label: '管理员 QQ', type: 'string', multi: true, hint: '每行一个 QQ 号，点「+ 再加一个」加更多。批准出门这类事只认这些人；留空 = 谁申请等谁回' },
      { key: 'enabled', label: '启用桥接', type: 'boolean', hint: '关掉后 dsh_task 会被拒绝' },
      { key: 'recall_limit', label: '默认检索条数', type: 'number', hint: 'maimai_recall 不传 limit 时用这个（1–20）' },
      { key: 'allow_memory_write', label: '允许写记忆', type: 'boolean', hint: '关掉后 maimai_remember 只读不写' },
      { key: 'dsh_command', label: 'DSH 命令', type: 'string', hint: '可执行文件名或完整路径' },
      { key: 'dsh_profile', label: 'DSH profile', type: 'string', hint: '默认 headless' },
      { key: 'dsh_timeout_seconds', label: 'DSH 超时（秒）', type: 'number', hint: '单次任务最长等待' },
      { key: 'dsh_cwd', label: 'DSH 工作目录', type: 'string', hint: '留空则继承 MaiBot 的目录' },
      { key: 'dsh_extra_args', label: '追加参数', type: 'string', hint: '按空格拆开，例如 --session-id <id> 续用同一会话' },
      { key: 'speak_model', label: '口吻模型', type: 'string', hint: 'maimai_speak 用哪个模型，留空用宿主默认' },
    ]

    /** [outing] 段的「自己想起来」：定时叫醒她那套。 */
    const AUTO_FIELDS = [
      { key: 'auto_enabled', label: '让她自己想起来', type: 'boolean', hint: '开着才会到点自己冒出来申请；关着得有人先撩她一句' },
      { key: 'auto_stream_id', label: '在哪个群里叫她', type: 'string', multi: true, hint: '每行一个群号，可以填多个（轮流挑一个叫）。留空就用她自己记下的最近说过话的群' },
      { key: 'auto_windows', label: '什么时段', type: 'string', hint: '逗号分隔，跨夜写成 18:00-09:00' },
      { key: 'auto_daily_limit', label: '每天最多几次', type: 'number', hint: '0 = 不限' },
      { key: 'auto_cooldown_minutes', label: '两次至少隔（分钟）', type: 'number', hint: '防止她一直想出去' },
      { key: 'auto_intent', label: '叫醒时说的一句', type: 'string', hint: '留空用默认文案' },
    ]

    /** [taste] 段：她自己点赞 / 收藏的那套开关。 */
    const TASTE_FIELDS = [
      { key: 'enabled', label: '允许她自己动手', type: 'boolean', hint: '关掉后只会嘴上说喜欢，不点赞也不收藏' },
      { key: 'auto_like', label: '可以自己点赞', type: 'boolean', hint: '' },
      { key: 'auto_fav', label: '可以自己收藏', type: 'boolean', hint: '' },
      { key: 'fav_folder', label: '收藏夹', type: 'string', hint: '留空 = 默认收藏夹；填名字或 id 都行' },
      { key: 'daily_limit', label: '每天最多几次', type: 'number', hint: '0 = 不限' },
      { key: 'cooldown_seconds', label: '两次间隔（秒）', type: 'number', hint: '防止一激动连点一串被当成刷赞' },
      { key: 'require_reason', label: '必须说为什么喜欢', type: 'boolean', hint: '让她记住自己为什么喜欢，也挡住乱点' },
      { key: 'dry_run', label: '试运行', type: 'boolean', hint: '只记账不真发，先看看她的口味再放开' },
    ]

    /** [relay] 段：DSH 借她的嘴说话那条通道。 */
    const RELAY_FIELDS = [
      { key: 'enabled', label: '允许 DSH 借她的嘴', type: 'boolean', hint: '关掉后 DSH 只能把话交给她，由她自己说' },
      { key: 'daily_limit', label: '每天最多几句', type: 'number', hint: '0 = 不限；建议别开太大，群里会以为是她本人' },
      { key: 'max_chars', label: '一句最多多少字', type: 'number', hint: '超了就不发，防止一条刷屏' },
    ]

    /** 逗号分隔的字符串 ↔ 数组（全角逗号也认）。 */
    function splitList(value) {
      return String(value ?? '')
        .replace(/，/g, ',')
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean)
    }

    function joinList(items) {
      return items.map((s) => String(s).trim()).filter(Boolean).join(',')
    }

    /**
     * 一行一个的多值输入：每个值一个输入框，右边 × 删掉，底下「+ 再加一个」新开一行。
     * 对 config.toml 写出去仍然是逗号串，所以后端和插件都不用动。
     */
    function MultiInput({ value, placeholder, onChange }) {
      const [items, setItems] = useState(() => {
        const list = splitList(value)
        return list.length ? list : ['']
      })

      useEffect(() => {
        const next = splitList(value)
        if (!next.length) return
        setItems((prev) => (joinList(prev) === joinList(next) ? prev : next))
      }, [value])

      const syncNext = (next) => {
        setItems(next)
        onChange(joinList(next))
      }

      const setAt = (index, text) => {
        const next = items.slice()
        next[index] = text
        syncNext(next)
      }

      const removeAt = (index) => {
        const next = items.filter((_, i) => i !== index)
        syncNext(next.length ? next : [''])
      }

      const blank = items.some((item) => !String(item).trim())

      return h('div', { style: { display: 'flex', flexDirection: 'column', gap: 6 } },
        ...items.map((item, index) => h('div', { key: `mv-${index}`, style: { display: 'flex', gap: 6 } },
          h('input', {
            style: { ...inputStyle, flex: 1 },
            value: item,
            placeholder,
            onChange: (event) => setAt(index, event.target.value),
          }),
          h('button', {
            type: 'button',
            style: buttonStyle,
            title: '删掉这一条',
            onClick: () => removeAt(index),
          }, '×'),
        )),
        h('div', { style: { display: 'flex', gap: 8, alignItems: 'center' } },
          h('button', {
            type: 'button',
            style: { ...buttonStyle, alignSelf: 'flex-start' },
            disabled: blank,
            title: blank ? '先把空的那行填上' : '再加一条',
            onClick: () => syncNext([...items, '']),
          }, '+ 再加一个'),
          blank
            ? h('span', { style: { fontSize: 11, color: 'var(--dsw-alias-label-tertiary)' } }, '有空的还没填完')
            : null,
        ),
      )
    }
    function MaimaiSettings() {
      const [status, setStatus] = useState(null)
      const [form, setForm] = useState({
        bridgeDir: '',
        maibotHome: '',
        pythonExe: '',
        presetOut: '',
      })
      const [pluginForm, setPluginForm] = useState(null)
      const [busy, setBusy] = useState('')
      const [error, setError] = useState('')
      const [notice, setNotice] = useState('')
      const [persona, setPersona] = useState('')
      const [query, setQuery] = useState('')
      const [hits, setHits] = useState('')
      const [writeText, setWriteText] = useState('')
      const [writeSource, setWriteSource] = useState('dsh:settings')
      const [writeLog, setWriteLog] = useState('')
      const [regenerateLog, setRegenerateLog] = useState('')
      const [logins, setLogins] = useState(null)
      const [loginDrafts, setLoginDrafts] = useState({})
      const [openSite, setOpenSite] = useState('')
      const [loginLog, setLoginLog] = useState('')
      const [pluginTaste, setPluginTaste] = useState(null)
      const [tasteState, setTasteState] = useState(null)
      const [tasteLog, setTasteLog] = useState('')
      const [biliCred, setBiliCred] = useState(null)
      const [biliLog, setBiliLog] = useState('')
      const [biliDraft, setBiliDraft] = useState('')
      const [admin, setAdmin] = useState(null)
      const [pluginOuting, setPluginOuting] = useState(null)
      const [outingState, setOutingState] = useState(null)
      const [autoLog, setAutoLog] = useState('')
      const [pluginRelay, setPluginRelay] = useState(null)
      const [relayState, setRelayState] = useState(null)
      const [relayLog, setRelayLog] = useState('')

      const applyStatus = useCallback((data) => {
        setStatus(data)
        setTasteState(data.taste || null)
        setBiliCred(data.biliCredential || null)
        setAdmin(data.admin || null)
        setOutingState(data.outingState || null)
        setRelayState(data.relayState || null)
        const resolved = data.resolved || {}
        setForm({
          bridgeDir: resolved.bridgeDir || '',
          maibotHome: resolved.maibotHome || '',
          pythonExe: resolved.pythonExe || '',
          presetOut: resolved.presetOut || '',
        })
        const pc = data.pluginConfig
        setPluginForm(pc && pc.exists ? { ...pc.values } : null)
        setPluginTaste(pc && pc.exists ? { ...(pc.taste || {}) } : null)
        setPluginOuting(pc && pc.exists ? { ...(pc.outing || {}) } : null)
        setPluginRelay(pc && pc.exists ? { ...(pc.relay || {}) } : null)
      }, [])

      const load = useCallback(async () => {
        const res = await fetch(`${API}status`)
        if (!res.ok) throw new Error(`读取状态失败：HTTP ${res.status}`)
        applyStatus(await res.json())
      }, [applyStatus])

      const loadLogins = useCallback(async () => {
        try {
          const res = await fetch(`${API}logins`)
          const data = await res.json()
          if (!res.ok || !data.ok) throw new Error(data.error || `读取登录信息失败：HTTP ${res.status}`)
          setLogins(data)
          const drafts = {}
          for (const site of data.sites || []) {
            drafts[site.key] = data.values && data.values[site.key] ? data.values[site.key].cookie || '' : ''
          }
          setLoginDrafts(drafts)
        } catch (err) {
          setError(String(err && err.message ? err.message : err))
        }
      }, [])

      useEffect(() => {
        load().catch((err) => setError(String(err && err.message ? err.message : err)))
        loadLogins()
      }, [load, loadLogins])

      const run = useCallback(async (name, action) => {
        setBusy(name)
        setError('')
        setNotice('')
        try {
          await action()
        } catch (err) {
          setError(String(err && err.message ? err.message : err))
        } finally {
          setBusy('')
        }
      }, [])

      const onSave = useCallback(() => run('save', async () => {
        const res = await fetch(`${API}settings`, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify(form),
        })
        const data = await res.json()
        if (!res.ok || !data.ok) throw new Error(data.error || `保存失败：HTTP ${res.status}`)
        setNotice('路径已保存')
        await load()
      }), [form, load, run])

      const onSavePlugin = useCallback(() => run('save-plugin', async () => {
        if (!pluginForm) throw new Error('没有读到插件配置')
        const res = await fetch(`${API}plugin-config`, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify(pluginForm),
        })
        const data = await res.json()
        if (!res.ok || !data.ok) throw new Error(data.error || `保存失败：HTTP ${res.status}`)
        setNotice('插件配置已保存，重启 MaiBot 后生效')
        await load()
      }), [pluginForm, load, run])

      const onPersona = useCallback(() => run('persona', async () => {
        setPersona('')
        const res = await fetch(`${API}persona`)
        const data = await res.json()
        if (!res.ok || !data.ok) throw new Error(data.stderr || data.error || '读取人格失败')
        setPersona(data.persona || '（空）')
      }), [run])

      const onRecall = useCallback(() => run('recall', async () => {
        setHits('')
        if (!query.trim()) throw new Error('先写一个检索词')
        const res = await fetch(`${API}recall`, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ query: query.trim(), limit: 5 }),
        })
        const data = await res.json()
        if (!res.ok || !data.ok) throw new Error(data.stderr || data.error || '检索失败')
        setHits(data.result || '（没有命中）')
      }), [query, run])

      const onRemember = useCallback(() => run('remember', async () => {
        setWriteLog('')
        const text = writeText.trim()
        if (!text) throw new Error('先写点内容再点')
        const res = await fetch(`${API}remember`, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ text, source: writeSource.trim() || 'dsh:settings' }),
        })
        const data = await res.json()
        if (!res.ok || !data.ok) throw new Error(data.stderr || data.result || data.error || '写入失败')
        setWriteLog(data.result || '已写入')
        setWriteText('')
        setNotice('已写进她的长期记忆')
        await load()
      }), [writeText, writeSource, load, run])

      const onSaveLogin = useCallback((siteKey, override) => run(`login:${siteKey}`, async () => {
        setLoginLog('')
        const value = override !== undefined ? override : loginDrafts[siteKey] || ''
        const res = await fetch(`${API}logins`, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ [siteKey]: value }),
        })
        const data = await res.json()
        if (!res.ok || !data.ok) throw new Error(data.error || `保存失败：HTTP ${res.status}`)
        setLogins((prev) => (prev ? { ...prev, exists: true, values: data.values || {} } : prev))
        setLoginLog(String(value || '').trim() ? '已保存，下次去看那个平台就带着登录态' : '已清除这个平台的登录')
      }), [loginDrafts, run])

      const onRegenerate = useCallback(() => run('regenerate', async () => {
        setRegenerateLog('')
        const res = await fetch(`${API}regenerate`, { method: 'POST' })
        const data = await res.json()
        if (!res.ok || !data.ok) throw new Error(data.stderr || data.error || '重新生成失败')
        setRegenerateLog(data.stdout || '已重新生成')
        setNotice('preset 已重新生成，重启 DSH 后生效')
      }), [run])

      const updateField = (key) => (event) => {
        const value = event.target.value
        setForm((prev) => ({ ...prev, [key]: value }))
      }

      const updatePluginField = (key, type) => (event) => {
        const raw = type === 'boolean' ? event.target.checked : event.target.value
        const value = type === 'number'
          ? (raw === '' ? 0 : Number(raw))
          : raw
        setPluginForm((prev) => ({ ...(prev || {}), [key]: value }))
      }

      const updateTasteField = (key, type) => (event) => {
        const raw = type === 'boolean' ? event.target.checked : event.target.value
        const value = type === 'number' ? (raw === '' ? 0 : Number(raw)) : raw
        setPluginTaste((prev) => ({ ...(prev || {}), [key]: value }))
      }

      const onSaveTaste = useCallback(() => run('save-taste', async () => {
        if (!pluginTaste) throw new Error('没有读到插件配置')
        const res = await fetch(`${API}plugin-config`, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ taste: pluginTaste }),
        })
        const data = await res.json()
        if (!res.ok || !data.ok) throw new Error(data.error || `保存失败：HTTP ${res.status}`)
        setNotice('「喜欢就自己动手」已保存，重启 MaiBot 后生效')
        await load()
      }), [pluginTaste, load, run])

      const refreshTaste = useCallback(() => run('taste-refresh', async () => {
        const res = await fetch(`${API}taste`)
        const data = await res.json()
        if (!res.ok || !data.ok) throw new Error(data.error || `读取失败：HTTP ${res.status}`)
        setTasteState(data)
        setTasteLog('记账已刷新')
      }), [run])

      const updateAutoField = (key, type) => (event) => {
        const raw = type === 'boolean' ? event.target.checked : event.target.value
        const value = type === 'number' ? (raw === '' ? 0 : Number(raw)) : raw
        setPluginOuting((prev) => ({ ...(prev || {}), [key]: value }))
      }

      const onSaveAuto = useCallback(() => run('save-auto', async () => {
        if (!pluginOuting) throw new Error('没有读到插件配置')
        const res = await fetch(`${API}plugin-config`, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ outing: pluginOuting }),
        })
        const data = await res.json()
        if (!res.ok || !data.ok) throw new Error(data.error || `保存失败：HTTP ${res.status}`)
        setNotice('「自己想起来」已保存，重启 MaiBot 后生效')
        await load()
      }), [pluginOuting, load, run])

      const refreshOuting = useCallback(() => run('outing-refresh', async () => {
        await load()
        setAutoLog('记账已刷新')
      }), [load, run])

      const updateRelayField = (key, type) => (event) => {
        const raw = type === 'boolean' ? event.target.checked : event.target.value
        const value = type === 'number' ? (raw === '' ? 0 : Number(raw)) : raw
        setPluginRelay((prev) => ({ ...(prev || {}), [key]: value }))
      }

      const onSaveRelay = useCallback(() => run('save-relay', async () => {
        if (!pluginRelay) throw new Error('没有读到插件配置')
        const res = await fetch(`${API}plugin-config`, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ relay: pluginRelay }),
        })
        const data = await res.json()
        if (!res.ok || !data.ok) throw new Error(data.error || `保存失败：HTTP ${res.status}`)
        setNotice('「替她说一句」已保存，重启 MaiBot 后生效')
        await load()
      }), [pluginRelay, load, run])

      const refreshRelay = useCallback(() => run('relay-refresh', async () => {
        await load()
        setRelayLog('记账已刷新')
      }), [load, run])

      /** 任意平台扫码登录：POST 起进程，然后每 4 秒问一次进度。 */
      const onCookieLogin = useCallback((siteKey) => run(`login:${siteKey}`, async () => {
        setLoginLog('')
        const res = await fetch(`${API}cookie-login`, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ site: siteKey }),
        })
        const data = await res.json()
        if (!res.ok || !data.ok) throw new Error(data.error || `启动失败：HTTP ${res.status}`)
        setLoginLog('已经弹出浏览器窗口，去里面登录（最多等 4 分钟），登录成功会自动保存')
        let tries = 0
        const timer = setInterval(async () => {
          tries += 1
          try {
            const poll = await fetch(`${API}cookie-login`)
            const info = await poll.json()
            if (info.output) setLoginLog(String(info.output).trim().slice(-600))
            if (!info.running || tries > 75) {
              clearInterval(timer)
              await load()
            }
          } catch {
            clearInterval(timer)
          }
        }, 4000)
      }), [load, run])

      const onSaveBiliManual = useCallback(() => run('bili-save', async () => {
        setBiliLog('')
        const value = biliDraft.trim()
        if (!value) throw new Error('先把 SESSDATA 粘进来')
        const res = await fetch(`${API}bili-credential`, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ sessdata: value }),
        })
        const data = await res.json()
        if (!res.ok || !data.ok) throw new Error(data.error || `保存失败：HTTP ${res.status}`)
        setBiliCred(data)
        setBiliDraft('')
        setBiliLog('已保存，重启 MaiBot 后生效')
      }), [biliDraft, run])

      const memory = status && status.memory
      const plugin = status && status.plugin
      const preset = status && status.preset

      return h('div', { style: { maxWidth: 760, padding: '4px 2px' } },
        h('h2', { style: { margin: '0 0 6px', fontSize: 16, color: 'var(--dsw-alias-label-primary)' } }, 'Maibot互联DSH'),
        h('p', { style: muted },
          '把 DSH 的「麦麦」模式和本机 MaiBot 接起来：人格实时读、长期记忆共用同一个库、DSH 能被她调用、她的插件参数也能在这里改。'),

        h('div', { style: card },
          h('div', { style: cardTitle }, '连通状态'),
          h('div', { style: kvRow },
            h('span', null, h('span', { style: statusDot(!!(status && status.maibotVersion)) }), 'MaiBot 版本'),
            h('span', { style: { color: 'var(--dsw-alias-label-primary)' } },
              status ? (status.maibotVersion || '未检测到 pyproject.toml') : '读取中…'),
          ),
          h('div', { style: kvRow },
            h('span', null, h('span', { style: statusDot(!!(status && status.maibotOnline)) }), 'MaiBot 本体'),
            h('span', { style: { color: 'var(--dsw-alias-label-primary)' } },
              status ? (status.maibotOnline ? 'WebUI 在线（8001）' : '没监听 8001，本体可能没启动') : '读取中…'),
          ),
          h('div', { style: kvRow },
            h('span', null, h('span', { style: statusDot(!!(plugin && plugin.installed)) }), '桥插件'),
            h('span', { style: { color: 'var(--dsw-alias-label-primary)' } },
              plugin
                ? (plugin.installed ? `已安装 ${plugin.version || ''}`.trim() : '未安装到 plugins/maimai_bridge')
                : '读取中…'),
          ),
          h('div', { style: kvRow },
            h('span', null, h('span', { style: statusDot(!!(admin && admin.configured)) }), '管理员 QQ'),
            h('span', { style: { color: 'var(--dsw-alias-label-primary)' } },
              admin
                ? (admin.configured ? admin.display : '还没设（谁申请等谁回）')
                : '读取中…'),
          ),
          h('div', { style: kvRow },
            h('span', null, h('span', { style: statusDot(!!memory) }), '长期记忆库'),
            h('span', { style: { color: 'var(--dsw-alias-label-primary)' } },
              memory ? formatBytes(memory.bytes) : '未检测到 metadata.db'),
          ),
          h('div', { style: kvRow },
            h('span', null, h('span', { style: statusDot(!!(preset && preset.exists)) }), 'DSH preset'),
            h('span', { style: { color: 'var(--dsw-alias-label-primary)' } },
              preset
                ? (preset.exists ? `已生成（${new Date(preset.mtime).toLocaleString()}）` : '还没生成，点下面的按钮')
                : '读取中…'),
          ),
          h('div', { style: { ...kvRow, borderBottom: 'none' } },
            h('span', null, '设置文件'),
            h('span', {
              style: {
                color: 'var(--dsw-alias-label-tertiary)',
                fontSize: 11,
                wordBreak: 'break-all',
                textAlign: 'right',
              },
            }, status ? status.settingsFile : '—'),
          ),
        ),

        h('div', { style: card },
          h('div', { style: cardTitle }, 'MaiBot 侧插件参数'),
          h('p', { style: muted },
            '直接读写 MaiBot 插件 maimai_bridge 的 config.toml。改完要重启 MaiBot 才生效（这里只改值，注释和其他键原样保留）。'),
          pluginForm
            ? h('div', null,
              ...PLUGIN_FIELDS.map((field) => h('div', { key: field.key, style: fieldRow },
                h('span', { style: labelStyle }, field.label),
                field.type === 'boolean'
                  ? h('label', { style: { ...buttonRow, gap: 8 } },
                    h('input', {
                      type: 'checkbox',
                      checked: !!pluginForm[field.key],
                      onChange: updatePluginField(field.key, field.type),
                    }),
                    h('span', { style: { fontSize: 12, color: 'var(--dsw-alias-label-tertiary)' } }, field.hint),
                  )
                  : field.multi
                    ? h(MultiInput, {
                      value: pluginForm[field.key],
                      placeholder: field.hint,
                      onChange: (text) => setPluginForm((prev) => ({ ...(prev || {}), [field.key]: text })),
                    })
                    : h('input', {
                      style: inputStyle,
                      type: field.type === 'number' ? 'number' : 'text',
                      value: pluginForm[field.key] === undefined || pluginForm[field.key] === null
                        ? ''
                        : String(pluginForm[field.key]),
                      placeholder: field.hint,
                      onChange: updatePluginField(field.key, field.type),
                    }),
              )),
              h('div', { style: buttonRow },
                h('button', {
                  type: 'button',
                  style: primaryButtonStyle,
                  disabled: busy === 'save-plugin',
                  onClick: onSavePlugin,
                }, busy === 'save-plugin' ? '保存中…' : '保存插件参数'),
              ),
            )
            : h('p', { style: muted }, '没找到 plugins/maimai_bridge/config.toml —— 先把 MaiBot 目录填对并保存。'),
        ),

        h('div', { style: card },
          h('div', { style: cardTitle }, '喜欢就自己动手'),
          h('p', { style: muted },
            '她看完真喜欢的，自己点个赞、收进收藏夹。额度和间隔在这里管，记账在 ',
            h('code', { style: { fontSize: 11 } }, 'data/plugins/maimai_bridge/taste.json'),
            '。改完要重启 MaiBot 才生效。'),
          pluginTaste
            ? h('div', null,
              ...TASTE_FIELDS.map((field) => h('div', { key: field.key, style: fieldRow },
                h('span', { style: labelStyle }, field.label),
                field.type === 'boolean'
                  ? h('label', { style: { ...buttonRow, gap: 8 } },
                    h('input', {
                      type: 'checkbox',
                      checked: !!pluginTaste[field.key],
                      onChange: updateTasteField(field.key, field.type),
                    }),
                    h('span', { style: { fontSize: 12, color: 'var(--dsw-alias-label-tertiary)' } }, field.hint),
                  )
                  : h('input', {
                    style: inputStyle,
                    type: field.type === 'number' ? 'number' : 'text',
                    value: pluginTaste[field.key] === undefined || pluginTaste[field.key] === null
                      ? ''
                      : String(pluginTaste[field.key]),
                    placeholder: field.hint,
                    onChange: updateTasteField(field.key, field.type),
                  }),
              )),
              h('div', { style: buttonRow },
                h('button', {
                  type: 'button',
                  style: primaryButtonStyle,
                  disabled: busy === 'save-taste',
                  onClick: onSaveTaste,
                }, busy === 'save-taste' ? '保存中…' : '保存这些开关'),
                h('button', {
                  type: 'button',
                  style: buttonStyle,
                  disabled: busy === 'taste-refresh',
                  onClick: refreshTaste,
                }, busy === 'taste-refresh' ? '刷新中…' : '刷新今天记账'),
              ),
              tasteState
                ? h('p', { style: { ...muted, marginTop: 10 } },
                  `今天（${tasteState.date || '—'}）已经自己动手 ${tasteState.used || 0} 次`,
                  tasteState.liked && tasteState.liked.length
                    ? `；最近点赞：${tasteState.liked.slice(0, 3).map((x) => (x && (x.title || x.bvid)) || '').filter(Boolean).join('、')}`
                    : '；今天还没点过赞',
                )
                : null,
              tasteLog
                ? h('p', { style: { margin: '6px 0 0', fontSize: 11, color: 'var(--dsw-alias-label-tertiary)' } }, tasteLog)
                : null,
            )
            : h('p', { style: muted }, '没读到 [taste] 段 —— 先把 MaiBot 目录填对，或重启 MaiBot 让新配置生成。'),
        ),

        h('div', { style: card },
          h('div', { style: cardTitle }, '自己想起来'),
          h('p', { style: muted },
            '前面那套是「她想去，先问你」；这里是「没人撩她，她也会想起来」。',
            '开着之后，到时段她会自己冒出来说想出去转转，然后照样走申请流程——批不批还是你说了算。',
            '关着就得有人先跟她说一句。改完要重启 MaiBot 才生效。'),
          pluginOuting
            ? h('div', null,
              ...AUTO_FIELDS.map((field) => h('div', { key: field.key, style: fieldRow },
                h('span', { style: labelStyle }, field.label),
                field.type === 'boolean'
                  ? h('label', { style: { ...buttonRow, gap: 8 } },
                    h('input', {
                      type: 'checkbox',
                      checked: !!pluginOuting[field.key],
                      onChange: updateAutoField(field.key, field.type),
                    }),
                    h('span', { style: { fontSize: 12, color: 'var(--dsw-alias-label-tertiary)' } }, field.hint),
                  )
                  : field.multi
                    ? h(MultiInput, {
                      value: pluginOuting[field.key],
                      placeholder: field.hint,
                      onChange: (text) => setPluginOuting((prev) => ({ ...(prev || {}), [field.key]: text })),
                    })
                    : h('input', {
                      style: inputStyle,
                      type: field.type === 'number' ? 'number' : 'text',
                      value: pluginOuting[field.key] === undefined || pluginOuting[field.key] === null
                        ? ''
                        : String(pluginOuting[field.key]),
                      placeholder: field.hint,
                      onChange: updateAutoField(field.key, field.type),
                    }),
              )),
              h('div', { style: buttonRow },
                h('button', {
                  type: 'button',
                  style: primaryButtonStyle,
                  disabled: busy === 'save-auto',
                  onClick: onSaveAuto,
                }, busy === 'save-auto' ? '保存中…' : '保存这些设置'),
                h('button', {
                  type: 'button',
                  style: buttonStyle,
                  disabled: busy === 'outing-refresh',
                  onClick: refreshOuting,
                }, busy === 'outing-refresh' ? '刷新中…' : '刷新今天记账'),
              ),
              outingState
                ? h('p', { style: { ...muted, marginTop: 10 } },
                  `今天（${outingState.date || '—'}）出去 ${outingState.used || 0} 次，叫醒 ${outingState.autoCount || 0} 次`,
                  outingState.leaseLeftMs > 0
                    ? `；现在在外面，还剩 ${Math.ceil(outingState.leaseLeftMs / 60000)} 分钟`
                    : (outingState.waiting ? '；有一条申请正等着回' : '；现在没在外面'))
                : null,
              autoLog
                ? h('p', { style: { margin: '6px 0 0', fontSize: 11, color: 'var(--dsw-alias-label-tertiary)' } }, autoLog)
                : null,
            )
            : h('p', { style: muted }, '没读到 [outing] 段 —— 先把 MaiBot 目录填对，或重启 MaiBot 让新配置生成。'),
        ),

        h('div', { style: card },
          h('div', { style: cardTitle }, '替她说一句'),
          h('p', { style: muted },
            '她可以把活交给 DSH 去干，但 DSH 没有发送权——它只能在答复里用 [[speak]]…[[/speak]] 写好台词，',
            '由这里校验后代发。钱和账号的事、@所有人、太长的话都会被拦下。改完要重启 MaiBot 才生效。'),
          pluginRelay
            ? h('div', null,
              ...RELAY_FIELDS.map((field) => h('div', { key: field.key, style: fieldRow },
                h('span', { style: labelStyle }, field.label),
                field.type === 'boolean'
                  ? h('label', { style: { ...buttonRow, gap: 8 } },
                    h('input', {
                      type: 'checkbox',
                      checked: !!pluginRelay[field.key],
                      onChange: updateRelayField(field.key, field.type),
                    }),
                    h('span', { style: { fontSize: 12, color: 'var(--dsw-alias-label-tertiary)' } }, field.hint),
                  )
                  : h('input', {
                    style: inputStyle,
                    type: field.type === 'number' ? 'number' : 'text',
                    value: pluginRelay[field.key] === undefined || pluginRelay[field.key] === null
                      ? ''
                      : String(pluginRelay[field.key]),
                    placeholder: field.hint,
                    onChange: updateRelayField(field.key, field.type),
                  }),
              )),
              h('div', { style: buttonRow },
                h('button', {
                  type: 'button',
                  style: primaryButtonStyle,
                  disabled: busy === 'save-relay',
                  onClick: onSaveRelay,
                }, busy === 'save-relay' ? '保存中…' : '保存这些设置'),
                h('button', {
                  type: 'button',
                  style: buttonStyle,
                  disabled: busy === 'relay-refresh',
                  onClick: refreshRelay,
                }, busy === 'relay-refresh' ? '刷新中…' : '刷新今天记账'),
              ),
              relayState
                ? h('p', { style: { ...muted, marginTop: 10 } },
                  `今天（${relayState.date || '—'}）替她说了 ${relayState.count || 0} 句`,
                  relayState.recent && relayState.recent.length
                    ? `；最近：${relayState.recent.slice(0, 2).join(' / ')}`
                    : '；今天还没代发过')
                : null,
              relayLog
                ? h('p', { style: { margin: '6px 0 0', fontSize: 11, color: 'var(--dsw-alias-label-tertiary)' } }, relayLog)
                : null,
            )
            : h('p', { style: muted }, '没读到 [relay] 段 —— 先把 MaiBot 目录填对，或重启 MaiBot 让新配置生成。'),
        ),

        h('div', { style: card },
          h('div', { style: cardTitle }, '路径'),
          h('div', { style: fieldRow },
            h('span', { style: labelStyle }, 'MaiBot 目录'),
            h('input', {
              style: inputStyle,
              value: form.maibotHome,
              placeholder: '例如 C:\\MaiBot，或一键包的 …\\modules\\MaiBot',
              onChange: updateField('maibotHome'),
            }),
          ),
          h('div', { style: fieldRow },
            h('span', { style: labelStyle }, 'Python 解释器'),
            h('input', {
              style: inputStyle,
              value: form.pythonExe,
              placeholder: '例如 C:\\Python312\\python.exe，或一键包的 …\\python-env\\python.exe',
              onChange: updateField('pythonExe'),
            }),
          ),
          h('div', { style: fieldRow },
            h('span', { style: labelStyle }, 'preset 输出目录'),
            h('input', {
              style: inputStyle,
              value: form.presetOut,
              onChange: updateField('presetOut'),
            }),
          ),
          h('div', { style: fieldRow },
            h('span', { style: labelStyle }, '桥接脚本目录'),
            h('input', {
              style: inputStyle,
              value: form.bridgeDir,
              onChange: updateField('bridgeDir'),
            }),
          ),
          h('div', { style: buttonRow },
            h('button', {
              type: 'button',
              style: primaryButtonStyle,
              disabled: busy === 'save',
              onClick: onSave,
            }, busy === 'save' ? '保存中…' : '保存路径'),
          ),
        ),

        h('div', { style: card },
          h('div', { style: cardTitle }, '操作'),
          h('p', { style: muted }, '「读取人格」直接问 MaiBot 当前人设；「重新生成 preset」会把最新人格写进 DSH 的麦麦模式。'),
          h('div', { style: buttonRow },
            h('button', {
              type: 'button',
              style: buttonStyle,
              disabled: busy === 'persona',
              onClick: onPersona,
            }, busy === 'persona' ? '读取中…' : '读取人格'),
            h('button', {
              type: 'button',
              style: buttonStyle,
              disabled: busy === 'regenerate',
              onClick: onRegenerate,
            }, busy === 'regenerate' ? '生成中…' : '重新生成 preset'),
          ),
          persona ? h('pre', { style: preStyle }, persona) : null,
          regenerateLog ? h('pre', { style: preStyle }, regenerateLog) : null,
        ),

        h('div', { style: card },
          h('div', { style: cardTitle }, '长期记忆（双向）'),
          h('p', { style: muted }, '这里读写的是 MaiBot 自己的 A-Memorix 长期记忆，和群里她记得的是同一个库。用单词更准——带空格的短语（如「万圣节 cos」）常常命中不到，拆成关键词分开查。'),
          h('div', { style: { ...buttonRow, marginBottom: 4 } },
            h('input', {
              style: { ...inputStyle, flex: '1 1 260px', width: 'auto' },
              value: query,
              placeholder: '输入关键词，例如 姆巴佩 / 万圣节',
              onChange: (event) => setQuery(event.target.value),
              onKeyDown: (event) => { if (event.key === 'Enter') onRecall() },
            }),
            h('button', {
              type: 'button',
              style: buttonStyle,
              disabled: busy === 'recall',
              onClick: onRecall,
            }, busy === 'recall' ? '检索中…' : '检索'),
          ),
          hits ? h('pre', { style: preStyle }, hits) : null,

          h('div', {
            style: {
              marginTop: 16,
              paddingTop: 14,
              borderTop: '1px solid var(--dsw-alias-border-l1)',
            },
          },
            h('div', {
              style: {
                fontSize: 12,
                fontWeight: 600,
                marginBottom: 8,
                color: 'var(--dsw-alias-label-primary)',
              },
            }, '写一条进她的记忆'),
            h('p', { style: { ...muted, margin: '0 0 8px' } },
              'DSH 这边发生的事，写进去她才知道。第三人称陈述，一句话说清谁做了什么、结果如何；她导入时会自己抽事实和图谱，写得具体比写得长有用。'),
            h('textarea', {
              style: {
                ...inputStyle,
                minHeight: 72,
                resize: 'vertical',
                marginBottom: 8,
                lineHeight: 1.6,
              },
              value: writeText,
              placeholder: '例如：2026年10月30日，把 MaiBot 和 DSH 的记忆打通了，现在能主动把事写进自己的长期记忆。',
              onChange: (event) => setWriteText(event.target.value),
            }),
            h('div', { style: buttonRow },
              h('input', {
                style: { ...inputStyle, flex: '0 0 190px', width: 190 },
                value: writeSource,
                placeholder: '来源标记',
                onChange: (event) => setWriteSource(event.target.value),
              }),
              h('button', {
                type: 'button',
                style: primaryButtonStyle,
                disabled: busy === 'remember',
                onClick: onRemember,
              }, busy === 'remember' ? '写入中…' : '写进记忆'),
              h('span', { style: { fontSize: 11, color: 'var(--dsw-alias-label-tertiary)' } },
                '写入要等她自己抽完事实，通常十几秒'),
            ),
            writeLog ? h('pre', { style: preStyle }, writeLog) : null,
          ),
        ),

        h('div', { style: card },
          h('div', { style: cardTitle }, '平台登录'),
          h('p', { style: muted },
            '填了哪个平台的 Cookie，去看那个平台时就带着登录态——能看到的更多，也更不容易被挡。点平台名展开；只填你愿意给她用的那个号。'),
          h('div', {
            style: {
              margin: '10px 0 14px',
              padding: '10px 12px',
              borderRadius: 8,
              border: '1px solid var(--dsw-alias-border-l1)',
              background: 'var(--dsw-alias-bg-layer-2)',
            },
          },
            h('div', { style: { display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, fontWeight: 600 } },
              h('span', { style: statusDot(!!(biliCred && biliCred.loggedIn)) }),
              h('span', null, 'B站（字幕靠它）'),
              h('span', {
                style: { fontSize: 11, fontWeight: 400, color: 'var(--dsw-alias-label-tertiary)', flex: 1 },
              },
                biliCred && biliCred.exists
                  ? (biliCred.loggedIn
                    ? `已登录 · SESSDATA ${biliCred.mask || '****'}${biliCred.hasJct ? ' · 带 csrf' : ' · 缺 csrf，点赞会失败'}`
                    : '凭证文件在，但 sessdata 是空的')
                  : '还没登录过'),
            ),
            h('div', { style: { ...buttonRow, marginTop: 8 } },
              h('button', {
                type: 'button',
                style: primaryButtonStyle,
                disabled: busy === 'login:bilibili',
                onClick: () => onCookieLogin('bilibili'),
              }, busy === 'login:bilibili' ? '等登录…' : '扫码登录（会弹浏览器）'),
              h('button', {
                type: 'button',
                style: buttonStyle,
                disabled: busy === 'bili-save',
                onClick: onSaveBiliManual,
              }, busy === 'bili-save' ? '保存中…' : '手工填 SESSDATA'),
            ),
            h('div', { style: { display: 'flex', gap: 8, marginTop: 8 } },
              h('input', {
                style: { ...inputStyle, flex: 1 },
                value: biliDraft,
                placeholder: '或者直接把 SESSDATA=xxxx 粘这里，再点「手工填 SESSDATA」',
                onChange: (event) => setBiliDraft(event.target.value),
              }),
            ),
            biliCred && biliCred.file
              ? h('p', {
                style: {
                  margin: '8px 0 0',
                  fontSize: 11,
                  color: 'var(--dsw-alias-label-tertiary)',
                  wordBreak: 'break-all',
                },
              }, biliCred.file)
              : null,
            biliLog ? h('pre', { style: { ...preStyle, maxHeight: 160, marginTop: 8 } }, biliLog) : null,
          ),
          logins && logins.sites
            ? logins.sites.map((site) => {
              const saved = logins.values && logins.values[site.key]
              const open = openSite === site.key
              const draft = loginDrafts[site.key] || ''
              return h('div', {
                key: site.key,
                style: { borderBottom: '1px solid var(--dsw-alias-border-l1)' },
              },
                h('div', {
                  style: { display: 'flex', alignItems: 'center', gap: 10, padding: '9px 0', cursor: 'pointer' },
                  onClick: () => setOpenSite(open ? '' : site.key),
                },
                  h('span', { style: statusDot(!!saved) }),
                  h('span', { style: { fontSize: 12, width: 84, color: 'var(--dsw-alias-label-primary)' } }, site.label),
                  h('span', {
                    style: { fontSize: 11, color: 'var(--dsw-alias-label-tertiary)', flex: 1 },
                  }, saved ? `已保存 · ${String(saved.cookie || '').length} 字符` : '未设置'),
                  h('button', {
                    type: 'button',
                    style: { ...buttonStyle, padding: '3px 10px', fontSize: 11 },
                    disabled: busy === `login:${site.key}`,
                    onClick: (event) => {
                      event.stopPropagation()
                      onCookieLogin(site.key)
                    },
                  }, busy === `login:${site.key}` ? '等登录…' : '扫码登录'),
                  h('span', { style: { fontSize: 11, color: 'var(--dsw-alias-label-tertiary)' } }, open ? '收起' : '展开'),
                ),
                open
                  ? h('div', { style: { paddingBottom: 12 } },
                    h('textarea', {
                      style: {
                        ...inputStyle,
                        minHeight: 64,
                        resize: 'vertical',
                        lineHeight: 1.6,
                        marginBottom: 8,
                        fontFamily: 'monospace',
                      },
                      value: draft,
                      placeholder: '粘贴 Cookie 字符串，形如 name=value; name2=value2',
                      onChange: (event) => setLoginDrafts({ ...loginDrafts, [site.key]: event.target.value }),
                    }),
                    h('div', { style: buttonRow },
                      h('button', {
                        type: 'button',
                        style: primaryButtonStyle,
                        disabled: busy === `login:${site.key}`,
                        onClick: () => onSaveLogin(site.key),
                      }, busy === `login:${site.key}` ? '保存中…' : '保存'),
                      h('button', {
                        type: 'button',
                        style: buttonStyle,
                        disabled: busy === `login:${site.key}` || !saved,
                        onClick: () => {
                          setLoginDrafts({ ...loginDrafts, [site.key]: '' })
                          onSaveLogin(site.key, '')
                        },
                      }, '清除'),
                      h('span', { style: { fontSize: 11, color: 'var(--dsw-alias-label-tertiary)' } },
                        '取法：浏览器 F12 → Network → 任一请求 → 复制 Cookie 请求头'),
                    ),
                  )
                  : null,
              )
            })
            : h('p', { style: muted }, '正在读取…'),
          loginLog
            ? h('p', { style: { margin: '10px 0 0', fontSize: 11, color: 'var(--dsw-alias-label-tertiary)' } }, loginLog)
            : null,
        ),

        notice
          ? h('div', { style: { fontSize: 12, color: 'var(--dsw-alias-state-success-primary)', marginBottom: 8 } }, notice)
          : null,
        error
          ? h('div', {
            style: {
              fontSize: 12,
              color: 'var(--dsw-alias-state-error-primary)',
              background: 'var(--dsw-alias-bg-layer-1)',
              border: '1px solid var(--dsw-alias-state-error-primary)',
              borderRadius: 8,
              padding: '9px 12px',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            },
          }, error)
          : null,
      )
    }

    return {
      inject: ['slots'],
      apply(ctx) {
        ctx.slots.inject('settings.section', () => ctx.slots.register({
          name: 'settings.section',
          id: 'maimai',
          order: 55,
          label: 'Maibot互联DSH',
        }, MaimaiSettings))
      },
    }
  },
})
