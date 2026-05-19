import { useEffect, useMemo, useRef, useState } from 'react'
import { fetchDiagnosticReportData, fetchDiagnosticRun } from '../api/geo.js'
import { buildReportDisplayData, getReportDataState } from '../lib/reportDataAdapter.js'
import { generateReportHtml } from '../lib/reportGenerator.js'
import './DiagnosticReportPage.css'

const DEFAULT_GENERATION_TIME_MS = 3 * 60 * 1000
const ACTIVE_RUN_STATUSES = ['queued', 'running', 'aggregating']

function StatusState({ title, detail, progress = null, estimatedGenerationTime = null, showProgress = false }) {
  const hasProgress = Number.isFinite(Number(progress))
  const progressValue = hasProgress ? Math.max(0, Math.min(100, Math.round(Number(progress)))) : 0

  return (
    <div className="diagnostic-report-shell">
      <div className="report-state-card">
        <div className="report-state-eyebrow">GEO 诊断报告</div>
        <h1>{title}</h1>
        {detail ? <p>{detail}</p> : null}
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

function Overview({ data }) {
  const ranking = data.display.competitor_ranking
  const selfRank = ranking.findIndex(row => row.is_self) + 1

  return (
    <>
      <div className="dr-ov">
        <div className="dr-ov-card">
          <div className="dr-ov-brow">全局排名</div>
          <div><span className="dr-rank-n">{selfRank || '—'}</span><span className="dr-rank-u">/ {ranking.length || '—'}</span></div>
          <div className="dr-rank-sub">按品牌可见度排序</div>
          <div className="dr-rank-rows">
            {ranking.length ? ranking.map((row, index) => (
              <div className={`dr-rank-row ${row.is_self ? 'self' : ''}`} key={`${row.name}-${index}`}>
                <span className="idx">{index + 1}</span><span className="nm">{row.name}</span><span className="vl">{displayPercent(row.visibility ?? row.mention_rate)}</span>
              </div>
            )) : <EmptyState title="暂无竞品排名" detail="聚合数据未提供 competitor_ranking。" />}
          </div>
        </div>
        <div className="dr-ov-card"><div className="dr-ov-brow">品牌健康评分</div><Gauge score={data.global.ai_recommend_score} /></div>
      </div>
      <div className="dr-factor-strip">
        <div className="dr-factor-card"><div className={`dr-factor-v ${numberClass((data.global.visibility ?? 0) * 100)}`}>{displayPercent(data.global.visibility)}</div><div className="dr-factor-l">可见度</div><div className="dr-factor-sub">query 不提及品牌时，回答中提及品牌的概率</div></div>
        <div className="dr-factor-card"><div className="dr-factor-v">{displayValue(data.global.rank, 2)}</div><div className="dr-factor-l">平均位次</div><div className="dr-factor-sub">品牌被提及时在回答中的平均排名</div></div>
        <div className="dr-factor-card"><div className={`dr-factor-v ${numberClass((data.global.sentiment_score ?? 0) * 100)}`}>{displayPercent(data.global.sentiment_score)}</div><div className="dr-factor-l">舆情指数</div><div className="dr-factor-sub">正面=1.0 · 中立=0.5 · 负面=0.1 加权均值</div></div>
      </div>
      <div className="dr-factor-formula">AI 推荐度 = 可见度 × 舆情指数 × 100 · 任意因子为 0 则得分为 0</div>
    </>
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
  const own = sources.filter(row => row.type === '自有').reduce((sum, row) => sum + (row.count ?? 0), 0)
  return (
    <>
      {sources.length ? <><div className="dr-kpis c3"><div className="dr-kpi"><div className="dr-kpi-v ok">{own}</div><div className="dr-kpi-l">品牌自有引用量</div></div><div className="dr-kpi"><div className="dr-kpi-v">{max}</div><div className="dr-kpi-l">最高信源引用数</div></div><div className="dr-kpi"><div className="dr-kpi-v">{sources.length}</div><div className="dr-kpi-l">信源域名数</div></div></div><div className="dr-sub-h">引用信源排行</div><div className="dr-src-list">{sources.map((source, index) => <div className="dr-src" key={source.domain}><span className="dr-src-i">#{index + 1}</span><div className="dr-src-n">{source.domain} {source.type ? <span className="dr-chip muted">{source.type}</span> : null}</div><div className="dr-src-bar"><MiniBar value={max ? (source.count ?? 0) / max * 100 : 0} type={source.type === '自有' ? 'g' : 'n'} /></div><span className="dr-src-c">{displayValue(source.count, 0)}</span></div>)}</div></> : <EmptyState title="暂无引用信源排行" />}
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
    <div className="dr-topic-vis-list">
      {rows.map(topic => (
        <div className="dr-topic-vis" key={topic.topic}>
          <div className="dr-topic-vis-h">{topic.topic}</div>
          <div className="dr-topic-vis-platforms">
            {topic.platforms.map(platform => {
              const topCompetitors = platform.competitors.filter(row => !row.is_self).slice(0, 2)
              return (
                <div className="dr-topic-vis-row" key={`${topic.topic}-${platform.platform}`}>
                  <div className="dr-topic-vis-main">
                    <strong>{platform.platform}</strong>
                    <small>{displayValue(platform.samples, 0)} 条样本 · {displayValue(platform.visibility_eligible_samples, 0)} 条可见度样本</small>
                  </div>
                  <div className="dr-topic-vis-bar"><MiniBar value={percentValue(platform.visibility)} type={Number(platform.visibility) >= 0.5 ? 'g' : 'a'} /></div>
                  <div className="dr-topic-vis-metric">{displayPercent(platform.visibility)}</div>
                  <div className="dr-topic-vis-rank">{platform.competitor_rank == null ? '未采集' : `#${displayValue(platform.competitor_rank, 0)}`}</div>
                  <div className="dr-topic-vis-ctx">
                    {topCompetitors.length ? topCompetitors.map(row => (
                      <span key={row.name}>{row.name} {displayPercent(row.visibility)}</span>
                    )) : <span>暂无竞品数据</span>}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}

function Competitors({ data }) {
  const rows = data.display.competitor_ranking
  if (!rows.length) return <EmptyState title="暂无竞品排名" detail="聚合数据未提供 competitor_ranking。" />
  return (
    <div className="dr-comp-bars">
      {rows.map((row, index) => {
        const value = row.visibility ?? row.mention_rate
        return (
          <div className={`dr-comp-bar-row ${row.is_self ? 'self' : ''}`} key={`${row.name}-${index}`}>
            <span className="dr-comp-rank">#{index + 1}</span>
            <span className="dr-comp-name">{row.name}</span>
            <div className="dr-comp-track"><div className="dr-comp-fill" style={{ width: `${percentValue(value)}%` }} /></div>
            <span className="dr-comp-value">{displayPercent(value)}</span>
            <span className="dr-comp-type">{row.is_self ? '本品牌' : '竞品'}</span>
          </div>
        )
      })}
    </div>
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
  const [rawData, setRawData] = useState(null)
  const [status, setStatus] = useState({ status: 'loading', message: '数据采集中' })
  const runStartedAtRef = useRef(null)

  useEffect(() => {
    let cancelled = false
    let timer = null
    const runId = new URLSearchParams(window.location.search).get('run_id')

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
          setStatus({ status: 'error', message: '数据加载失败', detail: error?.message || '请稍后重试或检查诊断报告接口。' })
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
  }, [])

  const data = useMemo(() => rawData && status.status === 'ready' ? buildReportDisplayData(rawData) : null, [rawData, status.status])

  function handleExport() {
    const html = generateReportHtml(rawData)
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
  if (status.status === 'error') return <StatusState title={status.message || '数据加载失败'} detail={status.detail || '请稍后重试或检查诊断报告接口。'} />

  return (
    <div className="diagnostic-report-shell">
      <nav className="dr-nav"><div className="dr-nav-l">GEO 诊断报告</div><div className="dr-nav-r"><span>Report Contract</span><span className="dr-nav-date">{data.meta.report_date || '未采集'}</span><button type="button" className="dr-nav-export" onClick={handleExport}>导出 HTML</button></div></nav>
      <header className="dr-hero"><div className="dr-hero-over">{data.meta.brand_name || '未命名品牌'} · {data.meta.brand_tagline || 'GEO 诊断'}</div><h1>AI 可见度诊断</h1><p>基于 report_data.json 渲染契约生成；报告内容来自巡检聚合或上游诊断输入，未采集字段不会被前端补造。</p></header>
      {data.executive_summary || data.global.summary_text ? <Section number="00" title="Executive Summary"><div className="dr-summary"><p>{data.executive_summary || data.global.summary_text}</p></div></Section> : null}
      <Overview data={data} />
      <Section number="01" title="关键问题&优化建议"><Insights data={data} /></Section>
      <Section number="02" title="信源引用情况"><Sources data={data} /></Section>
      <Section number="03" title="六平台健康度"><Platforms data={data} /></Section>
      <Section number="03A" title="分话题可见度表现"><TopicPlatformVisibility data={data} /></Section>
      <Section number="04" title="竞品排名与差距"><Competitors data={data} /></Section>
      <Section number="05" title="品牌调性分析"><Sentiment data={data} /></Section>
      <Section number="06" title="品牌配置"><BrandConfig data={data} /></Section>
      <footer className="dr-footer"><span>{data.meta.brand_name || '未命名品牌'} · GEO 诊断报告</span><span>{data.meta.report_date || '未采集'} · {displayValue(data.meta.total_queries, 0)} 场景 · {displayValue(data.meta.total_competitors, 0)} 竞品</span></footer>
    </div>
  )
}
