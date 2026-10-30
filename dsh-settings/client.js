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

      const applyStatus = useCallback((data) => {
        setStatus(data)
        const resolved = data.resolved || {}
        setForm({
          bridgeDir: resolved.bridgeDir || '',
          maibotHome: resolved.maibotHome || '',
          pythonExe: resolved.pythonExe || '',
          presetOut: resolved.presetOut || '',
        })
        const pc = data.pluginConfig
        setPluginForm(pc && pc.exists ? { ...pc.values } : null)
      }, [])

      const load = useCallback(async () => {
        const res = await fetch(`${API}status`)
        if (!res.ok) throw new Error(`读取状态失败：HTTP ${res.status}`)
        applyStatus(await res.json())
      }, [applyStatus])

      useEffect(() => {
        load().catch((err) => setError(String(err && err.message ? err.message : err)))
      }, [load])

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
