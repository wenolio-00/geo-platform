import { useMemo, useRef, useState } from 'react'
import { runPromptLab } from '../api/geo.js'
import './PromptLabPage.css'

const PLATFORM_OPTIONS = [
  { key: 'GPT', label: 'GPT' },
  { key: 'claude', label: 'Claude' },
  { key: '豆包', label: '豆包' },
  { key: 'DeepSeek', label: 'DeepSeek' },
  { key: 'Tongyi', label: '通义千问' },
]

const DEFAULT_PROMPT = '请介绍杭州兑吧网络科技有限公司的核心业务，并列出可验证来源。'

function formatUsage(usage) {
  if (!usage || typeof usage !== 'object' || Object.keys(usage).length === 0) return '未返回 usage'
  const prompt = usage.prompt_tokens ?? usage.input_tokens
  const completion = usage.completion_tokens ?? usage.output_tokens
  const total = usage.total_tokens
  return [
    prompt !== undefined ? `Prompt ${prompt}` : null,
    completion !== undefined ? `Output ${completion}` : null,
    total !== undefined ? `Total ${total}` : null,
  ].filter(Boolean).join(' · ') || JSON.stringify(usage)
}

function platformStatusText(group) {
  if (!group) return ''
  if (group.success_count > 0 && group.failed_count > 0) return '部分完成'
  if (group.success_count > 0) return '完成'
  return '失败'
}

export default function PromptLabPage() {
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT)
  const [platforms, setPlatforms] = useState(['GPT', 'claude'])
  const [rounds, setRounds] = useState(5)
  const [webSearchEnabled, setWebSearchEnabled] = useState(true)
  const [temperature, setTemperature] = useState(0.2)
  const [maxTokens, setMaxTokens] = useState(1600)
  const [isRunning, setIsRunning] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const abortRef = useRef(null)

  const canRun = useMemo(() => prompt.trim().length > 0 && platforms.length > 0 && !isRunning, [prompt, platforms, isRunning])

  const togglePlatform = (key) => {
    setPlatforms((current) => (
      current.includes(key)
        ? current.filter((item) => item !== key)
        : [...current, key]
    ))
  }

  const handleRun = async () => {
    if (!canRun) return
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    setIsRunning(true)
    setError('')
    setNotice('')
    try {
      const response = await runPromptLab({
        prompt,
        platforms,
        rounds: Number(rounds),
        web_search_enabled: webSearchEnabled,
        temperature: Number(temperature),
        max_tokens: Number(maxTokens),
      }, { signal: controller.signal })
      setResult(response)
      setNotice(`运行完成：${response.platform_results?.length || 0} 个平台`)
    } catch (err) {
      if (err?.name === 'AbortError') {
        setNotice('已取消。本次后端已在途请求会在自身超时后结束，未开始的轮次不会继续发起。')
      } else {
        setError(err?.message || 'Prompt Lab 运行失败')
      }
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null
        setIsRunning(false)
      }
    }
  }

  const handleCancel = () => {
    abortRef.current?.abort()
    abortRef.current = null
    setIsRunning(false)
    setNotice('已取消。本次后端已在途请求会在自身超时后结束，未开始的轮次不会继续发起。')
  }

  return (
    <div className="prompt-lab-page">
      <header className="prompt-lab-header">
        <div>
          <p className="prompt-lab-kicker">Prompt Lab</p>
          <h1>手动多平台调用测试</h1>
        </div>
        <div className="prompt-lab-run-meta">
          {result?.run_id ? <span>{result.run_id}</span> : <span>未运行</span>}
        </div>
      </header>

      <div className="prompt-lab-shell">
        <section className="prompt-lab-controls" aria-label="Prompt Lab controls">
          <label className="prompt-field">
            <span>Prompt</span>
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              rows={10}
              placeholder="输入要测试的 prompt"
            />
          </label>

          <div className="prompt-control-block">
            <div className="prompt-control-title">平台</div>
            <div className="platform-choice-grid">
              {PLATFORM_OPTIONS.map((platform) => (
                <label key={platform.key} className={`platform-choice ${platforms.includes(platform.key) ? 'checked' : ''}`}>
                  <input
                    type="checkbox"
                    checked={platforms.includes(platform.key)}
                    onChange={() => togglePlatform(platform.key)}
                  />
                  <span>{platform.label}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="prompt-settings-grid">
            <label>
              <span>Rounds</span>
              <input
                type="number"
                min="1"
                max="5"
                value={rounds}
                onChange={(event) => setRounds(event.target.value)}
              />
            </label>
            <label>
              <span>Temperature</span>
              <input
                type="number"
                min="0"
                max="2"
                step="0.1"
                value={temperature}
                onChange={(event) => setTemperature(event.target.value)}
              />
            </label>
            <label>
              <span>Max tokens</span>
              <input
                type="number"
                min="256"
                max="8000"
                step="128"
                value={maxTokens}
                onChange={(event) => setMaxTokens(event.target.value)}
              />
            </label>
          </div>

          <label className="prompt-toggle">
            <input
              type="checkbox"
              checked={webSearchEnabled}
              onChange={(event) => setWebSearchEnabled(event.target.checked)}
            />
            <span>Web search</span>
          </label>

          <div className="prompt-action-row">
            <button className="primary-action" disabled={!canRun} onClick={handleRun}>
              {isRunning ? '运行中' : '运行'}
            </button>
            <button className="secondary-action" disabled={!isRunning} onClick={handleCancel}>
              取消
            </button>
            <button className="secondary-action" disabled={isRunning || !result} onClick={() => setResult(null)}>
              清空结果
            </button>
          </div>

          {error ? <div className="prompt-error">{error}</div> : null}
          {notice ? <div className="prompt-notice">{notice}</div> : null}
        </section>

        <section className="prompt-lab-results" aria-label="Prompt Lab results">
          {!result ? (
            <div className="prompt-empty-state">
              <h2>等待运行</h2>
              <p>结果会按平台分组显示，每个平台最多 5 次独立调用。</p>
            </div>
          ) : (
            <>
              <div className="result-summary">
                <div>
                  <span>创建时间</span>
                  <strong>{result.created_at}</strong>
                </div>
                <div>
                  <span>Rounds</span>
                  <strong>{result.rounds}</strong>
                </div>
                <div>
                  <span>Web search</span>
                  <strong>{result.web_search_enabled ? '开启' : '关闭'}</strong>
                </div>
              </div>

              {(result.platform_results || []).map((group) => (
                <PlatformResult key={group.platform} group={group} />
              ))}
            </>
          )}
        </section>
      </div>
    </div>
  )
}

function PlatformResult({ group }) {
  return (
    <section className="platform-result">
      <header className="platform-result-header">
        <div>
          <h2>{group.display_name || group.platform}</h2>
          <p>{group.configured_model || '未配置模型'}</p>
        </div>
        <div className={`platform-status ${group.status === 'failed' ? 'failed' : 'completed'}`}>
          {platformStatusText(group)}
          <span>{group.success_count} success / {group.failed_count} failed</span>
        </div>
      </header>
      <div className="invocation-grid">
        {(group.invocations || []).map((invocation) => (
          <InvocationCard key={`${group.platform}-${invocation.round}`} invocation={invocation} />
        ))}
      </div>
    </section>
  )
}

function InvocationCard({ invocation }) {
  const hasCitations = Array.isArray(invocation.citations) && invocation.citations.length > 0
  return (
    <article className={`invocation-card ${invocation.status}`}>
      <header>
        <div>
          <span className="round-label">Round {invocation.round}</span>
          <strong>{invocation.status === 'success' ? 'Success' : 'Failed'}</strong>
        </div>
        <span>{invocation.model || 'No model'}</span>
      </header>

      {invocation.status === 'failed' ? (
        <div className="invocation-error">{invocation.error || '调用失败'}</div>
      ) : (
        <>
          <pre className="answer-block">{invocation.answer || '未返回回答'}</pre>
          <div className="citation-block">
            <div className="citation-heading">信源</div>
            {hasCitations ? (
              <ul>
                {invocation.citations.map((citation, index) => (
                  <li key={`${citation.url || citation.domain || index}`}>
                    {citation.url ? (
                      <a href={citation.url} target="_blank" rel="noreferrer">
                        {citation.title || citation.url}
                      </a>
                    ) : (
                      <span>{citation.title || citation.domain || '未命名信源'}</span>
                    )}
                    {citation.domain ? <small>{citation.domain}</small> : null}
                    {citation.snippet ? <p>{citation.snippet}</p> : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="empty-citations">未返回信源</p>
            )}
          </div>
          <div className="usage-line">{formatUsage(invocation.usage)}</div>
        </>
      )}
    </article>
  )
}
