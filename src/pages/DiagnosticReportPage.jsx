import { useEffect, useMemo, useRef, useState } from 'react'
import { fetchDiagnosticReportData, fetchDiagnosticRun } from '../api/geo.js'
import { buildReportDisplayData, getReportDataState } from '../lib/reportDataAdapter.js'
import { generateReportHtml } from '../lib/reportGenerator.js'
import './DiagnosticReportPage.css'

const DEFAULT_GENERATION_TIME_MS = 3 * 60 * 1000
const ACTIVE_RUN_STATUSES = ['queued', 'running', 'aggregating']
const REPORT_EDITOR_STORAGE_PREFIX = 'geo-diagnostic-report-hidden-sections'
const EDITABLE_REPORT_SECTIONS = [
  { id: 'executive_summary', title: '00 Executive Summary' },
  { id: 'overview', title: '全局概览与核心指标' },
  { id: 'insights', title: '01 关键问题&优化建议' },
  { id: 'sources', title: '02 信源引用情况' },
  { id: 'platforms', title: '03 六平台健康度' },
  { id: 'topic_platform_visibility', title: '03A 分话题可见度表现' },
  { id: 'competitors', title: '04 竞品排名与差距' },
  { id: 'sentiment', title: '05 品牌调性分析' },
  { id: 'brand_config', title: '06 品牌配置' },
]
const EDITABLE_REPORT_SECTION_IDS = new Set(EDITABLE_REPORT_SECTIONS.map(section => section.id))

function getRunIdFromLocation() {
  return new URLSearchParams(window.location.search).get('run_id')
}

function getReportEditorStorageKey(runId) {
  return `${REPORT_EDITOR_STORAGE_PREFIX}:${runId || 'default'}`
}

function readHiddenSections(runId) {
  try {
    const raw = window.localStorage.getItem(getReportEditorStorageKey(runId))
    const parsed = raw ? JSON.parse(raw) : []
    return new Set(Array.isArray(parsed) ? parsed.filter(id => EDITABLE_REPORT_SECTION_IDS.has(id)) : [])
  } catch {
    return new Set()
  }
}

function writeHiddenSections(runId, hiddenSections) {
  try {
    window.localStorage.setItem(getReportEditorStorageKey(runId), JSON.stringify([...hiddenSections]))
  } catch {
    // Local persistence is a convenience; report editing still works in memory.
  }
}

function backendErrorContext(error) {
  const context = {
    http_status: error?.status,
    error_code: error?.error_code,
    endpoint: error?.endpoint,
    stage: error?.stage,
    run_id: error?.run_id,
    brand_config_id: error?.brand_config_id,
    brand_id: error?.brand_id,
    action_id: error?.action_id,
    rule_id: error?.rule_id,
    terminal_reason: error?.terminal_reason,
    retriable: error?.retriable,
  }
  return Object.fromEntries(Object.entries(context).filter(([, value]) => value !== undefined && value !== null && value !== ''))
}

function StatusState({ title, detail, progress = null, estimatedGenerationTime = null, showProgress = false, errorContext = null }) {
  const hasProgress = Number.isFinite(Number(progress))
  const progressValue = hasProgress ? Math.max(0, Math.min(100, Math.round(Number(progress)))) : 0
  const contextEntries = errorContext ? Object.entries(errorContext) : []

  return (
    <div className="diagnostic-report-shell">
      <div className="report-state-card">
        <div className="report-state-eyebrow">GEO 诊断报告</div>
        <h1>{title}</h1>
        {detail ? <p>{detail}</p> : null}
        {contextEntries.length ? (
          <dl className="report-error-context">
            {contextEntries.map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd>{String(value)}</dd>
              </div>
            ))}
          </dl>
        ) : null}
        {(showProgress || hasProgress || estimatedGenerationTime) ? (
          <div className="report-state-progress">
            <div className="report-progress-top">
              <span>预计还需时间</span>
              <strong>{estimatedGenerationTime || '计算中'}</strong>
            </div>
            <div
              className="report-progress-track"
              role="progressbar"
              aria-label="诊断报告生成进度"
              aria-valuemin="0"
              aria-valuemax="100"
              aria-valuenow={progressValue}
            >
              <div className="report-progress-fill" style={{ width: `${progressValue}%` }} />
            </div>
            <div className="report-progress-bottom">
              <span>当前进度</span>
              <span>{progressValue}%</span>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}

function displayValue(value, decimals = 1, suffix = '') {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '未采集'
  return `${Number(value).toFixed(decimals)}${suffix}`
}

function displayPercent(value, decimals = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '未采集'
  return `${(Number(value) * 100).toFixed(decimals)}%`
}

function numberClass(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 'neutral'
  if (value >= 75) return 'ok'
  if (value >= 20) return 'warn'
  return 'risk'
}

function getProgressValue(value) {
  if (!Number.isFinite(Number(value))) return null
  return Math.max(0, Math.min(100, Math.round(Number(value))))
}

function formatDuration(ms) {
  if (!Number.isFinite(ms) || ms <= 0) return '计算中'
  const seconds = Math.max(1, Math.round(ms / 1000))
  if (seconds < 60) return `${seconds} 秒`
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  return rest ? `${minutes} 分 ${rest} 秒` : `${minutes} 分钟`
}

function parseTimestamp(value) {
  if (!value) return null
  const timestamp = Date.parse(value)
  return Number.isFinite(timestamp) ? timestamp : null
}

function getRunStartTime(run, fallbackStartedAt) {
  return (
    parseTimestamp(run?.inspection_started_at) ||
    parseTimestamp(run?.inspectionStartedAt) ||
    parseTimestamp(run?.created_at) ||
    parseTimestamp(run?.createdAt) ||
    fallbackStartedAt
  )
}

function getEstimatedGenerationTime(run, progress, startedAt) {
  if (progress >= 100) return '即将完成'

  const explicitRemaining = run?.estimated_remaining_ms ?? run?.estimatedRemainingMs
  if (explicitRemaining !== null && explicitRemaining !== undefined) {
    const explicitRemainingMs = Number(explicitRemaining)
    if (Number.isFinite(explicitRemainingMs)) {
      return explicitRemainingMs > 0 ? `还需约 ${formatDuration(explicitRemainingMs)}` : '即将完成'
    }
  }

  const explicitEstimate = run?.estimated_generation_time || run?.estimatedGenerationTime
  if (explicitEstimate) return String(explicitEstimate)

  if (!startedAt) return '计算中'
  const elapsedMs = Math.max(0, Date.now() - startedAt)
  const remainingMs = DEFAULT_GENERATION_TIME_MS - elapsedMs
  if (remainingMs <= 0) return progress >= 92 ? '即将完成' : '已超出预估，正在继续处理'
  return `还需约 ${formatDuration(remainingMs)}`
}

function Section({ number, title, children }) {
  return (
    <section className="dr-sec">
      <div className="dr-sec-h">
        <span className="dr-sec-n">{number}</span>
        <span className="dr-sec-t">{title}</span>
      </div>
      {children}
    </section>
  )
}

function ReportSection({ number, title, children }) {
  return (
    <section className="dr-report-section">
      <div className="dr-report-section-h">
        <span className="dr-report-section-n">{number}</span>
        <span className="dr-report-section-dot">·</span>
        <span className="dr-report-section-t">{title}</span>
      </div>
      {children}
    </section>
  )
}

function EditableReportBlock({ title, editMode, onRemove, children }) {
  if (!editMode) return <>{children}</>
  return (
    <div className="dr-edit-frame">
      <div className="dr-edit-toolbar">
        <span>{title}</span>
        <button type="button" className="dr-edit-remove" onClick={onRemove}>移除</button>
      </div>
      {children}
    </div>
  )
}

function ReportEditPanel({ hiddenSections, editMode, onRestore, onRestoreAll }) {
  if (!editMode) return null
  const hidden = EDITABLE_REPORT_SECTIONS.filter(section => hiddenSections.has(section.id))
  return (
    <div className="dr-edit-panel">
      <div>
        <strong>编辑模式</strong>
        <span>移除不需要的模块后，导出的 HTML 会同步删减。</span>
      </div>
      {hidden.length ? (
        <div className="dr-edit-hidden">
          <span>已隐藏</span>
          {hidden.map(section => (
            <button type="button" key={section.id} onClick={() => onRestore(section.id)}>{section.title}</button>
          ))}
          <button type="button" className="dr-edit-restore-all" onClick={onRestoreAll}>恢复全部</button>
        </div>
      ) : null}
    </div>
  )
}

function EmptyState({ title, detail = '该模块没有可展示的巡检聚合数据。' }) {
  return <div className="dr-empty"><b>{title}</b><span>{detail}</span></div>
}

function MiniBar({ value, type = 'n' }) {
  const width = Number.isFinite(Number(value)) ? Math.max(0, Math.min(100, Number(value))) : 0
  return <div className="dr-bar"><div className={`dr-bar-f ${type}`} style={{ width: `${width}%` }} /></div>
}

function percentValue(value) {
  return Number.isFinite(Number(value)) ? Math.max(0, Math.min(100, Number(value) * 100)) : 0
}

function formatReportDate(value) {
  return value ? String(value).replace(/[./]/g, '-') : '未采集'
}

function displayPlatformName(value) {
  const raw = String(value || '').trim()
  if (!raw) return '未采集'
  if (raw.toLowerCase() === 'claude') return 'Claude'
  return raw
}

function buildPlatformSummary(data) {
  const platforms = data.display.platforms.length
    ? data.display.platforms.map(platform => platform.name)
    : data.display.topic_platform_visibility.flatMap(topic => topic.platforms.map(platform => platform.platform))
  const uniquePlatforms = Array.from(new Set(platforms.filter(Boolean)))
  const model = data.display.source_references
    .flatMap(source => source.references || [])
    .map(ref => ref.model)
    .find(Boolean)
  if (uniquePlatforms.length === 1) {
    const platform = displayPlatformName(uniquePlatforms[0])
    return model ? `${platform} (${model} · 联网)` : platform
  }
  return uniquePlatforms.length ? uniquePlatforms.map(displayPlatformName).join(' · ') : '未采集'
}

function buildCompetitorSummary(data) {
  const configured = data.brand_config?.competitors?.map(row => row.name).filter(Boolean) || []
  const competitors = configured.length
    ? configured
    : data.display.competitor_ranking.filter(row => !row.is_self).map(row => row.name)
  return competitors.length ? competitors.join(' · ') : '未采集'
}

function ReportTop({ data, editMode, onToggleEdit, onExport }) {
  return (
    <header className="dr-report-top">
      <div className="dr-report-top-inner">
        <div><div className="dr-report-meta-label">巡检日期</div><div className="dr-report-meta-value">{formatReportDate(data.meta.report_date)}</div></div>
        <div><div className="dr-report-meta-label">巡检平台</div><div className="dr-report-meta-value">{buildPlatformSummary(data)}</div></div>
        <div><div className="dr-report-meta-label">巡检样本</div><div className="dr-report-meta-value">{displayValue(data.meta.total_queries, 0)} 条 / 全部成功</div></div>
        <div><div className="dr-report-meta-label">竞品对照</div><div className="dr-report-meta-value">{buildCompetitorSummary(data)}</div></div>
        <div className="dr-head-actions">
          <button type="button" className={`dr-head-action ${editMode ? 'active' : ''}`} onClick={onToggleEdit}>{editMode ? '完成编辑' : '编辑报告'}</button>
          <button type="button" className="dr-head-action" onClick={onExport}>导出 HTML</button>
        </div>
      </div>
    </header>
  )
}

function SentimentChange({ value }) {
  const change = String(value || '').toLowerCase()
  if (change === 'up') return <span className="dr-sent-change up">↑</span>
  if (change === 'down') return <span className="dr-sent-change down">↓</span>
  if (change === 'flat') return <span className="dr-sent-change flat">-</span>
  return <span className="dr-sent-change flat">未采集</span>
}

function Gauge({ score }) {
  const hasScore = Number.isFinite(Number(score))
  const rawScore = hasScore ? Math.max(0, Number(score)) : 0
  const clean = hasScore ? Math.min(100, rawScore) : 0
  const offset = 276.5 * (1 - clean / 100)
  const label = hasScore ? rawScore >= 90 ? '强推荐' : rawScore >= 60 ? '中等推荐' : '待提升' : '未采集'
  const scoreText = hasScore ? Math.round(rawScore) : '—'

  return (
    <div className="dr-g-wrap">
      <div className="dr-g-area">
        <svg className="dr-g-svg" viewBox="0 0 230 130" xmlns="http://www.w3.org/2000/svg">
          <path d="M27 118 A88 88 0 0 1 203 118" fill="none" stroke="#ede9e3" strokeWidth="14" strokeLinecap="round" />
          <path d="M27 118 A88 88 0 0 1 203 118" fill="none" stroke="#2E5FA3" strokeWidth="14" strokeLinecap="round" strokeDasharray="276.5" strokeDashoffset={offset.toFixed(1)} />
          <line x1="204.4" y1="89.0" x2="193.0" y2="92.7" stroke="#2E7D52" strokeWidth="2.5" strokeLinecap="round" />
          <circle cx="198.7" cy="90.8" r="5" fill="#2E7D52" />
        </svg>
        <div className="dr-g-center"><div className="dr-g-val">{scoreText}</div><div className="dr-g-sublabel">{label}</div></div>
      </div>
      <div className="dr-g-legend">
        <div className="dr-g-leg-row"><div className="ll"><span className="dr-g-leg-dot" style={{ background: '#2E5FA3' }} /><span>当前评分</span></div><span className="dr-g-leg-val" style={{ color: '#2E5FA3' }}>{scoreText}</span></div>
        <div className="dr-g-leg-row"><div className="ll"><span className="dr-g-leg-dot" style={{ background: '#2E7D52' }} /><span>行业推荐线</span></div><span className="dr-g-leg-val" style={{ color: '#2E7D52' }}>90+</span></div>
      </div>
    </div>
  )
}

function Overview({ data, showSummary = true }) {
  const ranking = data.display.competitor_ranking
  const selfRank = ranking.findIndex(row => row.is_self) + 1
  const bestCompetitor = ranking.find(row => !row.is_self)
  const totalQueries = data.meta.total_queries
  const visibleCount = Number.isFinite(Number(totalQueries)) && Number.isFinite(Number(data.global.visibility))
    ? Math.round(Number(totalQueries) * Number(data.global.visibility))
    : null
  const delta = Number.isFinite(Number(data.global.visibility)) && bestCompetitor && Number.isFinite(Number(bestCompetitor.visibility ?? bestCompetitor.mention_rate))
    ? (Number(data.global.visibility) - Number(bestCompetitor.visibility ?? bestCompetitor.mention_rate)) * 100
    : null
  const deltaText = Number.isFinite(delta)
    ? `${delta >= 0 ? '领先竞品 +' : '落后竞品 '}${delta.toFixed(1)} pp`
    : '竞品差距未采集'
  const sentiment = data.sentiment || {}
  const summary = data.executive_summary || data.global.summary_text || `本次基于真实 AI 回答完成 ${displayValue(totalQueries, 0)} 条查询巡检，${data.meta.brand_name || '本品牌'} 自然可见度为 ${displayPercent(data.global.visibility)}，AI 推荐得分为 ${displayValue(data.global.ai_recommend_score, 1)}。`

  return (
    <ReportSection number="01" title="核心指标">
      {showSummary && summary ? <div className="dr-core-summary">{summary}</div> : null}
      <div className="dr-metric-grid">
        <div className="dr-metric-card"><div className="dr-metric-value">{displayPercent(data.global.visibility)}</div><div className="dr-metric-label">自然可见度</div><div className="dr-metric-sub">{visibleCount !== null ? `${displayValue(totalQueries, 0)} 条中 ${visibleCount} 条提及本品` : '样本提及数未采集'}</div></div>
        <div className="dr-metric-card good"><div className="dr-metric-value">#{selfRank || '—'}</div><div className="dr-metric-label">竞品排名</div><div className="dr-metric-sub">{deltaText}</div></div>
        <div className="dr-metric-card"><div className="dr-metric-value">{displayValue(data.global.ai_recommend_score, 1)}</div><div className="dr-metric-label">AI 推荐得分</div><div className="dr-metric-sub">满分 100</div></div>
        <div className="dr-metric-card good"><div className="dr-metric-value">{displayPercent(sentiment.negative_rate, 0)}</div><div className="dr-metric-label">负面情感率</div><div className="dr-metric-sub">正面 {displayPercent(sentiment.positive_rate)} · 中性 {displayPercent(sentiment.neutral_rate)}</div></div>
      </div>
    </ReportSection>
  )
}

function Insights({ data }) {
  const rows = data.display.insights
  if (!rows.length) return <EmptyState title="暂无关键问题" detail="上游诊断文案未提供 insights。" />
  return <div className="dr-insights">{rows.map((row, index) => <div className="dr-ins" key={index}><span className="dr-ins-badge">{row.priority || '未定级'}</span><div className="dr-ins-txt">{row.text || '暂无数据'}</div></div>)}</div>
}

function Sources({ data }) {
  const sources = data.display.sources
  const sourceReferences = data.display.source_references || []
  if (!sources.length && !sourceReferences.length && !data.display.source_gap.length) return <EmptyState title="暂无信源数据" detail="聚合数据未提供 sources、source_references 或 source_gap。" />
  const max = Math.max(...sources.map(row => row.count ?? 0), 0)
  const own = sources
    .filter(row => row.ownership === 'brand_owned' || row.is_brand_owned === true || row.type === '品牌自有' || row.type === '自有')
    .reduce((sum, row) => sum + (row.count ?? 0), 0)
  return (
    <>
      {sources.length ? <><div className="dr-kpis c3"><div className="dr-kpi"><div className="dr-kpi-v ok">{own}</div><div className="dr-kpi-l">品牌自有引用量</div></div><div className="dr-kpi"><div className="dr-kpi-v">{max}</div><div className="dr-kpi-l">最高信源引用数</div></div><div className="dr-kpi"><div className="dr-kpi-v">{sources.length}</div><div className="dr-kpi-l">信源域名数</div></div></div><div className="dr-sub-h">引用信源排行</div><div className="dr-src-list">{sources.map((source, index) => <div className="dr-src" key={source.domain}><span className="dr-src-i">#{index + 1}</span><div className="dr-src-n">{source.domain} {source.type ? <span className="dr-chip muted">{source.type}</span> : null}</div><div className="dr-src-bar"><MiniBar value={max ? (source.count ?? 0) / max * 100 : 0} type={source.ownership === 'brand_owned' || source.is_brand_owned === true || source.type === '品牌自有' || source.type === '自有' ? 'g' : 'n'} /></div><span className="dr-src-c">{displayValue(source.count, 0)}</span></div>)}</div></> : <EmptyState title="暂无引用信源排行" />}
      {sourceReferences.length ? <><div className="dr-sub-h">高频引用网址</div><div className="dr-url-list">{sourceReferences.map((source, index) => <details className="dr-url-ref" key={source.url}><summary><span className="dr-src-i">#{index + 1}</span><span className="dr-url-main"><a href={source.url} target="_blank" rel="noreferrer">{source.title || source.url}</a><small>{source.domain} {source.type ? <span className="dr-chip muted">{source.type}</span> : null}</small></span><span className="dr-src-c">{displayValue(source.citation_count, 0)}</span></summary><div className="dr-url-ref-body">{source.references.length ? source.references.map((ref, refIndex) => <div className="dr-url-quote" key={`${source.url}-${ref.inspection_id || refIndex}`}><div className="dr-url-meta">{[ref.platform, ref.topic, ref.query_id].filter(Boolean).join(' · ') || '未采集'}</div><p>{ref.quoted_text || ref.answer_excerpt || '暂无引用片段'}</p>{ref.query_text ? <div className="dr-url-query">{ref.query_text}</div> : null}</div>) : <div className="dr-url-quote"><p>暂无引用片段</p></div>}</div></details>)}</div></> : null}
    </>
  )
}

function Platforms({ data }) {
  const rows = data.display.platforms
  if (!rows.length) return <EmptyState title="暂无平台健康度" detail="聚合数据未提供 platforms。" />
  return <div className="dr-tw"><table><thead><tr><th>平台</th><th>提及率</th><th>健康评分</th><th>自有引用</th><th>竞品排名</th></tr></thead><tbody>{rows.map(row => <tr key={row.name}><td><strong>{row.name}</strong><small>{displayValue(row.samples, 0)} 条样本</small></td><td><b>{displayPercent(row.mention_rate)}</b><MiniBar value={Number(row.mention_rate) * 100} type={Number(row.mention_rate) >= 0.5 ? 'g' : 'a'} /></td><td><span className={`dr-hs ${Number(row.ai_recommend_score) >= 75 ? 'g' : Number(row.ai_recommend_score) >= 50 ? 'y' : 'r'}`}>{displayValue(row.ai_recommend_score, 0)}</span></td><td>{displayValue(row.own_citations, 0)}</td><td>{row.competitor_rank === null ? '未采集' : `#${displayValue(row.competitor_rank, 0)}`}</td></tr>)}</tbody></table></div>
}

function TopicPlatformVisibility({ data }) {
  const rows = data.display.topic_platform_visibility || []
  if (!rows.length) return <EmptyState title="暂无分话题可见度" detail="聚合数据未提供 topic_platform_visibility。" />
  return (
    <ReportSection number="02" title="话题可见度 × 竞品对比">
    <div className="dr-topic-grid">
      {rows.map(topic => (
        <div className="dr-topic-card" key={topic.topic}>
          {(() => {
            const platform = [...topic.platforms].sort((a, b) => (b.samples ?? 0) - (a.samples ?? 0))[0]
            const sentiment = data.display.topics.find(row => row.name === topic.topic)
            return (
              <>
                <div className="dr-topic-title">{topic.topic}</div>
                {(platform?.competitors || []).slice(0, 4).map((row, index) => {
                  const value = row.visibility ?? row.mention_rate
                  const kind = row.is_self ? 'self' : index === 0 ? 'lead' : ''
                  return (
                    <div className="dr-topic-brand-row" key={`${topic.topic}-${row.name}`}>
                      <div className={`dr-topic-brand-name ${row.is_self ? 'self' : ''}`}>{row.is_self ? <span className="dr-self-badge">本品</span> : null}{row.name}</div>
                      <div className="dr-topic-track"><div className={`dr-topic-fill ${kind}`} style={{ width: `${percentValue(value)}%` }} /></div>
                      <div className={`dr-topic-pct ${kind}`}>{displayPercent(value)}</div>
                    </div>
                  )
                })}
                {sentiment ? <div className="dr-sent-chips"><span className="dr-sent-chip pos">正面 {displayValue(sentiment.positive, 0, '%')}</span><span className="dr-sent-chip neu">中性 {displayValue(sentiment.neutral, 0, '%')}</span><span className="dr-sent-chip neg">负面 {displayValue(sentiment.negative, 0, '%')}</span></div> : null}
              </>
            )
          })()}
        </div>
      ))}
    </div>
    </ReportSection>
  )
}

function Competitors({ data }) {
  const rows = data.display.competitor_ranking
  if (!rows.length) return <EmptyState title="暂无竞品排名" detail="聚合数据未提供 competitor_ranking。" />
  function background(row) {
    if (row.is_self) return data.meta.brand_tagline || '本品'
    const matched = data.brand_config?.competitors?.find(item => item.name === row.name)
    return matched?.category || matched?.business_line || '竞品'
  }
  return (
    <ReportSection number="03" title={`全量竞品排名（${displayValue(data.meta.total_queries, 0)} 条综合）`}>
      <div className="dr-rank-table">
        <table>
          <thead><tr><th>排名</th><th>品牌</th><th>背景</th><th>可见度</th><th>提及率</th><th>客群匹配分</th></tr></thead>
          <tbody>
            {rows.map((row, index) => {
              const value = row.visibility ?? row.mention_rate
              return (
                <tr key={`${row.name}-${index}`}>
                  <td><strong>#{index + 1}</strong></td>
                  <td className="dr-rank-brand"><strong>{row.name}</strong>{row.is_self ? <span className="dr-rank-badge">本品</span> : null}</td>
                  <td>{background(row)}</td>
                  <td><div className="dr-rank-visibility"><div className="dr-rank-track"><div className={`dr-rank-fill ${row.is_self ? 'self' : ''}`} style={{ width: `${percentValue(value)}%` }} /></div><span className={`dr-rank-percent ${row.is_self ? 'self' : ''}`}>{displayPercent(value)}</span></div></td>
                  <td>{displayPercent(row.mention_rate ?? row.visibility)}</td>
                  <td>{displayValue(row.customer_fit_score ?? row.fit_score, 1)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </ReportSection>
  )
}

function Sentiment({ data }) {
  if (!data.sentiment && !data.display.topics.length) return <EmptyState title="暂无调性数据" detail="聚合数据未提供 sentiment 或 topics。" />
  const sentiment = data.sentiment || {}
  return (
    <>
      <div className="dr-sent-kpis"><div className="dr-sent-kpi"><div className="dr-sent-kpi-v green">{displayPercent(sentiment.positive_rate, 0)}</div><div className="dr-sent-kpi-l">正面推荐</div></div><div className="dr-sent-kpi"><div className="dr-sent-kpi-v">{displayPercent(sentiment.neutral_rate, 0)}</div><div className="dr-sent-kpi-l">中立列举</div></div><div className="dr-sent-kpi"><div className="dr-sent-kpi-v red">{displayPercent(sentiment.negative_rate, 0)}</div><div className="dr-sent-kpi-l">负面评价</div></div><div className="dr-sent-kpi"><div className="dr-sent-kpi-v blue">{displayValue(data.global.ai_recommend_score, 0)}</div><div className="dr-sent-kpi-l">AI 推荐度</div></div></div>
      {data.display.topics.length ? <div className="dr-tw dr-sent-table"><table><thead><tr><th>话题</th><th>正面</th><th>中立</th><th>负面</th><th>较上期变化</th></tr></thead><tbody>{data.display.topics.map(topic => <tr key={topic.name}><td><strong>{topic.name}</strong></td><td className="dr-sent-positive">{displayValue(topic.positive, 0, '%')}</td><td>{displayValue(topic.neutral, 0, '%')}</td><td className="dr-sent-negative">{displayValue(topic.negative, 0, '%')}</td><td><SentimentChange value={topic.change ?? topic.verdict} /></td></tr>)}</tbody></table></div> : <EmptyState title="暂无话题调性" />}
    </>
  )
}

function BrandConfig({ data }) {
  const config = data.brand_config
  if (!config) return <EmptyState title="暂无品牌配置" detail="上游未提供 brand_config。" />
  return (
    <div className="dr-kpis c4">
      <div className="dr-kpi"><div className="dr-kpi-v">{displayValue(config.aliases_count, 0)}</div><div className="dr-kpi-l">别名数量</div></div>
      <div className="dr-kpi"><div className="dr-kpi-v">{displayValue(config.topics_monitored, 0)}</div><div className="dr-kpi-l">监测话题</div></div>
      <div className="dr-kpi"><div className="dr-kpi-v">{displayValue(config.competitors_count, 0)}</div><div className="dr-kpi-l">横评竞品</div></div>
      <div className="dr-kpi"><div className="dr-kpi-v">{displayValue(config.queries_count, 0)}</div><div className="dr-kpi-l">场景问题</div></div>
    </div>
  )
}

export default function DiagnosticReportPage() {
  const pageRunId = useMemo(() => getRunIdFromLocation(), [])
  const [rawData, setRawData] = useState(null)
  const [status, setStatus] = useState({ status: 'loading', message: '数据采集中' })
  const [editMode, setEditMode] = useState(false)
  const [hiddenSections, setHiddenSections] = useState(() => readHiddenSections(pageRunId))
  const runStartedAtRef = useRef(null)

  useEffect(() => {
    let cancelled = false
    let timer = null
    const runId = pageRunId

    if (!runId) {
      setStatus({ status: 'missing_run', message: '缺少诊断任务 ID' })
      setRawData(null)
      return () => { cancelled = true }
    }

    async function loadCompletedReport() {
      const data = await fetchDiagnosticReportData({ run_id: runId })
      if (cancelled) return
      const nextState = getReportDataState(data)
      setRawData(data)
      setStatus(nextState.status === 'ready' ? { status: 'ready', message: 'ready' } : nextState)
    }

    async function pollRun(attempt = 0) {
      try {
        const run = await fetchDiagnosticRun(runId)
        if (cancelled) return
        const runStatus = String(run?.status || '').toLowerCase()
        const progress = getProgressValue(run?.progress)
        const detail = run?.message || run?.detail || (progress !== null ? `当前进度 ${progress}%` : '后端正在生成巡检聚合数据。')
        if (!runStartedAtRef.current) runStartedAtRef.current = getRunStartTime(run, Date.now())
        const estimatedGenerationTime = getEstimatedGenerationTime(run, progress, runStartedAtRef.current)

        if (runStatus === 'completed') {
          setStatus({ status: 'loading_report', message: '读取报告数据', detail: '诊断任务已完成，正在读取 report_data_v1。', progress: 100, estimatedGenerationTime: '即将完成' })
          await loadCompletedReport()
          return
        }

        if (runStatus === 'failed') {
          setRawData(null)
          setStatus({ status: 'failed', message: '诊断任务失败', detail: run?.error || detail })
          return
        }

        if (runStatus === 'interrupted') {
          setRawData(null)
          setStatus({
            status: 'interrupted',
            message: '诊断任务已中断',
            detail: '任务被后端重启中断，请重新发起诊断。',
            progress: progress ?? 0,
          })
          return
        }

        if (ACTIVE_RUN_STATUSES.includes(runStatus)) {
          if (attempt >= 120) {
            setRawData(null)
            setStatus({ status: 'error', message: '诊断任务超时', detail: '任务超过 3 分钟仍未完成，请稍后刷新或检查后端任务状态。' })
            return
          }
          setStatus({
            status: 'running',
            message: runStatus === 'queued' ? '诊断任务排队中' : runStatus === 'aggregating' ? '正在聚合报告' : '正在巡检',
            detail,
            progress: progress ?? 0,
            estimatedGenerationTime,
          })
          timer = window.setTimeout(() => pollRun(attempt + 1), 1500)
          return
        }

        throw new Error(`未知诊断任务状态: ${run?.status || 'empty'}`)
      } catch (error) {
        if (!cancelled) {
          setRawData(null)
          const errorContext = backendErrorContext(error)
          if (error?.status === 409 && error?.endpoint === 'GET /diagnostic-report') {
            setStatus({
              status: 'diagnostic_state',
              message: '诊断报告暂不可用',
              detail: error?.message || '后端返回了诊断报告状态。',
              errorContext,
            })
            return
          }
          setStatus({
            status: 'error',
            message: '数据加载失败',
            detail: error?.message || '请稍后重试或检查诊断报告接口。',
            errorContext,
          })
        }
      }
    }

    setRawData(null)
    setStatus({ status: 'loading', message: '读取诊断任务', detail: `Run ${runId}` })
    pollRun()
    return () => {
      cancelled = true
      if (timer) window.clearTimeout(timer)
    }
  }, [pageRunId])

  const data = useMemo(() => rawData && status.status === 'ready' ? buildReportDisplayData(rawData) : null, [rawData, status.status])
  const hiddenSectionList = useMemo(() => [...hiddenSections], [hiddenSections])

  useEffect(() => {
    writeHiddenSections(pageRunId, hiddenSections)
  }, [hiddenSections, pageRunId])

  function hideSection(sectionId) {
    setHiddenSections(current => new Set([...current, sectionId]))
  }

  function restoreSection(sectionId) {
    setHiddenSections(current => {
      const next = new Set(current)
      next.delete(sectionId)
      return next
    })
  }

  function restoreAllSections() {
    setHiddenSections(new Set())
  }

  function isSectionVisible(sectionId) {
    return !hiddenSections.has(sectionId)
  }

  function renderEditableBlock(sectionId, children) {
    const section = EDITABLE_REPORT_SECTIONS.find(item => item.id === sectionId)
    if (!section || !isSectionVisible(sectionId)) return null
    return (
      <EditableReportBlock key={sectionId} title={section.title} editMode={editMode} onRemove={() => hideSection(sectionId)}>
        {children}
      </EditableReportBlock>
    )
  }

  function handleExport() {
    const html = generateReportHtml(rawData, { editable: true, hiddenSections: hiddenSectionList })
    const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${data.meta.report_id || 'geo_diagnostic_report'}.html`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  if (status.status === 'missing_run') return <StatusState title="缺少诊断任务 ID" detail="请从品牌配置页启动诊断，或使用包含 run_id 的诊断报告链接。" />
  if (status.status === 'loading') return <StatusState title={status.message || '读取诊断任务'} detail={status.detail || '正在读取诊断任务状态。'} />
  if (status.status === 'running') return <StatusState title={status.message || '正在巡检'} detail={status.detail || '后端正在生成巡检聚合数据。'} progress={status.progress} estimatedGenerationTime={status.estimatedGenerationTime} showProgress />
  if (status.status === 'loading_report') return <StatusState title={status.message || '读取报告数据'} detail={status.detail || '诊断任务已完成，正在读取 report_data_v1。'} progress={status.progress} estimatedGenerationTime={status.estimatedGenerationTime} showProgress />
  if (status.status === 'empty') return <StatusState title="暂无巡检数据" detail="当前品牌或批次没有可生成报告的数据。" />
  if (status.status === 'invalid') return <StatusState title="报告数据结构异常" detail={(status.errors || []).join('；')} />
  if (status.status === 'failed') return <StatusState title="诊断任务失败" detail={status.detail || '请检查后端任务日志。'} />
  if (status.status === 'interrupted') return <StatusState title="诊断任务已中断" detail={status.detail || '任务被后端重启中断，请重新发起诊断。'} />
  if (status.status === 'diagnostic_state') return <StatusState title={status.message || '诊断报告暂不可用'} detail={status.detail || '后端返回了诊断报告状态。'} errorContext={status.errorContext} />
  if (status.status === 'error') return <StatusState title={status.message || '数据加载失败'} detail={status.detail || '请稍后重试或检查诊断报告接口。'} errorContext={status.errorContext} />

  return (
    <div className="diagnostic-report-shell">
      <ReportTop data={data} editMode={editMode} onToggleEdit={() => setEditMode(value => !value)} onExport={handleExport} />
      <main className="dr-report-main">
        <ReportEditPanel hiddenSections={hiddenSections} editMode={editMode} onRestore={restoreSection} onRestoreAll={restoreAllSections} />
        {renderEditableBlock('overview', <Overview data={data} showSummary={isSectionVisible('executive_summary')} />)}
        {renderEditableBlock('topic_platform_visibility', <TopicPlatformVisibility data={data} />)}
        {renderEditableBlock('competitors', <Competitors data={data} />)}
        <div className="dr-legacy-sections">
          {renderEditableBlock('insights', <Section number="04" title="关键问题&优化建议"><Insights data={data} /></Section>)}
          {renderEditableBlock('sources', <Section number="05" title="信源引用情况"><Sources data={data} /></Section>)}
          {renderEditableBlock('platforms', <Section number="06" title="六平台健康度"><Platforms data={data} /></Section>)}
          {renderEditableBlock('sentiment', <Section number="07" title="品牌调性分析"><Sentiment data={data} /></Section>)}
          {renderEditableBlock('brand_config', <Section number="08" title="品牌配置"><BrandConfig data={data} /></Section>)}
        </div>
        <footer className="dr-footer"><span>{data.meta.brand_name || '未命名品牌'} · GEO 诊断报告</span><span>{formatReportDate(data.meta.report_date)} · {displayValue(data.meta.total_queries, 0)} 场景 · {displayValue(data.meta.total_competitors, 0)} 竞品</span></footer>
      </main>
    </div>
  )
}
