import { useState, useEffect } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, CartesianGrid, Cell, RadarChart, Radar,
  PolarGrid, PolarAngleAxis, PolarRadiusAxis, Legend,
} from 'recharts'
import {
  fetchOverview,
  fetchCompetitiveBrands,
  fetchModelBreakdown,
  fetchBrandHistory,
} from '../api/geo.js'
import './VisibilityPage.css'

// ── Helper: 排名变化标识 ──
function RankDelta({ value }) {
  if (value > 0) return <span className="delta delta-up">↑{value}</span>
  if (value < 0) return <span className="delta delta-down">↓{Math.abs(value)}</span>
  return <span className="delta delta-flat">—</span>
}

// ── Helper: 趋势变化 ──
function TrendBadge({ value }) {
  const cls = value > 0 ? 'trend-up' : value < 0 ? 'trend-down' : 'trend-flat'
  const sign = value > 0 ? '+' : ''
  return <span className={`trend-badge ${cls}`}>{sign}{value.toFixed(1)}</span>
}

function formatDelta(value) {
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(1)}`
}

// ── 监测口径与效果变化拆解 ──
function QuerySetMethodology({ data }) {
  const { queryset, metrics, attribution } = data
  if (!queryset || !metrics?.delta_breakdown) return null

  return (
    <div className="methodology-grid fade-up fade-up-1">
      <div className="panel methodology-panel">
        <div className="panel-header">
          <h3>监测题库口径说明</h3>
          <span className="panel-meta mono">{queryset.version} · {queryset.total_queries} 条查询</span>
        </div>
        <div className="queryset-composition">
          <div className="composition-card core">
            <span className="composition-count mono">{queryset.composition.core_anchor}</span>
            <span className="composition-label">核心锚点</span>
            <span className="composition-desc">核心趋势与默认归因</span>
          </div>
          <div className="composition-card adaptive">
            <span className="composition-count mono">{queryset.composition.adaptive}</span>
            <span className="composition-label">动态覆盖</span>
            <span className="composition-desc">新业务覆盖分析</span>
          </div>
          <div className="composition-card experimental">
            <span className="composition-count mono">{queryset.composition.experimental}</span>
            <span className="composition-label">实验场景</span>
            <span className="composition-desc">新场景探索</span>
          </div>
        </div>
        <p className="methodology-note">{data.methodology_note}</p>
        <div className="scope-tags">
          <span>正式监测 {queryset.run_scope.production}</span>
          <span>桥接验证 {queryset.run_scope.bridge}</span>
          <span>影子观察 {queryset.run_scope.shadow}</span>
        </div>
      </div>

      <div className="panel methodology-panel">
        <div className="panel-header">
          <h3>效果变化拆解</h3>
          <span className="panel-meta">归因可信度：{attribution.confidence_label}</span>
        </div>
        <div className="delta-breakdown">
          {metrics.delta_breakdown.map(item => (
            <div key={item.metric_id} className={`delta-card ${item.metric_id === attribution.primary_metric ? 'primary' : ''}`}>
              <div>
                <div className="delta-name">{item.metric_name}</div>
                <div className="delta-desc">{item.interpretation}</div>
              </div>
              <div className="delta-value mono">{formatDelta(item.value)}{item.unit}</div>
            </div>
          ))}
        </div>
        <div className="confidence-reason">{attribution.reason}</div>
      </div>
    </div>
  )
}

// ── 顶部概览卡片 ──
function OverviewCards({ data }) {
  const s = data.summary
  return (
    <div className="overview-grid fade-up">
      <div className="stat-card stat-card-hero">
        <div className="stat-eyebrow">AI 可见度指数 · 品牌可见度</div>
        <div className="stat-row">
          <span className="stat-big">{s.gvi_score}</span>
          <TrendBadge value={s.gvi_delta} />
        </div>
        <div className="stat-sub">
          全局排名 #{s.global_rank} / {s.total_brands}
          <RankDelta value={s.rank_delta} />
        </div>
      </div>

      <div className="stat-card">
        <div className="stat-eyebrow">监测查询数</div>
        <div className="stat-big">{s.total_queries.toLocaleString()}</div>
        <div className="stat-sub mono">{s.platform_count} 平台 × {s.category_count} 品类</div>
      </div>

      <div className="stat-card">
        <div className="stat-eyebrow">品牌提及</div>
        <div className="stat-big">{s.total_mentions.toLocaleString()}</div>
        <div className="stat-sub">
          <span style={{color:'var(--green)'}}>推荐 {data.mention_context.explicit_recommendation}%</span>
          {' · '}
          列举 {data.mention_context.standard_listing}%
        </div>
      </div>

      <div className="stat-card">
        <div className="stat-eyebrow">提及上下文分布</div>
        <div className="context-bars">
          <div className="ctx-bar">
            <span className="ctx-label">明确推荐</span>
            <div className="ctx-track">
              <div className="ctx-fill ctx-green" style={{width: `${data.mention_context.explicit_recommendation}%`}} />
            </div>
            <span className="ctx-val mono">{data.mention_context.explicit_recommendation}%</span>
          </div>
          <div className="ctx-bar">
            <span className="ctx-label">标准列举</span>
            <div className="ctx-track">
              <div className="ctx-fill ctx-blue" style={{width: `${data.mention_context.standard_listing}%`}} />
            </div>
            <span className="ctx-val mono">{data.mention_context.standard_listing}%</span>
          </div>
          <div className="ctx-bar">
            <span className="ctx-label">附带提及</span>
            <div className="ctx-track">
              <div className="ctx-fill ctx-dim" style={{width: `${data.mention_context.incidental_mention}%`}} />
            </div>
            <span className="ctx-val mono">{data.mention_context.incidental_mention}%</span>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── 平台可见度柱状图 ──
function PlatformChart({ data }) {
  return (
    <div className="panel fade-up fade-up-1">
      <div className="panel-header">
        <h3>各平台可见度</h3>
        <span className="panel-meta mono">6 平台 · 回答占有率 %</span>
      </div>
      <div className="chart-container" style={{height: 260}}>
        <ResponsiveContainer>
          <BarChart data={data} margin={{top: 8, right: 12, bottom: 0, left: -10}} barCategoryGap="25%">
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
            <XAxis dataKey="platform" tick={{fill:'#8893A7', fontSize:11}} axisLine={false} tickLine={false} />
            <YAxis tick={{fill:'#556178', fontSize:10}} axisLine={false} tickLine={false} domain={[0, 70]} />
            <Tooltip
              contentStyle={{background:'#1E2640', border:'1px solid rgba(255,255,255,0.08)', borderRadius:8, fontSize:12}}
              labelStyle={{color:'#E8ECF4'}}
              itemStyle={{color:'#8893A7'}}
              formatter={(v) => `${v.toFixed(1)}%`}
            />
            <Bar dataKey="visibility" radius={[4,4,0,0]} name="可见度">
              {data.map((entry, i) => (
                <Cell key={i} fill={entry.color} fillOpacity={0.85} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

// ── 7天趋势折线图 ──
function TrendChart({ data }) {
  return (
    <div className="panel fade-up fade-up-2">
      <div className="panel-header">
        <h3>品牌可见度趋势</h3>
        <span className="panel-meta mono">近 7 日</span>
      </div>
      <div className="chart-container" style={{height: 260}}>
        <ResponsiveContainer>
          <LineChart data={data} margin={{top: 8, right: 12, bottom: 0, left: -10}}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
            <XAxis dataKey="date" tick={{fill:'#8893A7', fontSize:11}} axisLine={false} tickLine={false} />
            <YAxis tick={{fill:'#556178', fontSize:10}} axisLine={false} tickLine={false} domain={['dataMin - 2', 'dataMax + 2']} />
            <Tooltip
              contentStyle={{background:'#1E2640', border:'1px solid rgba(255,255,255,0.08)', borderRadius:8, fontSize:12}}
              labelStyle={{color:'#E8ECF4'}}
              formatter={(v) => `${v.toFixed(1)}`}
            />
            <Line type="monotone" dataKey="gvi" stroke="#3B82F6" strokeWidth={2.5} dot={{r:3, fill:'#3B82F6'}} activeDot={{r:5}} name="GVI" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

// ── 分模型对比柱状图 ──
function ModelBreakdown({ data }) {
  if (!data) return null
  const COLORS = ['#4F6BF6','#FF6B35','#F97316','#22D3EE','#A855F7','#3B82F6']
  return (
    <div className="panel fade-up fade-up-3">
      <div className="panel-header">
        <h3>分模型可见度 · {data.brand_name}</h3>
        <span className="panel-meta mono">一致性指数</span>
      </div>
      <div className="chart-container" style={{height: 280}}>
        <ResponsiveContainer>
          <BarChart data={data.models} margin={{top: 8, right: 12, bottom: 0, left: -10}} barCategoryGap="20%">
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
            <XAxis dataKey="model" tick={{fill:'#8893A7', fontSize:10}} axisLine={false} tickLine={false} />
            <YAxis tick={{fill:'#556178', fontSize:10}} axisLine={false} tickLine={false} domain={[0, 65]} />
            <Tooltip
              contentStyle={{background:'#1E2640', border:'1px solid rgba(255,255,255,0.08)', borderRadius:8, fontSize:12}}
              labelStyle={{color:'#E8ECF4'}}
              formatter={(v, name, props) => {
                if (name === '可见度') return [`${v.toFixed(1)}%`, name]
                return [v, name]
              }}
              content={({active, payload, label}) => {
                if (!active || !payload?.length) return null
                const d = payload[0].payload
                return (
                  <div style={{background:'#1E2640', border:'1px solid rgba(255,255,255,0.08)', borderRadius:8, padding:'10px 14px', fontSize:12}}>
                    <div style={{color:'#E8ECF4', fontWeight:500, marginBottom:4}}>{label}</div>
                    <div style={{color:'#8893A7'}}>可见度: <span style={{color:'#E8ECF4'}}>{d.visibility}%</span></div>
                    <div style={{color:'#8893A7'}}>提及: <span style={{color:'#E8ECF4'}}>{d.mention_count}/{d.total_queries}</span></div>
                    <div style={{color:'#8893A7'}}>一致性: <span style={{color: d.consistency >= 0.85 ? '#22C55E' : '#F59E0B'}}>{(d.consistency*100).toFixed(0)}%</span></div>
                  </div>
                )
              }}
            />
            <Bar dataKey="visibility" radius={[4,4,0,0]} name="可见度">
              {data.models.map((_, i) => <Cell key={i} fill={COLORS[i]} fillOpacity={0.85} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

// ── 竞品排名表格 ──
function CompetitiveTable({ data, onSelectBrand }) {
  const [sortKey, setSortKey] = useState('rank')
  const [expandedBrand, setExpandedBrand] = useState(null)

  const sorted = [...data.rows].sort((a, b) => {
    if (sortKey === 'rank') return a.global.rank - b.global.rank
    if (sortKey === 'visibility') return b.global.visibility - a.global.visibility
    if (sortKey === 'trend') return b.global.trend_7d - a.global.trend_7d
    return 0
  })

  return (
    <div className="panel panel-full fade-up fade-up-4">
      <div className="panel-header">
        <h3>竞品可见度排名</h3>
        <div className="table-controls">
          <button className={`ctrl-btn ${sortKey==='rank'?'active':''}`} onClick={()=>setSortKey('rank')}>按排名</button>
          <button className={`ctrl-btn ${sortKey==='visibility'?'active':''}`} onClick={()=>setSortKey('visibility')}>按可见度</button>
          <button className={`ctrl-btn ${sortKey==='trend'?'active':''}`} onClick={()=>setSortKey('trend')}>按趋势</button>
        </div>
      </div>
      <div className="table-wrapper">
        <table className="data-table">
          <thead>
            <tr>
              <th style={{width:40}}>#</th>
              <th>品牌</th>
              <th>全局可见度</th>
              <th>排名变化</th>
              <th>7日趋势</th>
              <th>DeepSeek</th>
              <th>Kimi</th>
              <th>豆包</th>
              <th>通义</th>
              <th>文心</th>
              <th>元宝</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, i) => (
              <>
                <tr
                  key={row.brand_id}
                  className={`${row.is_main_brand ? 'row-main' : ''} ${expandedBrand === row.brand_id ? 'row-expanded' : ''}`}
                  onClick={() => {
                    setExpandedBrand(expandedBrand === row.brand_id ? null : row.brand_id)
                    onSelectBrand(row.brand_id)
                  }}
                  style={{cursor:'pointer'}}
                >
                  <td className="mono">{row.global.rank}</td>
                  <td>
                    <span className="brand-cell">
                      {row.is_main_brand && <span className="main-badge">本品</span>}
                      {row.brand_name}
                    </span>
                  </td>
                  <td>
                    <div className="vis-cell">
                      <div className="vis-bar-bg">
                        <div
                          className="vis-bar-fill"
                          style={{
                            width: `${row.global.visibility}%`,
                            background: row.is_main_brand ? 'var(--accent)' : 'var(--text-dim)',
                          }}
                        />
                      </div>
                      <span className="mono">{row.global.visibility.toFixed(1)}%</span>
                    </div>
                  </td>
                  <td><RankDelta value={row.global.rank_delta} /></td>
                  <td><TrendBadge value={row.global.trend_7d} /></td>
                  <td className="mono platform-cell">{row.platform_breakdown.deepseek.toFixed(1)}</td>
                  <td className="mono platform-cell">{row.platform_breakdown.kimi.toFixed(1)}</td>
                  <td className="mono platform-cell">{row.platform_breakdown.doubao.toFixed(1)}</td>
                  <td className="mono platform-cell">{row.platform_breakdown.tongyi.toFixed(1)}</td>
                  <td className="mono platform-cell">{row.platform_breakdown.wenxin.toFixed(1)}</td>
                  <td className="mono platform-cell">{row.platform_breakdown.yuanbao.toFixed(1)}</td>
                </tr>
                {expandedBrand === row.brand_id && (
                  <tr key={`${row.brand_id}-expand`} className="expand-row">
                    <td colSpan={11}>
                      <div className="expand-content">
                        <div className="expand-title">分品类可见度</div>
                        <div className="category-chips">
                          {row.categories.map(cat => (
                            <div key={cat.category_id} className="cat-chip">
                              <span className="cat-name">{cat.category_name}</span>
                              <span className="cat-vis mono">{cat.visibility.toFixed(1)}%</span>
                              <span className="cat-rank">#{cat.rank} <RankDelta value={cat.rank_delta} /></span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>
      <div className="table-footer mono">
        快照: {data.snapshot_date} · {data.meta.total_brands_in_global} 品牌 · Prompt {data.meta.prompt_version} · 更新 {new Date(data.meta.last_update).toLocaleTimeString('zh-CN')}
      </div>
    </div>
  )
}

// ── 主页面 ──
export default function VisibilityPage() {
  const [overview, setOverview] = useState(null)
  const [competitive, setCompetitive] = useState(null)
  const [modelData, setModelData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      try {
        const [ov, comp, model] = await Promise.all([
          fetchOverview(),
          fetchCompetitiveBrands(),
          fetchModelBreakdown(10001),
        ])
        if (cancelled) return
        setOverview(ov)
        setCompetitive(comp)
        setModelData(model)
        setError(null)
      } catch (err) {
        if (!cancelled) setError(err.message || '监测数据加载失败')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  const handleSelectBrand = async (brandId) => {
    try {
      const model = await fetchModelBreakdown(brandId)
      setModelData(model)
      setError(null)
    } catch (err) {
      setError(err.message || '分模型数据加载失败')
    }
  }

  if (loading) {
    return (
      <div className="loading-state">
        <div className="loading-spinner" />
        <span>加载监测数据…</span>
      </div>
    )
  }

  if (error || !overview || !competitive) {
    return (
      <div className="loading-state">
        <span>{error || '监测数据不可用'}</span>
      </div>
    )
  }

  return (
    <div className="visibility-page">
      <header className="page-header">
        <div>
          <h1>AI 可见度监测</h1>
          <p className="page-sub">监测品牌在六大 AI 平台的场景化回答占有率，对标竞品与行业标杆表现</p>
        </div>
        <div className="header-right">
          <span className="snapshot-badge mono">
            <span className="dot dot-live" />
            {overview.snapshot_date}
          </span>
        </div>
      </header>

      <OverviewCards data={overview} />

      <QuerySetMethodology data={overview} />

      <div className="chart-grid">
        <PlatformChart data={overview.platform_visibility} />
        <TrendChart data={overview.trend_7d} />
      </div>

      <ModelBreakdown data={modelData} />

      <CompetitiveTable data={competitive} onSelectBrand={handleSelectBrand} />
    </div>
  )
}
