import { useCallback, useEffect, useMemo, useState } from 'react'
import { useLocation, useSearchParams } from 'react-router-dom'
import { fetchContentGenerationContext, generateOptimizedDraft } from '../api/geo.js'
import { intentLabel } from '../mock/data.js'
import './ContentGenerationPage.css'

const DEFAULT_BRAND_ID = 10001

const STATUS_TRANSITIONS = {
  idle: {
    GENERATE: 'generating',
    RESTORE_SUCCESS: 'success',
    SELECT_EMPTY: 'idle',
    LOAD_ERROR: 'error',
  },
  generating: {
    RESOLVE: 'success',
    REJECT: 'error',
  },
  success: {
    EDIT: 'editing',
    GENERATE: 'generating',
    RESTORE_SUCCESS: 'success',
    SELECT_EMPTY: 'idle',
  },
  editing: {
    SAVE: 'success',
    CANCEL: 'success',
    GENERATE: 'generating',
    RESTORE_SUCCESS: 'success',
    SELECT_EMPTY: 'idle',
  },
  error: {
    GENERATE: 'generating',
    RESET: 'idle',
    RESTORE_SUCCESS: 'success',
    SELECT_EMPTY: 'idle',
  },
}

function makeContract(context) {
  return {
    contract_version: context.contract_version,
    snapshot_date: context.snapshot_date,
    main_brand: context.brand,
    optimization_actions: context.actions,
    cross_topic_rules: context.rules,
  }
}

function resolveAction(contract, actionId) {
  return contract.optimization_actions.find(action => action.action_id === actionId) || contract.optimization_actions[0] || null
}

function getRuleCandidates(contract) {
  const activeRules = contract.rule_activation?.stores?.active_rules_store
  if (activeRules?.length) {
    return activeRules
      .filter(rule => rule.status === 'active')
      .sort((a, b) => Number(a.source_type === 'baseline') - Number(b.source_type === 'baseline'))
      .map(rule => ({
        ...rule,
        rule_id: rule.active_rule_id,
        source_rule_id: rule.source_rule_id,
        rule_name: rule.rule_name,
        applies_to: rule.applies_to?.length ? rule.applies_to : [rule.action_type],
      }))
  }
  return contract.cross_topic_rules || []
}

function resolveRule(contract, ruleId, action) {
  const rules = getRuleCandidates(contract)
  const direct = rules.find(rule => rule.rule_id === ruleId || rule.source_rule_id === ruleId)
  if (direct) return direct
  if (action) {
    return rules.find(rule => rule.applies_to.includes(action.action_type)) || rules[0] || null
  }
  return rules[0] || null
}

function validateDraftFreshness(draft, currentContract) {
  if (draft.contract_version !== currentContract.contract_version) {
    return {
      stale: true,
      action_exists: currentContract.optimization_actions.some(action => action.action_id === draft.action_id),
      rule_exists: currentContract.cross_topic_rules.some(rule => rule.rule_id === draft.rule_id),
    }
  }
  return { stale: false }
}

function formatDraftTime(value) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

function getNextDraftVersion(drafts, actionId, ruleId) {
  return drafts.filter(draft => draft.action_id === actionId && draft.rule_id === ruleId).length + 1
}

function getLatestDraft(drafts, actionId, ruleId) {
  return drafts
    .filter(draft => draft.action_id === actionId && draft.rule_id === ruleId)
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0] || null
}

function IconButton({ label, onClick, disabled, children }) {
  return (
    <button className="cg-icon-btn" type="button" aria-label={label} title={label} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  )
}

function CopyIcon() {
  return (
    <svg viewBox="0 0 40 40" aria-hidden="true">
      <rect x="15" y="14" width="17" height="20" rx="3.5" />
      <rect x="7" y="7" width="17" height="20" rx="3.5" />
    </svg>
  )
}

function ThumbUpIcon() {
  return (
    <svg viewBox="0 0 40 40" aria-hidden="true">
      <path d="M16 32h13.2c2.4 0 3.8-1.4 4.1-3.7l1.2-8.2c.4-2.8-1.1-4.7-3.8-4.7h-6.2l.8-5.3c.3-1.9-.8-3.4-2.7-3.8-1.5-.3-2.5.5-3.2 2.1l-3.1 6.8c-.6 1.5-1.5 2.5-3 3.2l-2 1c-1.7.8-2.5 2.1-2.5 4v4.1c0 2.8 1.7 4.5 4.5 4.5Z" />
    </svg>
  )
}

function ThumbDownIcon() {
  return (
    <svg viewBox="0 0 40 40" aria-hidden="true">
      <path d="M24 8H10.8C8.4 8 7 9.4 6.7 11.7l-1.2 8.2c-.4 2.8 1.1 4.7 3.8 4.7h6.2l-.8 5.3c-.3 1.9.8 3.4 2.7 3.8 1.5.3 2.5-.5 3.2-2.1l3.1-6.8c.6-1.5 1.5-2.5 3-3.2l2-1c1.7-.8 2.5-2.1 2.5-4v-4.1C31.2 9.7 29.5 8 26.7 8Z" />
    </svg>
  )
}

function PencilIcon() {
  return (
    <svg viewBox="0 0 40 40" aria-hidden="true">
      <path d="M21.6 5.9 30 9.3c1.3.5 1.9 1.9 1.4 3.2L22.5 32 10.8 38 7.5 25.4l8.9-19.3c.5-1.2 2-1.7 3.2-1.2Z" />
      <path d="m14.1 12 13.7 5.7" />
    </svg>
  )
}

function RegenerateIcon() {
  return (
    <svg viewBox="0 0 40 40" aria-hidden="true">
      <path d="M7 9h10v10" />
      <path d="M17 9 7 19" />
      <path d="M20.5 8.5a15 15 0 1 1-12 8.8" />
    </svg>
  )
}

export default function ContentGenerationPage() {
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const actionIdParam = searchParams.get('action_id')
  const ruleIdParam = searchParams.get('rule_id')

  const [context, setContext] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [selectedActionId, setSelectedActionId] = useState('')
  const [selectedRuleId, setSelectedRuleId] = useState('')
  const [status, setStatus] = useState('idle')
  const [drafts, setDrafts] = useState([])
  const [activeDraftId, setActiveDraftId] = useState(null)
  const [editingText, setEditingText] = useState('')
  const [error, setError] = useState(null)

  const dispatch = useCallback((event) => {
    setStatus(current => STATUS_TRANSITIONS[current]?.[event] || current)
  }, [])

  useEffect(() => {
    let mounted = true

    fetchContentGenerationContext({ brand_id: DEFAULT_BRAND_ID })
      .then(data => {
        if (!mounted) return
        const contract = makeContract(data)
        const actionId = actionIdParam || location.state?.actionId || data.defaults.action_id
        const action = resolveAction(contract, actionId)
        const ruleId = ruleIdParam || location.state?.ruleId || resolveRule(contract, '', action)?.rule_id || data.defaults.rule_id
        const rule = resolveRule(contract, ruleId, action)

        setContext(data)
        setSelectedActionId(action?.action_id || '')
        setSelectedRuleId(rule?.rule_id || '')
        setActiveDraftId(null)
        setLoading(false)
        dispatch('SELECT_EMPTY')
      })
      .catch(err => {
        if (!mounted) return
        setLoadError(err.message || '内容生成上下文加载失败')
        setLoading(false)
      })

    return () => {
      mounted = false
    }
  }, [actionIdParam, dispatch, location.state, ruleIdParam])

  const contract = useMemo(() => context ? makeContract(context) : null, [context])
  const selectedAction = useMemo(() => contract ? resolveAction(contract, selectedActionId) : null, [contract, selectedActionId])
  const selectedRule = useMemo(() => contract ? resolveRule(contract, selectedRuleId, selectedAction) : null, [contract, selectedRuleId, selectedAction])
  const activeDraft = useMemo(() => drafts.find(draft => draft.draft_id === activeDraftId) || null, [activeDraftId, drafts])
  const freshness = useMemo(() => {
    if (!activeDraft || !contract) return null
    return validateDraftFreshness(activeDraft, contract)
  }, [activeDraft, contract])
  const staleActionRemoved = Boolean(freshness?.stale && freshness.action_exists === false)

  const restoreDraftForSelection = useCallback((actionId, ruleId) => {
    const latestDraft = getLatestDraft(drafts, actionId, ruleId)
    setActiveDraftId(latestDraft?.draft_id || null)
    setEditingText('')
    setError(null)
    dispatch(latestDraft ? 'RESTORE_SUCCESS' : 'SELECT_EMPTY')
  }, [dispatch, drafts])

  function handleActionChange(event) {
    if (!contract) return
    const action = resolveAction(contract, event.target.value)
    const rule = resolveRule(contract, '', action)
    setSelectedActionId(action?.action_id || '')
    setSelectedRuleId(rule?.rule_id || '')
    restoreDraftForSelection(action?.action_id || '', rule?.rule_id || '')
  }

  async function handleGenerate() {
    if (!context || !selectedAction || !selectedRule || staleActionRemoved) return

    setError(null)
    setEditingText('')
    setActiveDraftId(null)
    dispatch('GENERATE')

    try {
      const generatedDraft = await generateOptimizedDraft({
        brand_id: context.brand.brand_id,
        action_id: selectedAction.action_id,
        rule_id: selectedRule.rule_id,
        contract_version: context.contract_version,
      })
      const nextDraft = {
        ...generatedDraft,
        brand_id: context.brand.brand_id,
        action_id: selectedAction.action_id,
        rule_id: selectedRule.rule_id,
        contract_version: context.contract_version,
        version: getNextDraftVersion(drafts, selectedAction.action_id, selectedRule.rule_id),
        parent_draft_id: null,
      }
      setDrafts(current => [...current, nextDraft])
      setActiveDraftId(nextDraft.draft_id)
      dispatch('RESOLVE')
    } catch (err) {
      setActiveDraftId(null)
      setError(err.message || '生成失败，请稍后重试')
      dispatch('REJECT')
    }
  }

  function handleEdit() {
    if (!activeDraft) return
    setEditingText(activeDraft.generated_text)
    dispatch('EDIT')
  }

  function handleSaveEdit() {
    if (!activeDraft || !selectedAction || !selectedRule || !editingText.trim()) return
    const nextDraft = {
      ...activeDraft,
      draft_id: `draft_${Date.now()}_manual`,
      version: getNextDraftVersion(drafts, activeDraft.action_id, activeDraft.rule_id),
      generated_text: editingText,
      generation_source: 'manual_edit',
      parent_draft_id: activeDraft.draft_id,
      created_at: new Date().toISOString(),
    }

    setDrafts(current => [...current, nextDraft])
    setActiveDraftId(nextDraft.draft_id)
    setEditingText('')
    dispatch('SAVE')
  }

  function handleCancelEdit() {
    setEditingText('')
    dispatch('CANCEL')
  }

  async function handleCopy() {
    const text = status === 'editing' ? editingText : activeDraft?.generated_text
    if (!text) return
    await navigator.clipboard.writeText(text)
  }

  function handleReset() {
    setError(null)
    setActiveDraftId(null)
    setEditingText('')
    dispatch('RESET')
  }

  if (loading) {
    return <div className="content-generation-page loading">加载中…</div>
  }

  if (loadError) {
    return <div className="content-generation-page loading">{loadError}</div>
  }

  if (!contract || !selectedAction || !selectedRule) {
    return <div className="content-generation-page loading">未找到可用的生成输入</div>
  }

  return (
    <div className="content-generation-page">
      <div className="cg-hero fade-up">
        <div className="cg-over">内容生成</div>
        <h1>用规则和优化动作生成可发布文本</h1>
        <p>选择优化动作，异步生成可编辑、可追踪版本的发布草稿。</p>
      </div>

      <div className="cg-grid">
        <section className="cg-panel fade-up">
          <div className="cg-panel-h">
            <h2>优化动作</h2>
            <span className="cg-meta">生成方向</span>
          </div>

          <label className="cg-field">
            <span>优化动作</span>
            <select value={selectedActionId} onChange={handleActionChange} disabled={status === 'generating'}>
              {contract.optimization_actions.map(action => (
                <option key={action.action_id} value={action.action_id}>{action.action_name}</option>
              ))}
            </select>
          </label>

          <div className="cg-generate-box">
            {error && <div className="cg-error">{error}</div>}
            <button className="cg-primary-btn" type="button" onClick={handleGenerate} disabled={status === 'generating' || staleActionRemoved}>
              {status === 'generating' && <span className="cg-spinner" aria-hidden="true" />}
              {status === 'generating' ? '生成中…' : status === 'error' ? '重试' : '生成优化草稿'}
            </button>
            {status === 'error' && (
              <button className="cg-secondary-btn" type="button" onClick={handleReset}>重置</button>
            )}
          </div>
        </section>

        <section className="cg-panel fade-up">
          <div className="cg-panel-h">
            <h2>优化后的文本</h2>
            {activeDraft ? (
              <span className="cg-version">v{activeDraft.version} · {activeDraft.generation_source} · {formatDraftTime(activeDraft.created_at)}</span>
            ) : (
              <span className="cg-meta">生成草稿</span>
            )}
          </div>

          {freshness?.stale && (
            <div className={`cg-alert ${freshness.action_exists ? 'info' : 'warning'}`}>
              {freshness.action_exists ? '诊断数据已更新，建议重新生成。' : '该优化动作已在最新诊断中移除，请选择其他动作。'}
            </div>
          )}

          <div className="cg-output">
            {activeDraft ? (
              <>
                <div className="cg-text-frame">
                  {status === 'editing' ? (
                    <textarea className="cg-text cg-editor" value={editingText} onChange={(event) => setEditingText(event.target.value)} />
                  ) : (
                    <pre className="cg-text">{activeDraft.generated_text}</pre>
                  )}
                </div>
                <div className="cg-toolbar">
                  <IconButton label="复制" onClick={handleCopy}><CopyIcon /></IconButton>
                  <IconButton label="有帮助"><ThumbUpIcon /></IconButton>
                  <IconButton label="没有帮助"><ThumbDownIcon /></IconButton>
                  <IconButton label="编辑" onClick={handleEdit} disabled={status === 'editing'}><PencilIcon /></IconButton>
                  <IconButton label="重新生成" onClick={handleGenerate} disabled={status === 'generating' || staleActionRemoved}><RegenerateIcon /></IconButton>
                </div>
              </>
            ) : (
              <div className="cg-empty">
                {status === 'generating' ? '正在生成草稿，请稍候…' : '选择优化动作后，点击生成优化草稿。'}
              </div>
            )}
            {status === 'editing' && (
              <div className="cg-edit-actions">
                <button className="cg-primary-btn" type="button" onClick={handleSaveEdit} disabled={!editingText.trim()}>保存</button>
                <button className="cg-secondary-btn" type="button" onClick={handleCancelEdit}>放弃</button>
              </div>
            )}
          </div>

          {activeDraft && (
            <>
              <div className="cg-output">
                <div className="cg-output-h">推荐发布平台</div>
                <div className="cg-platforms">
                  {activeDraft.publish_platforms.map(platform => (
                    <span className="cg-pill" key={platform}>{platform}</span>
                  ))}
                </div>
              </div>

              <div className="cg-output">
                <div className="cg-output-h">目标意图</div>
                <div className="cg-tags">
                  {activeDraft.target_intents.map(intentId => (
                    <span className="cg-tag" key={intentId}>{intentLabel(intentId)}</span>
                  ))}
                </div>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  )
}
