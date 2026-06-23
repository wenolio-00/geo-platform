import { useLocation, useSearchParams } from 'react-router-dom'
import { contentVersionId, useContentGenerationViewModel } from '../hooks/useContentGenerationViewModel.js'
import './ContentGenerationPage.css'

function formatDraftTime(value) {
  if (!value) return '未记录时间'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

function IconButton({ label, onClick, disabled, active, children }) {
  return (
    <button className={`cg-icon-btn ${active ? 'active' : ''}`} type="button" aria-label={label} title={label} onClick={onClick} disabled={disabled}>
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
  const vm = useContentGenerationViewModel({
    brandId: searchParams.get('brand_id') || location.state?.brandId,
    brandConfigId: searchParams.get('brand_config_id') || location.state?.brandConfigId,
    actionId: searchParams.get('action_id') || location.state?.actionId,
    ruleId: searchParams.get('rule_id') || location.state?.ruleId,
  })

  if (vm.loading) {
    return <div className="content-generation-page loading">加载中…</div>
  }

  if (vm.loadError) {
    return (
      <div className="content-generation-page loading">
        <div className="cg-empty">{vm.loadError}</div>
      </div>
    )
  }

  if (!vm.contract || !vm.selectedAction || !vm.selectedRule) {
    return <div className="content-generation-page loading">未找到可用的生成输入</div>
  }

  return (
    <div className="content-generation-page">
      <header className="cg-title fade-up">
        <h1>内容生成</h1>
      </header>

      <div className="cg-grid">
        <section className="cg-panel fade-up">
          <div className="cg-panel-h">
            <h2>选择</h2>
          </div>

          <label className="cg-field">
            <span>优化动作</span>
            <select value={vm.selectedActionId} onChange={vm.handleActionChange} disabled={vm.status === 'generating'}>
              {vm.contract.optimization_actions.map(action => (
                <option key={action.action_id} value={action.action_id}>{action.action_name}</option>
              ))}
            </select>
          </label>

          <label className="cg-field">
            <span>内容模板</span>
            <select value={vm.selectedTemplateId} onChange={vm.handleTemplateChange} disabled={vm.status === 'generating' || !vm.templateCandidates.length}>
              {vm.templateCandidates.length ? vm.templateCandidates.map(template => (
                <option key={template.template_id} value={template.template_id}>{template.display_name}</option>
              )) : (
                <option value="">未命中模板</option>
              )}
            </select>
          </label>

          <label className="cg-field">
            <span>历史版本</span>
            <select value={vm.activeVersionId || ''} onChange={vm.handleVersionChange} disabled={!vm.versionsForSelection.length || vm.status === 'generating'}>
              {vm.versionsForSelection.length ? vm.versionsForSelection.map(draft => (
                <option key={contentVersionId(draft)} value={contentVersionId(draft)}>
                  v{draft.version || '?'} · {formatDraftTime(draft.created_at)}
                </option>
              )) : (
                <option value="">暂无版本</option>
              )}
            </select>
          </label>

          <div className="cg-generate-box">
            {vm.error && <div className="cg-error">{vm.error}</div>}
            <button className="cg-primary-btn" type="button" onClick={vm.handleGenerate} disabled={vm.status === 'generating' || vm.staleActionRemoved}>
              {vm.status === 'generating' && <span className="cg-spinner" aria-hidden="true" />}
              {vm.status === 'generating' ? '生成中…' : vm.status === 'error' ? '重试' : '生成内容版本'}
            </button>
            {vm.status === 'error' && (
              <button className="cg-secondary-btn" type="button" onClick={vm.handleReset}>重置</button>
            )}
          </div>
        </section>

        <section className="cg-panel fade-up">
          <div className="cg-panel-h">
            <h2>输出</h2>
          </div>

          <div className="cg-output">
            {vm.activeDraft ? (
              <>
                <div className="cg-text-frame">
                  {vm.status === 'editing' ? (
                    <textarea className="cg-text cg-editor" value={vm.editingText} onChange={(event) => vm.setEditingText(event.target.value)} />
                  ) : (
                    <pre className="cg-text">{vm.activeDraft.generated_text}</pre>
                  )}
                </div>
                {vm.copyState !== 'idle' && (
                  <div className={`cg-copy-note ${vm.copyState}`}>
                    {vm.copyState === 'success' ? '已复制' : '复制失败'}
                  </div>
                )}
                <div className="cg-toolbar">
                  <IconButton label="复制" onClick={vm.handleCopy}><CopyIcon /></IconButton>
                  <IconButton label="有帮助" onClick={() => vm.handleFeedback('helpful')} active={vm.activeDraft.feedback_signal === 'helpful'}><ThumbUpIcon /></IconButton>
                  <IconButton label="没有帮助" onClick={() => vm.handleFeedback('not_helpful')} active={vm.activeDraft.feedback_signal === 'not_helpful'}><ThumbDownIcon /></IconButton>
                  <IconButton label="编辑" onClick={vm.handleEdit} disabled={vm.status === 'editing'}><PencilIcon /></IconButton>
                  <IconButton label="重新生成" onClick={vm.handleGenerate} disabled={vm.status === 'generating' || vm.staleActionRemoved}><RegenerateIcon /></IconButton>
                </div>
              </>
            ) : (
              <div className="cg-empty">
                {vm.status === 'generating' ? '正在生成草稿，请稍候…' : '选择优化动作后，点击生成内容版本。'}
              </div>
            )}
            {vm.feedbackError && <div className="cg-error">{vm.feedbackError}</div>}
            {vm.status === 'editing' && (
              <div className="cg-edit-actions">
                <button className="cg-primary-btn" type="button" onClick={vm.handleSaveEdit} disabled={!vm.editingText.trim()}>保存</button>
                <button className="cg-secondary-btn" type="button" onClick={vm.handleCancelEdit}>放弃</button>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
