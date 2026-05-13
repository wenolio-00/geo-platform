import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchBrandHistory, fetchDashboardContract } from '../api/geo.js'
import './DashboardPage.css'

const MAX_LIST_ITEMS = 6

function oneDecimal(value) {
  const n = Number(value)
  return Number.isFinite(n) ? n.toFixed(1) : '0.0'
}

function valueText(value, unit = '') {
  if (unit === '%') return `${oneDecimal(value)}%`
  if (unit === 'count') {
    const n = Number(value)
    return Number.isFinite(n) ? String(Math.round(n)) : '0'
  }
  if (unit === 'rank') return oneDecimal(value)
  return oneDecimal(value)
}

function deltaText(value, unit = '') {
  const n = Number(value)
  if (!Number.isFinite(n) || n === 0) return unit === '%' ? '0.0%' : '0.0'
  const sign = n > 0 ? '+' : ''
  return `${sign}${valueText(n, unit)}`
}

function indicatorClass(value, direction = 'higher_is_better', benchmarkValue = null) {
  const n = Number(value)
  if (!Number.isFinite(n)) return 'neutral'
  const benchmark = Number(benchmarkValue)
  if (Number.isFinite(benchmark) && benchmark > 0) {
    if (direction === 'lower_is_better') {
      if (n <= benchmark) return 'ok'
      if (n <= benchmark * 1.5) return 'warn'
      return 'risk'
    }
    if (n >= benchmark) return 'ok'
    if (n >= benchmark * 0.5) return 'warn'
    return 'risk'
  }
  if (direction === 'lower_is_better') {
    if (n <= 3) return 'ok'
    if (n <= 6) return 'warn'
    return 'risk'
  }
  if (n >= 75) return 'ok'
  if (n >= 20) return 'warn'
  return 'risk'
}

function deltaClass(delta, direction = 'higher_is_better') {
  const n = Number(delta)
  if (!Number.isFinite(n) || n === 0) return 'neutral'
  const improved = direction === 'lower_is_better' ? n < 0 : n > 0
  return improved ? 'ok' : 'risk'
}

function Section({ number, title, children, className = '' }) {
  return (
    <section className={`report-sec ${className}`}>
      <div className="report-sec-h">
        <span className="report-sec-n">{number}</span>
        <span className="report-sec-t">{title}</span>
      </div>
      {children}
    </section>
  )
}

function ChangeBadge({ metric }) {
  if (metric.previous_value === undefined || metric.previous_value === null) return null
  const delta = Number(metric.current_value) - Number(metric.previous_value)
  return <span className={`metric-change ${deltaClass(delta, metric.direction)}`}>{deltaText(delta, metric.unit)}</span>
}

function MetricCard({ metric, label, description }) {
  if (!metric) return null
  return (
    <div className="factor-card">
      <div className="metric-card-top">
        <div className={`factor-v ${indicatorClass(metric.current_value, metric.direction, metric.benchmark_value)}`}>{valueText(metric.current_value, metric.unit)}</div>
        <ChangeBadge metric={metric} />
      </div>
      <div className="factor-l">{label || metric.metric_name}</div>
      <div className="factor-sub">{description}</div>
    </div>
  )
}

function Chip({ children, type = 'n' }) {
  return <span className={`report-chip ${type}`}>{children}</span>
}

function buildDashboardView(contract) {
  const metrics = Object.fromEntries(contract.key_metrics.map(m => [m.metric_id, m]))
  const naturalVisibility = metrics.natural_visibility
  const avgRank = metrics.rank
  const visibility = metrics.visibility
  const sentimentScore = metrics.sentiment_score
  const ownCitations = metrics.own_citations
  const competitorSuppressionRate = metrics.competitor_suppression_rate
  const configuredTopics = (contract.brand_config?.topics || [])
    .filter(topic => topic.topic_name || topic.business_line)
    .sort((a, b) => (a.priority || 99) - (b.priority || 99))
    .slice(0, MAX_LIST_ITEMS)
  const configuredCompetitors = (contract.brand_config?.competitors || [])
    .filter(competitor => competitor.name)
    .slice(0, MAX_LIST_ITEMS)

  return { metrics, naturalVisibility, avgRank, visibility, sentimentScore, ownCitations, competitorSuppressionRate, configuredTopics, configuredCompetitors }
}

function Hero({ contract, view, onOpenReport }) {
  return (
    <>
      <nav className="report-nav">
        <div className="nav-l">GEO Dashboard</div>
        <div className="nav-r">
          <span>工作台 · 报告链路已拆分</span>
          <span className="nav-date">{contract.snapshot_date}</span>
          <button type="button" className="nav-export" onClick={onOpenReport}>打开诊断报告</button>
        </div>
      </nav>
      <div className="report-hero fade-up">
        <div className="hero-over">{contract.main_brand.short_name} · {contract.main_brand.category}</div>
        <h1>GEO 工作台</h1>
        <p>Dashboard 保留品牌配置、指标观察和优化入口；诊断报告通过独立 report_data.json 契约渲染。</p>
      </div>
      <div className="factor-strip">
        <MetricCard metric={view.naturalVisibility} label="自然可见度" description="品牌出现在 AI 回答中的比例" />
        <MetricCard metric={view.avgRank} label="平均位次" description="仅计已提及品牌且位置大于 0 的样本" />
        <MetricCard metric={view.visibility} label="可见度" description="自然可见度 ÷ 平均位次" />
        <MetricCard metric={view.sentimentScore} label="舆情指数" description="正面=1.0 · 中立=0.5 · 负面=0.1 加权均值" />
      </div>
    </>
  )
}

function ConfigSummary({ view }) {
  return (
    <Section number="01" title="当前配置摘要" className="fade-up">
      <div className="kpis c3">
        <div className="kpi"><div className="kpi-v">{view.configuredTopics.length}</div><div className="kpi-l">业务话题</div></div>
        <div className="kpi"><div className="kpi-v">{view.configuredCompetitors.length}</div><div className="kpi-l">竞品配置</div></div>
        <div className="kpi"><div className="kpi-v warn">{valueText(view.ownCitations.current_value, view.ownCitations.unit)}</div><div className="kpi-l">品牌自有引用</div></div>
      </div>
      <div className="topic-grid">
        {view.configuredTopics.map(topic => (
          <div className="topic-card topic-a" key={topic.topic_name || topic.business_line}>
            <div className="topic-head"><div className="topic-name">{topic.topic_name || topic.business_line}</div><Chip type="n">P{topic.priority || '-'}</Chip></div>
            <div className="topic-meta">{topic.business_line || '待补充'} · {(topic.intent_ids || []).length} intents</div>
          </div>
        ))}
      </div>
    </Section>
  )
}

function StrategyPanel({ contract, onSelectAction }) {
  return (
    <Section number="02" title="优化方向" className="fade-up">
      <div className="strats">
        {contract.optimization_actions.slice(0, MAX_LIST_ITEMS).map((action, index) => (
          <button type="button" className="strat strat-clickable" key={action.action_id} onClick={() => onSelectAction(action)}>
            <div className="strat-n">{String(index + 1).padStart(2, '0')}</div>
            <div className="strat-t">{action.action_name}</div>
            <div className="strat-b">产出：{action.output_assets.join('、')}。成功指标：{action.success_metrics.join('、')}。</div>
            <div className="strat-link">进入内容生成 →</div>
          </button>
        ))}
      </div>
    </Section>
  )
}

function buildMetricOptimizationRows(contract, history) {
  if (!history?.by_metric) return []
  return contract.key_metrics
    .filter(metric => metric.use_for_before_after)
    .map(metric => {
      const points = history.by_metric[metric.metric_id]
      if (!Array.isArray(points) || points.length < 2) return null
      const start = Number(points[0].value)
      const latest = Number(points[points.length - 1].value)
      if (!Number.isFinite(start) || !Number.isFinite(latest)) return null
      const current = Number.isFinite(Number(metric.current_value)) ? Number(metric.current_value) : latest
      const delta = current - start
      return { metric, current, delta }
    })
    .filter(Boolean)
    .slice(0, MAX_LIST_ITEMS)
}

function MetricOptimization({ contract, history }) {
  const rows = buildMetricOptimizationRows(contract, history)
  if (!rows.length) return null
  return (
    <Section number="03" title="关键指标观察" className="fade-up">
      <div className="metric-optim-grid">
        {rows.map(row => (
          <div className="metric-optim-card" key={row.metric.metric_id}>
            <div className="metric-optim-head">
              <div className="metric-optim-name">{row.metric.metric_name}</div>
              <span className={`metric-delta ${deltaClass(row.delta, row.metric.direction)}`}>{deltaText(row.delta, row.metric.unit)}</span>
            </div>
            <div className={`metric-optim-current ${indicatorClass(row.current, row.metric.direction, row.metric.benchmark_value)}`}>{valueText(row.current, row.metric.unit)}</div>
          </div>
        ))}
      </div>
    </Section>
  )
}

export default function DashboardPage() {
  const [contract, setContract] = useState(null)
  const [history, setHistory] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    let cancelled = false
    async function loadDashboard() {
      try {
        const data = await fetchDashboardContract()
        const historyData = await fetchBrandHistory(data.main_brand.brand_id, 30)
        if (cancelled) return
        setContract(data)
        setHistory(historyData)
        setError(null)
      } catch (err) {
        if (!cancelled) setError(err.message || 'Dashboard 数据加载失败')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    loadDashboard()
    return () => { cancelled = true }
  }, [])

  const view = useMemo(() => contract ? buildDashboardView(contract) : null, [contract])

  function handleOpenReport() {
    const runId = contract.latest_run_id || contract.diagnostic_run?.run_id || contract.report?.run_id
    if (!runId) {
      setError('当前 Dashboard contract 未提供 run_id，请从品牌配置页启动诊断。')
      return
    }
    navigate(`/report/diagnostic?run_id=${encodeURIComponent(runId)}`)
  }

  function handleSelectAction(action) {
    const matchedRule = contract.cross_topic_rules.find(rule => rule.applies_to.includes(action.action_type)) || contract.cross_topic_rules[0]
    navigate(`/content/generate?action_id=${encodeURIComponent(action.action_id)}&rule_id=${encodeURIComponent(matchedRule.rule_id)}`, {
      state: { actionId: action.action_id, ruleId: matchedRule.rule_id },
    })
  }

  if (loading) return <div className="dashboard-page loading">加载中…</div>
  if (error || !contract) return <div className="dashboard-page loading">{error || 'Dashboard 数据不可用'}</div>

  return (
    <div className="dashboard-page">
      <Hero contract={contract} view={view} onOpenReport={handleOpenReport} />
      <ConfigSummary view={view} />
      <StrategyPanel contract={contract} onSelectAction={handleSelectAction} />
      <MetricOptimization contract={contract} history={history} />
      <footer className="report-footer">
        <span>{contract.main_brand.short_name} · GEO 工作台</span>
        <span>{contract.snapshot_date} · 诊断报告入口已独立</span>
      </footer>
    </div>
  )
}
