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

      const applyStatus = useCallback((data) => {
        setStatus(data)
        setTasteState(data.taste || null)
        setBiliCred(data.biliCredential || null)
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

      const onBiliRelogin = useCallback(() => run('bili-relogin', async () => {
        setBiliLog('')
        const res = await fetch(`${API}bili-relogin`, { method: 'POST' })
        const data = await res.json()
        if (!res.ok || !data.ok) throw new Error(data.error || `启动失败：HTTP ${res.status}`)
        setBiliLog('已经弹出浏览器窗口，去里面扫码登录（最多等 4 分钟）')
        let tries = 0
        const timer = setInterval(async () => {
          tries += 1
          try {
            const poll = await fetch(`${API}bili-relogin`)
            const info = await poll.json()
            if (info.output) setBiliLog(String(info.output).trim().slice(-600))
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
                disabled: busy === 'bili-relogin',
                onClick: onBiliRelogin,
              }, busy === 'bili-relogin' ? '启动中…' : '扫码登录（会弹浏览器）'),
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
