import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchBrandHistory, fetchDashboardContract } from '../api/geo.js'
import { FIXED_DIAGNOSTIC_REPORT_URL } from '../config/reportFrontend.js'
import './DashboardPage.css'

const MAX_LIST_ITEMS = 6
const MAX_FINDINGS = 4

function safeArray(value) {
  return Array.isArray(value) ? value : []
}

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

function clampPercent(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return 0
  return Math.max(0, Math.min(100, n))
}

function severityRank(severity) {
  if (severity === 'P0') return 0
  if (severity === 'P1') return 1
  if (severity === 'P2') return 2
  return 3
}

function isPriorityIssue(issue) {
  return ['P0', 'P1'].includes(issue?.severity)
}

function metricGap(metric, compareKey = 'competitor_avg') {
  const current = Number(metric?.current_value)
  const compare = Number(metric?.[compareKey])
  if (!Number.isFinite(current) || !Number.isFinite(compare)) return null
  return current - compare
}

function metricComparisonText(metric) {
  const gap = metricGap(metric)
  if (gap === null) {
    return metric?.benchmark_label ? `目标 ${metric.benchmark_label}` : '暂无竞品均值'
  }
  return `较竞品均值 ${deltaText(gap, metric.unit)}`
}

function benchmarkGapText(metric) {
  const current = Number(metric?.current_value)
  const benchmark = Number(metric?.benchmark_value)
  if (!Number.isFinite(current) || !Number.isFinite(benchmark)) return '暂无目标线'
  return `距目标 ${deltaText(current - benchmark, metric.unit)}`
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
  const metrics = Object.fromEntries(safeArray(contract.key_metrics).map(m => [m.metric_id, m]))
  const avgRank = metrics.rank
  const visibility = metrics.visibility
  const sentimentScore = metrics.sentiment_score
  const ownCitations = metrics.own_citations
  const competitorSuppressionRate = metrics.competitor_suppression_rate
  const configuredTopics = safeArray(contract.brand_config?.topics)
    .filter(topic => topic.topic_name || topic.business_line)
    .sort((a, b) => (a.priority || 99) - (b.priority || 99))
    .slice(0, MAX_LIST_ITEMS)
  const configuredCompetitors = safeArray(contract.brand_config?.competitors)
    .filter(competitor => competitor.name)
    .slice(0, MAX_LIST_ITEMS)
  const keyIssues = safeArray(contract.key_issues)
    .filter(issue => issue?.title || issue?.business_pain)
    .sort((a, b) => severityRank(a.severity) - severityRank(b.severity))

  return { metrics, avgRank, visibility, sentimentScore, ownCitations, competitorSuppressionRate, configuredTopics, configuredCompetitors, keyIssues }
}

function buildDecisionModules(contract, view) {
  const priorityIssues = view.keyIssues.filter(isPriorityIssue)
  const evidenceCount = view.keyIssues.reduce((sum, issue) => sum + safeArray(issue.evidence).length, 0)
  const sourceGapIssues = view.keyIssues.filter(issue => {
    const text = `${issue.dimension || ''}${issue.title || ''}${issue.business_pain || ''}${safeArray(issue.root_cause).join('')}`
    return /盲区|缺口|缺少|缺席|信源|证据|引用|覆盖/.test(text)
  })
  const competitorIssues = view.keyIssues.filter(issue => {
    const text = `${issue.dimension || ''}${issue.title || ''}${issue.business_pain || ''}`
    return /竞品|压制|对比|候选/.test(text)
  })
  const p0Count = view.keyIssues.filter(issue => issue.severity === 'P0').length
  const p1Count = view.keyIssues.filter(issue => issue.severity === 'P1').length
  const blindSpotCount = sourceGapIssues.length || priorityIssues.length || view.keyIssues.length

  return [
    {
      id: 'visibility',
      label: '可见度',
      title: '进入候选集的强度',
      value: valueText(view.visibility?.current_value, view.visibility?.unit),
      tone: indicatorClass(view.visibility?.current_value, view.visibility?.direction, view.visibility?.benchmark_value),
      note: metricComparisonText(view.visibility),
      progress: clampPercent(view.visibility?.current_value),
      rows: [
        { label: '平均位次', value: valueText(view.avgRank?.current_value, view.avgRank?.unit) },
        { label: '目标线', value: view.visibility?.benchmark_label || '-' },
      ],
    },
    {
      id: 'blind-spots',
      label: '盲区',
      title: '高价值问题与证据缺口',
      value: valueText(blindSpotCount, 'count'),
      tone: blindSpotCount <= 1 ? 'ok' : blindSpotCount <= 3 ? 'warn' : 'risk',
      note: `${evidenceCount} 条可追溯证据样本`,
      progress: clampPercent(blindSpotCount * 24),
      rows: [
        { label: 'P0 问题', value: valueText(p0Count, 'count') },
        { label: 'P1 问题', value: valueText(p1Count, 'count') },
        { label: '自有引用', value: valueText(view.ownCitations?.current_value, view.ownCitations?.unit) },
      ],
    },
    {
      id: 'sentiment',
      label: '情感',
      title: 'AI 回答的正向倾向',
      value: valueText(view.sentimentScore?.current_value, view.sentimentScore?.unit),
      tone: indicatorClass(view.sentimentScore?.current_value, view.sentimentScore?.direction, view.sentimentScore?.benchmark_value),
      note: metricComparisonText(view.sentimentScore),
      progress: clampPercent(view.sentimentScore?.current_value),
      rows: [
        { label: '目标线', value: view.sentimentScore?.benchmark_label || '-' },
        { label: '竞品均值', value: valueText(view.sentimentScore?.competitor_avg, view.sentimentScore?.unit) },
        { label: '趋势', value: benchmarkGapText(view.sentimentScore) },
      ],
    },
    {
      id: 'competitors',
      label: '竞品',
      title: '被竞品单独占位的风险',
      value: valueText(view.competitorSuppressionRate?.current_value, view.competitorSuppressionRate?.unit),
      tone: indicatorClass(view.competitorSuppressionRate?.current_value, view.competitorSuppressionRate?.direction, view.competitorSuppressionRate?.benchmark_value),
      note: metricComparisonText(view.competitorSuppressionRate),
      progress: clampPercent(view.competitorSuppressionRate?.current_value),
      rows: [
        { label: '配置竞品', value: valueText(view.configuredCompetitors.length, 'count') },
        { label: '竞品问题', value: valueText(competitorIssues.length, 'count') },
        { label: '风险线', value: view.competitorSuppressionRate?.benchmark_label || '-' },
      ],
    },
  ]
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
        <h1>GEO 决策仪表盘</h1>
        <p>用可见度、盲区、情感和竞品四个维度，把 AI 搜索中的品牌风险压缩成可扫读、可追踪、可行动的量化判断。</p>
      </div>
      <div className="factor-strip">
        <MetricCard metric={view.visibility} label="可见度" description="query 不提及品牌时，回答中提及品牌的概率" />
        <MetricCard metric={view.avgRank} label="平均位次" description="仅计已提及品牌且位置大于 0 的样本" />
        <MetricCard metric={view.sentimentScore} label="舆情指数" description="正面=1.0 · 中立=0.5 · 负面=0.1 加权均值" />
      </div>
    </>
  )
}

function DecisionBrief({ contract, view }) {
  const modules = buildDecisionModules(contract, view)
  return (
    <Section number="01" title="四维决策快照" className="fade-up decision-section">
      <div className="decision-grid">
        {modules.map(module => (
          <div className={`decision-card ${module.tone}`} key={module.id}>
            <div className="decision-top">
              <div>
                <div className="decision-label">{module.label}</div>
                <div className="decision-title">{module.title}</div>
              </div>
              <span className={`decision-state ${module.tone}`}>{module.tone === 'ok' ? '健康' : module.tone === 'warn' ? '关注' : '风险'}</span>
            </div>
            <div className={`decision-value ${module.tone}`}>{module.value}</div>
            <div className="decision-note">{module.note}</div>
            <div className="decision-bar"><span style={{ width: `${module.progress}%` }} /></div>
            <div className="decision-rows">
              {module.rows.map(row => (
                <div className="decision-row" key={row.label}>
                  <span>{row.label}</span>
                  <b>{row.value}</b>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </Section>
  )
}

function issueMetricValue(issue, metrics) {
  const metricId = issue.abnormal_metric?.metric_id
  const metric = metricId ? metrics[metricId] : null
  if (!metric) return null
  return {
    name: metric.metric_name,
    value: valueText(metric.current_value, metric.unit),
    status: indicatorClass(metric.current_value, metric.direction, metric.benchmark_value),
  }
}

function PriorityFindings({ contract, view, onSelectAction }) {
  const issues = view.keyIssues.slice(0, MAX_FINDINGS)
  if (!issues.length) return null
  return (
    <Section number="02" title="关键盲区与动作" className="fade-up">
      <div className="finding-list">
        {issues.map(issue => {
          const metric = issueMetricValue(issue, view.metrics)
          const actionId = safeArray(issue.recommended_actions)[0]
          const action = safeArray(contract.optimization_actions).find(item => item.action_id === actionId)
          const evidence = safeArray(issue.evidence)[0]
          return (
            <div className="finding-card" key={issue.issue_id || issue.title}>
              <div className="finding-head">
                <div>
                  <div className="finding-kicker">
                    <Chip type={issue.severity === 'P0' ? 'risk' : issue.severity === 'P1' ? 'warn' : 'n'}>{issue.severity || 'P?'}</Chip>
                    <span>{issue.dimension || '诊断发现'}</span>
                  </div>
                  <div className="finding-title">{issue.title}</div>
                </div>
                {metric && <div className={`finding-metric ${metric.status}`}><span>{metric.name}</span><b>{metric.value}</b></div>}
              </div>
              <div className="finding-pain">{issue.business_pain}</div>
              {evidence && (
                <div className="finding-evidence">
                  <span>{safeArray(evidence.platforms).join(' / ') || evidence.intent_id}</span>
                  <b>{evidence.prompt_sample}</b>
                </div>
              )}
              <div className="finding-foot">
                <div className="finding-lifts">
                  {safeArray(issue.expected_metric_lift).slice(0, 3).map(lift => (
                    <Chip key={`${issue.issue_id}-${lift.metric_id}`} type="ok">{lift.metric_id}: {lift.lift}</Chip>
                  ))}
                </div>
                {action && (
                  <button type="button" className="finding-action" onClick={() => onSelectAction(action)}>
                    生成优化内容
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </Section>
  )
}

function ConfigSummary({ view }) {
  return (
    <Section number="03" title="当前配置摘要" className="fade-up">
      <div className="kpis c3">
        <div className="kpi"><div className="kpi-v">{view.configuredTopics.length}</div><div className="kpi-l">业务话题</div></div>
        <div className="kpi"><div className="kpi-v">{view.configuredCompetitors.length}</div><div className="kpi-l">竞品配置</div></div>
        <div className="kpi"><div className="kpi-v warn">{valueText(view.ownCitations?.current_value, view.ownCitations?.unit)}</div><div className="kpi-l">品牌自有引用</div></div>
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
  const actions = safeArray(contract.optimization_actions).slice(0, MAX_LIST_ITEMS)
  return (
    <Section number="04" title="优化方向" className="fade-up">
      <div className="strats">
        {actions.map((action, index) => (
          <button type="button" className="strat strat-clickable" key={action.action_id} onClick={() => onSelectAction(action)}>
            <div className="strat-n">{String(index + 1).padStart(2, '0')}</div>
            <div className="strat-t">{action.action_name}</div>
            <div className="strat-b">产出：{safeArray(action.output_assets).join('、')}。成功指标：{safeArray(action.success_metrics).join('、')}。</div>
            <div className="strat-link">进入内容生成 →</div>
          </button>
        ))}
      </div>
    </Section>
  )
}

function buildMetricOptimizationRows(contract, history) {
  if (!history?.by_metric) return []
  return safeArray(contract.key_metrics)
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
    <Section number="05" title="关键指标观察" className="fade-up">
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
    window.location.assign(FIXED_DIAGNOSTIC_REPORT_URL)
  }

  function handleSelectAction(action) {
    const rules = safeArray(contract.cross_topic_rules)
    const matchedRule = rules.find(rule => safeArray(rule.applies_to).includes(action.action_type)) || rules[0]
    const ruleId = matchedRule?.rule_id || 'rule_content_optimization'
    const brandId = contract.main_brand?.brand_id
    const brandConfigId = contract.main_brand?.brand_config_id || contract.brand_config?.brand_config_id
    const params = new URLSearchParams({
      action_id: action.action_id,
      rule_id: ruleId,
    })
    if (brandId) params.set('brand_id', brandId)
    if (brandConfigId) params.set('brand_config_id', brandConfigId)
    navigate(`/content/generate?${params.toString()}`, {
      state: { actionId: action.action_id, ruleId, brandId, brandConfigId },
    })
  }

  if (loading) return <div className="dashboard-page loading">加载中…</div>
  if (error || !contract) return <div className="dashboard-page loading">{error || 'Dashboard 数据不可用'}</div>

  return (
    <div className="dashboard-page">
      <Hero contract={contract} view={view} onOpenReport={handleOpenReport} />
      <DecisionBrief contract={contract} view={view} />
      <PriorityFindings contract={contract} view={view} onSelectAction={handleSelectAction} />
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
