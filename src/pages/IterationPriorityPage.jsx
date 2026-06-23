import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchIterationPriorityBoard, saveIterationPriorityBoard } from '../api/geo.js'
import './IterationPriorityPage.css'

const PHASES = [
  { id: 'now', label: 'Now', hint: '当前 3-7 个最该推进的事项' },
  { id: 'next', label: 'Next', hint: '进入执行前仍需补齐边界' },
  { id: 'later', label: 'Later', hint: '保留方向，不复制专题细节' },
]

const STATUS_LABEL = {
  planned: '计划中',
  in_progress: '进行中',
  blocked: '阻塞',
  done: '已完成',
}

function safeArray(value) {
  return Array.isArray(value) ? value : []
}

function makeItem(phase, index) {
  const suffix = Date.now().toString(36)
  return {
    id: `iteration-item-${suffix}`,
    phase,
    priority: phase === 'now' ? `P0-${index}` : phase === 'next' ? `P1-${index}` : `P2-${index}`,
    title: 'New iteration item',
    status: 'planned',
    owner: 'shared',
    why_now: '',
    current_blocker: '',
    source_of_truth: [],
    next_action: '',
    exit_condition: '',
    handoff_note: '',
  }
}

function fieldText(item, field) {
  const value = item?.[field]
  return value === undefined || value === null ? '' : String(value)
}

function statusClass(status) {
  if (status === 'in_progress') return 'progress'
  if (status === 'blocked') return 'blocked'
  if (status === 'done') return 'done'
  return 'planned'
}

function itemCompleteness(item) {
  const fields = ['why_now', 'current_blocker', 'next_action', 'exit_condition', 'handoff_note']
  const filled = fields.filter(field => fieldText(item, field).trim()).length
  const hasSource = safeArray(item.source_of_truth).length > 0
  return Math.round(((filled + (hasSource ? 1 : 0)) / 6) * 100)
}

function buildShareUrl(viewOnly = false) {
  if (typeof window === 'undefined') return ''
  const url = new URL(window.location.href)
  url.pathname = '/iteration/priority'
  url.hash = ''
  if (viewOnly) {
    url.searchParams.set('view', '1')
  } else {
    url.searchParams.delete('view')
  }
  return url.toString()
}

function isViewOnlyUrl() {
  if (typeof window === 'undefined') return false
  return new URLSearchParams(window.location.search).get('view') === '1'
}

function ShareButton({ viewOnly = false, children }) {
  const [copied, setCopied] = useState(false)

  const copy = useCallback(async () => {
    const url = buildShareUrl(viewOnly)
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      setTimeout(() => setCopied(false), 1600)
    } catch {
      window.prompt('复制这个链接分享给同事：', url)
    }
  }, [viewOnly])

  return (
    <button type="button" className={`ip-share ${copied ? 'copied' : ''}`} onClick={copy}>
      {copied ? '已复制' : children}
    </button>
  )
}

function PhaseRail({ board, activePhase, selectedId, onPhaseChange, onSelectItem, onAddItem, readOnly = false }) {
  return (
    <aside className="ip-rail">
      {PHASES.map(phase => {
        const items = safeArray(board.items).filter(item => item.phase === phase.id)
        return (
          <section className="ip-phase" key={phase.id}>
            <button
              type="button"
              className={`ip-phase-head ${activePhase === phase.id ? 'active' : ''}`}
              onClick={() => onPhaseChange(phase.id)}
            >
              <span>{phase.label}</span>
              <strong>{items.length}</strong>
            </button>
            <p>{phase.hint}</p>
            <div className="ip-item-list">
              {items.map(item => (
                <button
                  type="button"
                  key={item.id}
                  className={`ip-item ${selectedId === item.id ? 'selected' : ''}`}
                  onClick={() => onSelectItem(item.id, phase.id)}
                >
                  <span className="ip-item-top">
                    <span className="ip-priority">{item.priority || '-'}</span>
                    <span className={`ip-status ${statusClass(item.status)}`}>{STATUS_LABEL[item.status] || item.status}</span>
                  </span>
                  <strong>{item.title}</strong>
                  <span className="ip-meter">
                    <span style={{ width: `${itemCompleteness(item)}%` }} />
                  </span>
                </button>
              ))}
            </div>
            {!readOnly && (
              <button type="button" className="ip-add" onClick={() => onAddItem(phase.id)}>
                <span aria-hidden="true">+</span>
                添加事项
              </button>
            )}
          </section>
        )
      })}
    </aside>
  )
}

function TextField({ label, value, onChange, multiline = false, placeholder = '', readOnly = false }) {
  return (
    <label className="ip-field">
      <span>{label}</span>
      {multiline ? (
        <textarea value={value} placeholder={placeholder} onChange={event => onChange(event.target.value)} rows={4} readOnly={readOnly} />
      ) : (
        <input value={value} placeholder={placeholder} onChange={event => onChange(event.target.value)} readOnly={readOnly} />
      )}
    </label>
  )
}

function ItemEditor({ item, onChange, readOnly = false }) {
  if (!item) {
    return (
      <section className="ip-editor empty">
        <div className="ip-empty-title">选择一个迭代事项</div>
        <p>左侧的 Now / Next / Later 是唯一优先级入口，细节仍回到各专题真相源维护。</p>
      </section>
    )
  }

  const update = (field, value) => onChange(item.id, { [field]: value })

  return (
    <section className="ip-editor">
      <div className="ip-editor-head">
        <div>
          <div className="ip-overline">Iteration item</div>
          <h2>{item.title || 'Untitled item'}</h2>
        </div>
        <span className="ip-score">{itemCompleteness(item)}%</span>
      </div>

      <div className="ip-editor-grid tight">
        <TextField label="Priority" value={fieldText(item, 'priority')} onChange={value => update('priority', value)} readOnly={readOnly} />
        <label className="ip-field">
          <span>Status</span>
          <select value={item.status || 'planned'} onChange={event => update('status', event.target.value)} disabled={readOnly}>
            <option value="planned">计划中</option>
            <option value="in_progress">进行中</option>
            <option value="blocked">阻塞</option>
            <option value="done">已完成</option>
          </select>
        </label>
        <label className="ip-field">
          <span>Phase</span>
          <select value={item.phase || 'later'} onChange={event => update('phase', event.target.value)} disabled={readOnly}>
            <option value="now">Now</option>
            <option value="next">Next</option>
            <option value="later">Later</option>
          </select>
        </label>
        <TextField label="Owner" value={fieldText(item, 'owner')} onChange={value => update('owner', value)} readOnly={readOnly} />
      </div>

      <TextField label="Title" value={fieldText(item, 'title')} onChange={value => update('title', value)} readOnly={readOnly} />
      <TextField label="Why now" value={fieldText(item, 'why_now')} onChange={value => update('why_now', value)} multiline readOnly={readOnly} />
      <TextField label="Current blocker" value={fieldText(item, 'current_blocker')} onChange={value => update('current_blocker', value)} multiline readOnly={readOnly} />
      <TextField
        label="Source-of-truth"
        value={safeArray(item.source_of_truth).join('\n')}
        onChange={value => update('source_of_truth', value.split('\n').map(line => line.trim()).filter(Boolean))}
        multiline
        placeholder="每行一个文档、接口或代码文件"
        readOnly={readOnly}
      />
      <TextField label="Next action" value={fieldText(item, 'next_action')} onChange={value => update('next_action', value)} multiline readOnly={readOnly} />
      <TextField label="Exit condition" value={fieldText(item, 'exit_condition')} onChange={value => update('exit_condition', value)} multiline readOnly={readOnly} />
      <TextField label="Handoff note" value={fieldText(item, 'handoff_note')} onChange={value => update('handoff_note', value)} multiline readOnly={readOnly} />
    </section>
  )
}

function RoleMap({ board }) {
  return (
    <section className="ip-role-map">
      <div className="ip-section-title">
        <span>Document roles</span>
        <strong>防漂移边界</strong>
      </div>
      <div className="ip-role-list">
        {safeArray(board.role_map).map(role => (
          <div className="ip-role" key={role.document}>
            <strong>{role.document}</strong>
            <span>{role.role}</span>
          </div>
        ))}
      </div>
    </section>
  )
}

export default function IterationPriorityPage() {
  const [board, setBoard] = useState(null)
  const [selectedId, setSelectedId] = useState('')
  const [activePhase, setActivePhase] = useState('now')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saveState, setSaveState] = useState('idle')
  const [readOnly] = useState(isViewOnlyUrl)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    fetchIterationPriorityBoard({ signal: controller.signal })
      .then(payload => {
        setBoard(payload)
        const firstNow = safeArray(payload.items).find(item => item.phase === 'now') || safeArray(payload.items)[0]
        setSelectedId(firstNow?.id || '')
        setActivePhase(firstNow?.phase || 'now')
        setError('')
      })
      .catch(err => {
        if (err?.name !== 'AbortError') setError(err.message || '加载迭代板失败')
      })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [])

  const selectedItem = useMemo(
    () => safeArray(board?.items).find(item => item.id === selectedId),
    [board, selectedId]
  )

  const counts = useMemo(() => {
    const items = safeArray(board?.items)
    return {
      total: items.length,
      now: items.filter(item => item.phase === 'now').length,
      blocked: items.filter(item => item.status === 'blocked').length,
      ready: items.filter(item => itemCompleteness(item) === 100).length,
    }
  }, [board])

  const patchItem = (itemId, patch) => {
    if (readOnly) return
    setBoard(current => ({
      ...current,
      items: safeArray(current.items).map(item => (item.id === itemId ? { ...item, ...patch } : item)),
    }))
    if (patch.phase) setActivePhase(patch.phase)
  }

  const addItem = phase => {
    if (readOnly) return
    setBoard(current => {
      const phaseCount = safeArray(current.items).filter(item => item.phase === phase).length
      const item = makeItem(phase, phaseCount + 1)
      setSelectedId(item.id)
      setActivePhase(phase)
      return { ...current, items: [...safeArray(current.items), item] }
    })
  }

  const saveBoard = async () => {
    if (readOnly) return
    if (!board) return
    setSaveState('saving')
    try {
      const saved = await saveIterationPriorityBoard(board)
      setBoard(saved)
      setSaveState('saved')
      setTimeout(() => setSaveState('idle'), 1600)
    } catch (err) {
      setSaveState('error')
      setError(err.message || '保存失败')
    }
  }

  if (loading) return <div className="iteration-page loading">加载迭代界面…</div>

  if (error && !board) {
    return (
      <div className="iteration-page loading">
        <div className="ip-error">{error}</div>
      </div>
    )
  }

  return (
    <div className="iteration-page">
      <header className="ip-topbar">
        <div>
          <div className="ip-overline">GEO Platform</div>
          <h1>{board.title}</h1>
          <p>一个入口管优先级，专题文档管细节，Progress 只管近况与交接。</p>
        </div>
        <div className="ip-actions">
          {readOnly && <span className="ip-readonly-badge">只读分享</span>}
          <span className={`ip-save-state ${saveState}`}>{saveState === 'saving' ? '同步中' : saveState === 'saved' ? '已同步' : saveState === 'error' ? '同步失败' : `Updated ${board.last_updated}`}</span>
          <ShareButton>分享可编辑版</ShareButton>
          <ShareButton viewOnly>分享只读版</ShareButton>
          {!readOnly && (
            <button type="button" className="ip-save" onClick={saveBoard} disabled={saveState === 'saving'}>
              保存到后端
            </button>
          )}
        </div>
      </header>

      {error && <div className="ip-error inline">{error}</div>}

      <section className="ip-stats" aria-label="Iteration board summary">
        <div><span>Total</span><strong>{counts.total}</strong></div>
        <div><span>Now</span><strong>{counts.now}</strong></div>
        <div><span>Blocked</span><strong>{counts.blocked}</strong></div>
        <div><span>Complete</span><strong>{counts.ready}</strong></div>
      </section>

      <div className="ip-workspace">
        <PhaseRail
          board={board}
          activePhase={activePhase}
          selectedId={selectedId}
          onPhaseChange={setActivePhase}
          onSelectItem={(itemId, phase) => {
            setSelectedId(itemId)
            setActivePhase(phase)
          }}
          onAddItem={addItem}
          readOnly={readOnly}
        />
        <ItemEditor item={selectedItem} onChange={patchItem} readOnly={readOnly} />
      </div>

      <div className="ip-bottom">
        <RoleMap board={board} />
        <section className="ip-risk-box">
          <div className="ip-section-title">
            <span>Cross-cutting risks</span>
            <strong>每次保存前扫一遍</strong>
          </div>
          <div className="ip-risk-list">
            {safeArray(board.cross_cutting_risks).map(risk => <span key={risk}>{risk}</span>)}
          </div>
        </section>
      </div>
    </div>
  )
}
