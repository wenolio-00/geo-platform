import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  computeContentEffectAttribution,
  fetchContentGenerationContext,
  generateOptimizedDraft,
  saveContentVersionEdit,
  submitContentFeedback,
} from '../api/geo.js'

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

export function contentVersionId(draft) {
  return draft?.content_version_id || draft?.draft_id
}

function makeContract(context) {
  return {
    contract_version: context.contract_version,
    snapshot_date: context.snapshot_date,
    main_brand: context.brand,
    optimization_actions: context.actions || [],
    cross_topic_rules: context.rules || [],
    rule_activation: context.rule_activation,
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
        rule_id: rule.active_rule_id || rule.rule_id,
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

function getLatestVersion(drafts, actionId, ruleId) {
  return drafts
    .filter(draft => draft.action_id === actionId && draft.rule_id === ruleId)
    .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))[0] || null
}

function validateDraftFreshness(draft, currentContract) {
  if (draft.contract_version !== currentContract.contract_version) {
    return {
      stale: true,
      action_exists: currentContract.optimization_actions.some(action => action.action_id === draft.action_id),
      rule_exists: getRuleCandidates(currentContract).some(rule => rule.rule_id === draft.rule_id || rule.source_rule_id === draft.rule_id),
      reason: 'contract_changed',
    }
  }
  const actionExists = currentContract.optimization_actions.some(action => action.action_id === draft.action_id)
  const ruleExists = getRuleCandidates(currentContract).some(rule => rule.rule_id === draft.rule_id || rule.source_rule_id === draft.rule_id)
  if (!actionExists || !ruleExists) {
    return { stale: true, action_exists: actionExists, rule_exists: ruleExists, reason: actionExists ? 'rule_removed' : 'action_removed' }
  }
  return { stale: false }
}

function replaceDraft(current, nextDraft) {
  const id = contentVersionId(nextDraft)
  const without = current.filter(draft => contentVersionId(draft) !== id)
  return [nextDraft, ...without].sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))
}

export function useContentGenerationViewModel(initialParams = {}) {
  const [context, setContext] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [selectedActionId, setSelectedActionId] = useState('')
  const [selectedRuleId, setSelectedRuleId] = useState('')
  const [selectedTemplateId, setSelectedTemplateId] = useState('')
  const [status, setStatus] = useState('idle')
  const [drafts, setDrafts] = useState([])
  const [activeVersionId, setActiveVersionId] = useState(null)
  const [editingText, setEditingText] = useState('')
  const [error, setError] = useState(null)
  const [feedbackError, setFeedbackError] = useState(null)
  const [copyState, setCopyState] = useState('idle')
  const [attributionBusy, setAttributionBusy] = useState(false)

  const dispatch = useCallback((event) => {
    setStatus(current => STATUS_TRANSITIONS[current]?.[event] || current)
  }, [])

  const brandId = initialParams.brandId || initialParams.brand_id || ''
  const brandConfigId = initialParams.brandConfigId || initialParams.brand_config_id || ''
  const initialActionId = initialParams.actionId || initialParams.action_id || ''
  const initialRuleId = initialParams.ruleId || initialParams.rule_id || ''

  useEffect(() => {
    let mounted = true

    setLoading(true)
    fetchContentGenerationContext({
      brand_id: brandId,
      brand_config_id: brandConfigId,
      action_id: initialActionId,
      rule_id: initialRuleId,
    })
      .then(data => {
        if (!mounted) return
        const contract = makeContract(data)
        const action = resolveAction(contract, initialActionId || data.defaults?.action_id)
        const rule = resolveRule(contract, initialRuleId || data.defaults?.rule_id, action)
        const versions = data.content_versions || []
        const latestDraft = getLatestVersion(versions, action?.action_id || '', rule?.rule_id || '')

        setContext(data)
        setDrafts(versions)
        setSelectedActionId(action?.action_id || '')
        setSelectedRuleId(rule?.rule_id || '')
        setSelectedTemplateId(data.template_recommendation?.template_id || data.defaults?.template_id || '')
        setActiveVersionId(contentVersionId(latestDraft) || null)
        setLoadError(null)
        setLoading(false)
        dispatch(latestDraft ? 'RESTORE_SUCCESS' : 'SELECT_EMPTY')
      })
      .catch(err => {
        if (!mounted) return
        setLoadError(err.message || '内容生成上下文加载失败')
        setLoading(false)
        dispatch('LOAD_ERROR')
      })

    return () => {
      mounted = false
    }
  }, [brandId, brandConfigId, initialActionId, initialRuleId, dispatch])

  const contract = useMemo(() => context ? makeContract(context) : null, [context])
  const selectedAction = useMemo(() => contract ? resolveAction(contract, selectedActionId) : null, [contract, selectedActionId])
  const selectedRule = useMemo(() => contract ? resolveRule(contract, selectedRuleId, selectedAction) : null, [contract, selectedRuleId, selectedAction])
  const templateContextForAction = context?.templates_by_action?.[selectedActionId] || context || {}
  const templateCandidates = templateContextForAction.template_candidates || []
  const selectedTemplate = templateCandidates.find(template => template.template_id === selectedTemplateId) || templateContextForAction.template_recommendation || null
  const activeDraft = useMemo(() => drafts.find(draft => contentVersionId(draft) === activeVersionId) || null, [activeVersionId, drafts])
  const versionsForSelection = useMemo(() => (
    drafts
      .filter(draft => draft.action_id === selectedActionId && draft.rule_id === selectedRuleId)
      .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))
  ), [drafts, selectedActionId, selectedRuleId])
  const freshness = useMemo(() => {
    if (!activeDraft || !contract) return null
    return validateDraftFreshness(activeDraft, contract)
  }, [activeDraft, contract])
  const staleActionRemoved = Boolean(freshness?.stale && freshness.action_exists === false)

  const restoreVersionForSelection = useCallback((actionId, ruleId) => {
    const latestDraft = getLatestVersion(drafts, actionId, ruleId)
    setActiveVersionId(contentVersionId(latestDraft) || null)
    setEditingText('')
    setError(null)
    setFeedbackError(null)
    dispatch(latestDraft ? 'RESTORE_SUCCESS' : 'SELECT_EMPTY')
  }, [dispatch, drafts])

  const handleActionChange = useCallback((event) => {
    if (!contract) return
    const action = resolveAction(contract, event.target.value)
    const rule = resolveRule(contract, '', action)
    const nextTemplate = context?.templates_by_action?.[action?.action_id]?.template_recommendation || context?.template_recommendation
    setSelectedActionId(action?.action_id || '')
    setSelectedRuleId(rule?.rule_id || '')
    setSelectedTemplateId(nextTemplate?.template_id || '')
    restoreVersionForSelection(action?.action_id || '', rule?.rule_id || '')
  }, [context, contract, restoreVersionForSelection])

  const handleVersionChange = useCallback((event) => {
    setActiveVersionId(event.target.value || null)
    setEditingText('')
    setFeedbackError(null)
    dispatch(event.target.value ? 'RESTORE_SUCCESS' : 'SELECT_EMPTY')
  }, [dispatch])

  const handleTemplateChange = useCallback((event) => {
    setSelectedTemplateId(event.target.value)
  }, [])

  const handleGenerate = useCallback(async () => {
    if (!context || !selectedAction || !selectedRule || staleActionRemoved) return

    setError(null)
    setEditingText('')
    setActiveVersionId(null)
    dispatch('GENERATE')

    try {
      const generatedDraft = await generateOptimizedDraft({
        brand_id: context.brand.brand_id,
        brand_config_id: context.brand.brand_config_id,
        action_id: selectedAction.action_id,
        rule_id: selectedRule.rule_id,
        template_id: selectedTemplate?.template_id,
        template_version: selectedTemplate?.template_version,
        contract_version: context.contract_version,
      })
      const nextDraft = {
        ...generatedDraft,
        brand_id: context.brand.brand_id,
        action_id: selectedAction.action_id,
        rule_id: selectedRule.rule_id,
        contract_version: context.contract_version,
      }
      setDrafts(current => replaceDraft(current, nextDraft))
      setActiveVersionId(contentVersionId(nextDraft))
      dispatch('RESOLVE')
    } catch (err) {
      setActiveVersionId(null)
      setError(err.message || '生成失败，请稍后重试')
      dispatch('REJECT')
    }
  }, [context, dispatch, selectedAction, selectedRule, selectedTemplate, staleActionRemoved])

  const handleEdit = useCallback(() => {
    if (!activeDraft) return
    setEditingText(activeDraft.generated_text)
    dispatch('EDIT')
  }, [activeDraft, dispatch])

  const handleSaveEdit = useCallback(async () => {
    if (!activeDraft || !editingText.trim()) return
    try {
      const savedDraft = await saveContentVersionEdit(contentVersionId(activeDraft), {
        generated_text: editingText,
      })
      setDrafts(current => replaceDraft(current, savedDraft))
      setActiveVersionId(contentVersionId(savedDraft))
      setEditingText('')
      setFeedbackError(null)
      dispatch('SAVE')
    } catch (err) {
      setFeedbackError(err.message || '保存编辑失败')
    }
  }, [activeDraft, dispatch, editingText])

  const handleCancelEdit = useCallback(() => {
    setEditingText('')
    dispatch('CANCEL')
  }, [dispatch])

  const handleCopy = useCallback(async () => {
    const text = status === 'editing' ? editingText : activeDraft?.generated_text
    if (!text) return
    try {
      await navigator.clipboard.writeText(text)
      setCopyState('success')
      window.setTimeout(() => setCopyState('idle'), 1800)
    } catch {
      setCopyState('error')
      window.setTimeout(() => setCopyState('idle'), 1800)
    }
  }, [activeDraft, editingText, status])

  const handleFeedback = useCallback(async (signal) => {
    if (!activeDraft) return
    setFeedbackError(null)
    try {
      const result = await submitContentFeedback(contentVersionId(activeDraft), { signal })
      setDrafts(current => current.map(draft => (
        contentVersionId(draft) === contentVersionId(activeDraft)
          ? { ...draft, feedback_summary: result.feedback_summary, feedback_signal: signal }
          : draft
      )))
    } catch (err) {
      setFeedbackError(err.message || '反馈保存失败')
    }
  }, [activeDraft])

  const handleRefreshAttribution = useCallback(async () => {
    if (!activeDraft) return
    setAttributionBusy(true)
    setFeedbackError(null)
    try {
      const attribution = await computeContentEffectAttribution(contentVersionId(activeDraft))
      setDrafts(current => current.map(draft => (
        contentVersionId(draft) === contentVersionId(activeDraft)
          ? { ...draft, effect_attribution: attribution }
          : draft
      )))
    } catch (err) {
      setFeedbackError(err.message || '效果归因刷新失败')
    } finally {
      setAttributionBusy(false)
    }
  }, [activeDraft])

  const handleReset = useCallback(() => {
    setError(null)
    setActiveVersionId(null)
    setEditingText('')
    dispatch('RESET')
  }, [dispatch])

  return {
    activeDraft,
    activeVersionId,
    attributionBusy,
    brandMaterialSummary: templateContextForAction?.brand_material_summary || context?.brand_material_summary,
    context,
    contract,
    copyState,
    editingText,
    error,
    feedbackError,
    freshness,
    handleActionChange,
    handleCancelEdit,
    handleCopy,
    handleEdit,
    handleFeedback,
    handleGenerate,
    handleRefreshAttribution,
    handleReset,
    handleSaveEdit,
    handleTemplateChange,
    handleVersionChange,
    loading,
    loadError,
    selectedAction,
    selectedActionId,
    selectedRule,
    selectedRuleId,
    selectedTemplate,
    selectedTemplateId,
    setEditingText,
    staleActionRemoved,
    status,
    templateCandidates,
    versionsForSelection,
  }
}
