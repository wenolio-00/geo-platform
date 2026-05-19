export const REPORT_SCHEMA_VERSION = 'report_data_schema_v1'
export const REPORT_CONTRACT_VERSION = 'report_data_v1'
export const REPORT_TEMPLATE_VERSION = 'geo_report_generator_goose_yellow_20260509'
export const INDUSTRY_RECOMMEND_TARGET = 90
export const DISPLAY_LIMIT = 6

export const REPORT_METRIC_DEFINITIONS = [
  {
    metric_id: 'rank',
    metric_name: '平均位次',
    aliases: ['avg_rank_position'],
    formula: '品牌被提及时在回答中的平均排名位次（仅计已提及品牌且位置大于 0 的样本）',
    benchmark_value: 2,
    benchmark_label: '≤ 2',
    direction: 'lower_is_better',
    unit: 'rank',
  },
  {
    metric_id: 'visibility',
    metric_name: '可见度',
    formula: 'query 不提及品牌时，回答中提及品牌的概率',
    benchmark_value: 0.5,
    benchmark_label: '≥ 50%',
    direction: 'higher_is_better',
    unit: '%',
  },
  {
    metric_id: 'sentiment_score',
    metric_name: '舆情指数',
    formula: '正面=1.0 · 中立=0.5 · 负面=0.1 的加权均值',
    benchmark_value: 0.6,
    benchmark_label: '≥ 60%',
    direction: 'higher_is_better',
    unit: '%',
  },
  {
    metric_id: 'ai_recommend_score',
    metric_name: 'AI 推荐度',
    formula: '可见度 × 舆情指数 × 100（任意因子为 0 则得分为 0）',
    benchmark_value: 90,
    benchmark_label: '≥ 90',
    direction: 'higher_is_better',
    unit: 'score',
  },
  {
    metric_id: 'own_citations',
    metric_name: '品牌自有引用',
    formula: 'AI 引用的信源中来自品牌官方域名的数量（is_cited=true 的记录数）',
    benchmark_value: 3,
    benchmark_label: '≥ 3',
    direction: 'higher_is_better',
    unit: 'count',
  },
  {
    metric_id: 'competitor_suppression_rate',
    metric_name: '竞品压制率',
    formula: '品牌未出现但竞品出现的样本占总巡检数的比例',
    benchmark_value: 0.3,
    benchmark_label: '< 30%',
    direction: 'lower_is_better',
    unit: '%',
  },
]

export const REPORT_SECTION_ORDER = [
  'executive_summary',
  'insights',
  'sources',
  'platforms',
  'competitors',
  'sentiment',
  'brand_config',
]

export const REPORT_SECTION_TITLES = {
  executive_summary: '00 Executive Summary',
  insights: '01 关键问题&优化建议',
  sources: '02 信源引用情况',
  platforms: '03 六平台健康度',
  competitors: '04 竞品排名与差距',
  sentiment: '05 品牌调性分析',
  brand_config: '06 品牌配置',
}

export const REPORT_COLORS = {
  primary: '#2E5FA3',
  positive: '#2E7D52',
  negative: '#B03A2E',
  neutral: '#6B6B6B',
  gooseYellow: '#F2D36B',
  gooseYellowText: '#8A6A00',
  surface: '#F5F6F8',
  card: '#FFFFFF',
}

export const REQUIRED_PATHS = [
  'meta',
  'meta.report_id',
  'meta.contract_version',
  'meta.template_version',
  'meta.brand_name',
  'meta.report_date',
  'meta.generated_at',
  'meta.total_queries',
  'meta.total_competitors',
  'lineage',
  'lineage.brand_config_id',
  'lineage.entity_id',
  'lineage.queryset_id',
  'lineage.queryset_version',
  'lineage.inspection_batch_id',
  'lineage.inspection_started_at',
  'lineage.inspection_completed_at',
  'lineage.aggregation_version',
  'audit',
  'audit.missing_fields',
  'audit.empty_sections',
  'audit.truncated',
  'audit.validation_errors',
  'audit.schema_version',
  'audit.source',
  'global',
]

export const ARRAY_SECTION_PATHS = {
  insights: 'insights',
  sources: 'sources',
  platforms: 'platforms',
}

export function hasOwnPath(input, path) {
  const keys = path.split('.')
  let value = input
  for (const key of keys) {
    if (!value || !Object.prototype.hasOwnProperty.call(value, key)) return false
    value = value[key]
  }
  return true
}

function getPath(input, path) {
  return path.split('.').reduce((value, key) => value?.[key], input)
}

function cloneAudit(audit = {}) {
  return {
    missing_fields: Array.isArray(audit.missing_fields) ? [...audit.missing_fields] : [],
    empty_sections: Array.isArray(audit.empty_sections) ? [...audit.empty_sections] : [],
    truncated: Array.isArray(audit.truncated) ? [...audit.truncated] : [],
    validation_errors: Array.isArray(audit.validation_errors) ? [...audit.validation_errors] : [],
    schema_version: audit.schema_version || REPORT_SCHEMA_VERSION,
    source: ['api', 'fixture', 'uploaded'].includes(audit.source) ? audit.source : 'api',
  }
}

function unique(values) {
  return Array.from(new Set(values.filter(Boolean)))
}

function toNumberOrNull(value) {
  if (value === null || value === undefined || value === '') return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function roundNumber(value, decimals = 4) {
  if (!Number.isFinite(value)) return null
  const factor = 10 ** decimals
  return Math.round(value * factor) / factor
}

export function computeVisibilityV63(visibility, legacyNaturalVisibility = null) {
  const explicit = toNumberOrNull(visibility)
  if (explicit !== null) return explicit
  return toNumberOrNull(legacyNaturalVisibility)
}

function normalizeSentimentChange(value) {
  const change = toStringOrNull(value)?.toLowerCase()
  if (['up', '↑', 'rise', 'rising', 'increase', 'positive'].includes(change)) return 'up'
  if (['down', '↓', 'fall', 'falling', 'decrease', 'negative'].includes(change)) return 'down'
  if (['flat', '-', 'neutral', 'same', 'stable'].includes(change)) return 'flat'
  return change || null
}

function computeSentimentScoreV63(rawSentiment, fallback) {
  const explicit = toNumberOrNull(fallback)
  if (explicit !== null) return explicit

  if (!rawSentiment || typeof rawSentiment !== 'object') return null
  const positive = toNumberOrNull(rawSentiment.positive_rate)
  const neutral = toNumberOrNull(rawSentiment.neutral_rate)
  const negative = toNumberOrNull(rawSentiment.negative_rate)
  const values = [positive, neutral, negative]
  if (values.every(value => value === null)) return null

  const p = positive ?? 0
  const n = neutral ?? 0
  const neg = negative ?? 0
  const total = p + n + neg
  if (total <= 0) return 0
  return roundNumber((p * 1 + n * 0.5 + neg * 0.1) / total)
}

export function computeAiRecommendScoreV63(visibility, sentimentScore) {
  const v = toNumberOrNull(visibility)
  const sentiment = toNumberOrNull(sentimentScore)
  if (v === null || sentiment === null || v <= 0 || sentiment <= 0) return 0
  return roundNumber(v * sentiment * 100, 2)
}

function computeOwnCitationsV63(rawGlobal, rawSources) {
  const explicit = toNumberOrNull(rawGlobal?.own_citations)
  if (explicit !== null) return explicit

  return normalizeArray(rawSources)
    .filter(row => row?.is_official === true || row?.type === '自有')
    .filter(row => row?.is_cited !== false)
    .reduce((sum, row) => sum + (toNumberOrNull(row?.count) ?? 1), 0)
}

function toStringOrNull(value) {
  if (value === null || value === undefined || value === '') return null
  return String(value)
}

function normalizeArray(value) {
  return Array.isArray(value) ? value : []
}

function normalizePlatformName(name) {
  const value = toStringOrNull(name)
  if (!value) return null
  if (value.replace(/\s+/g, '').toLowerCase() === '百度ai') return '文心一言'
  return value
}

function businessLineLookup(brandConfig) {
  const lookup = new Map()
  for (const topic of normalizeArray(brandConfig?.topics)) {
    const businessLine = toStringOrNull(topic?.business_line)
    const topicName = toStringOrNull(topic?.topic_name)
    const canonical = businessLine || topicName
    if (!canonical) continue
    for (const alias of [businessLine, topicName]) {
      if (alias) lookup.set(alias, canonical)
    }
  }
  return lookup
}

function normalizeTopicRows(rows, brandConfig) {
  const lookup = businessLineLookup(brandConfig)
  const grouped = new Map()

  for (const row of normalizeArray(rows)) {
    const rawName = toStringOrNull(row?.name)
    const name = lookup.get(rawName) || rawName
    if (!name) continue

    const normalized = {
      ...row,
      name,
      positive: toNumberOrNull(row?.positive),
      neutral: toNumberOrNull(row?.neutral),
      negative: toNumberOrNull(row?.negative),
      verdict: toStringOrNull(row?.verdict),
      change: normalizeSentimentChange(row?.change ?? row?.period_change ?? row?.trend ?? row?.verdict),
    }

    const existing = grouped.get(name)
    if (!existing) {
      grouped.set(name, { ...normalized, _topic_row_count: 1 })
      continue
    }

    const count = existing._topic_row_count + 1
    grouped.set(name, {
      ...existing,
      ...normalized,
      positive: averageNullable(existing.positive, normalized.positive, existing._topic_row_count),
      neutral: averageNullable(existing.neutral, normalized.neutral, existing._topic_row_count),
      negative: averageNullable(existing.negative, normalized.negative, existing._topic_row_count),
      change: existing.change === normalized.change ? existing.change : existing.change || normalized.change,
      _topic_row_count: count,
    })
  }

  return Array.from(grouped.values()).map(({ _topic_row_count, ...row }) => row)
}

function averageNullable(existing, incoming, existingCount) {
  if (existing === null) return incoming
  if (incoming === null) return existing
  return roundNumber((existing * existingCount + incoming) / (existingCount + 1), 2)
}

function normalizeBrandConfig(config) {
  if (!config || typeof config !== 'object') return null
  const entityAliases = normalizeArray(config.entity_aliases).filter(Boolean)
  const topics = normalizeArray(config.topics).filter(t => t?.topic_name || t?.business_line).map(t => ({
    topic_name: toStringOrNull(t.topic_name),
    business_line: toStringOrNull(t.business_line),
    priority: toNumberOrNull(t.priority),
  }))
  const competitorList = Array.isArray(config.competitors)
    ? config.competitors.filter(c => c?.name).map(c => ({
      name: toStringOrNull(c.name),
      aliases: normalizeArray(c.aliases).filter(Boolean),
      business_line: toStringOrNull(c.business_line),
      category: toStringOrNull(c.category),
    }))
    : []
  const queryList = normalizeArray(config.queries).filter(Boolean)

  return {
    entity_name: toStringOrNull(config.entity_name),
    entity_aliases: entityAliases,
    industry_segments: normalizeArray(config.industry_segments).filter(Boolean),
    topics,
    competitors: competitorList,
    queries: queryList,
    aliases_count: toNumberOrNull(config.aliases_count ?? config.alias_count ?? config.aliases) ?? entityAliases.length,
    topics_monitored: toNumberOrNull(config.topics_monitored ?? config.topic_count) ?? topics.length,
    competitors_count: toNumberOrNull(config.competitors_count ?? config.competitor_count ?? (Array.isArray(config.competitors) ? null : config.competitors)) ?? competitorList.length,
    queries_count: toNumberOrNull(config.queries_count ?? config.query_count ?? (Array.isArray(config.queries) ? null : config.queries)) ?? queryList.length,
  }
}

function normalizeSourceReferences(rows) {
  return normalizeArray(rows).map(row => {
    const references = normalizeArray(row?.references).map(ref => ({
      ...ref,
      inspection_id: toStringOrNull(ref?.inspection_id),
      platform: toStringOrNull(ref?.platform),
      model: toStringOrNull(ref?.model),
      query_id: toStringOrNull(ref?.query_id),
      query_text: toStringOrNull(ref?.query_text),
      query_pattern: toStringOrNull(ref?.query_pattern),
      query_layer: toStringOrNull(ref?.query_layer),
      topic: toStringOrNull(ref?.topic),
      intent_type: toStringOrNull(ref?.intent_type),
      quoted_text: toStringOrNull(ref?.quoted_text),
      answer_excerpt: toStringOrNull(ref?.answer_excerpt),
    })).filter(ref => ref.quoted_text || ref.answer_excerpt || ref.query_text)

    return {
      ...row,
      url: toStringOrNull(row?.url),
      domain: toStringOrNull(row?.domain),
      title: toStringOrNull(row?.title),
      type: toStringOrNull(row?.type),
      is_official: typeof row?.is_official === 'boolean' ? row.is_official : null,
      citation_count: toNumberOrNull(row?.citation_count) ?? references.length,
      references,
    }
  }).filter(row => row.url && row.domain)
}

function sectionEmpty(data, section) {
  if (section === 'executive_summary') return !data.executive_summary
  if (section === 'sources') {
    return (data.sources?.length ?? 0) === 0 &&
      (data.source_references?.length ?? 0) === 0 &&
      (data.source_gap?.length ?? 0) === 0
  }
  if (section === 'competitors') return (data.competitor_ranking?.length ?? 0) === 0
  if (section === 'sentiment') return !data.sentiment && (data.topics?.length ?? 0) === 0
  if (section === 'brand_config') return !data.brand_config
  const path = ARRAY_SECTION_PATHS[section]
  return path ? (data[path]?.length ?? 0) === 0 : false
}

export function validateReportData(raw) {
  const errors = []
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return { valid: false, errors: ['report_data must be an object'], missingFields: REQUIRED_PATHS }
  }

  const missingFields = REQUIRED_PATHS.filter(path => !hasOwnPath(raw, path))
  errors.push(...missingFields.map(path => `missing required field: ${path}`))

  const source = getPath(raw, 'audit.source')
  if (hasOwnPath(raw, 'audit.source') && !['api', 'fixture', 'uploaded'].includes(source)) {
    errors.push('audit.source must be api, fixture, or uploaded')
  }

  return { valid: errors.length === 0, errors, missingFields }
}

export function normalizeReportData(raw = {}) {
  const validation = validateReportData(raw)
  const audit = cloneAudit(raw.audit)
  audit.missing_fields = unique([...audit.missing_fields, ...validation.missingFields])
  audit.validation_errors = unique([...audit.validation_errors, ...validation.errors])
  const brandConfig = normalizeBrandConfig(raw.brand_config)
  const rank = toNumberOrNull(raw.global?.rank ?? raw.global?.avg_rank_position)
  const visibility = computeVisibilityV63(raw.global?.visibility, raw.global?.natural_visibility)
  const sentimentScore = computeSentimentScoreV63(raw.sentiment, raw.global?.sentiment_score)
  const aiRecommendScore = computeAiRecommendScoreV63(visibility, sentimentScore)
  const ownCitations = computeOwnCitationsV63(raw.global, raw.sources)

  const data = {
    meta: {
      report_id: toStringOrNull(raw.meta?.report_id),
      contract_version: toStringOrNull(raw.meta?.contract_version),
      template_version: toStringOrNull(raw.meta?.template_version),
      brand_name: toStringOrNull(raw.meta?.brand_name),
      brand_tagline: toStringOrNull(raw.meta?.brand_tagline),
      report_date: toStringOrNull(raw.meta?.report_date),
      generated_at: toStringOrNull(raw.meta?.generated_at),
      total_queries: toNumberOrNull(raw.meta?.total_queries),
      total_competitors: toNumberOrNull(raw.meta?.total_competitors),
    },
    lineage: { ...(raw.lineage || {}) },
    audit,
    metric_definitions: REPORT_METRIC_DEFINITIONS,
    executive_summary: toStringOrNull(raw.executive_summary),
    global: {
      rank,
      visibility,
      sentiment_score: sentimentScore,
      ai_recommend_score: aiRecommendScore,
      own_citations: ownCitations,
      competitor_suppression_rate: toNumberOrNull(raw.global?.competitor_suppression_rate),
      summary_text: toStringOrNull(raw.global?.summary_text),
    },
    competitor_ranking: normalizeArray(raw.competitor_ranking).map(row => ({
      ...row,
      name: toStringOrNull(row?.name),
      mention_rate: toNumberOrNull(row?.mention_rate),
      is_self: Boolean(row?.is_self),
    })).filter(row => row.name),
    platforms: normalizeArray(raw.platforms).map(row => ({
      ...row,
      name: normalizePlatformName(row?.name),
      samples: toNumberOrNull(row?.samples),
      mention_rate: toNumberOrNull(row?.mention_rate),
      ai_recommend_score: toNumberOrNull(row?.ai_recommend_score),
      own_citations: toNumberOrNull(row?.own_citations),
      competitor_rank: toNumberOrNull(row?.competitor_rank),
    })).filter(row => row.name),
    sources: normalizeArray(raw.sources).map(row => ({
      ...row,
      domain: toStringOrNull(row?.domain),
      type: toStringOrNull(row?.type),
      count: toNumberOrNull(row?.count),
      is_cited: typeof row?.is_cited === 'boolean' ? row.is_cited : null,
      is_official: typeof row?.is_official === 'boolean' ? row.is_official : null,
    })).filter(row => row.domain),
    source_references: normalizeSourceReferences(raw.source_references),
    source_gap: normalizeArray(raw.source_gap).map(row => ({
      ...row,
      domain: toStringOrNull(row?.domain),
      brand: toNumberOrNull(row?.brand),
      competitor: toNumberOrNull(row?.competitor),
    })).filter(row => row.domain),
    sentiment: raw.sentiment && typeof raw.sentiment === 'object' ? {
      positive_rate: toNumberOrNull(raw.sentiment.positive_rate),
      neutral_rate: toNumberOrNull(raw.sentiment.neutral_rate),
      negative_rate: toNumberOrNull(raw.sentiment.negative_rate),
    } : null,
    topics: normalizeTopicRows(raw.topics, brandConfig),
    optimization_recommendations: normalizeArray(raw.optimization_recommendations).map(row => ({
      ...row,
      title: toStringOrNull(row?.title),
      text: toStringOrNull(row?.text),
      priority: toStringOrNull(row?.priority),
    })).filter(row => row.title || row.text),
    retest_plan: raw.retest_plan ?? null,
    brand_config: brandConfig,
    insights: normalizeArray(raw.insights).map(row => ({
      ...row,
      priority: toStringOrNull(row?.priority),
      text: toStringOrNull(row?.text),
    })).filter(row => row.priority || row.text),
    display: {},
  }

  for (const path of ['insights', 'sources', 'source_references', 'source_gap', 'platforms', 'competitor_ranking', 'topics', 'brand_config']) {
    if (!hasOwnPath(raw, path)) data.audit.missing_fields = unique([...data.audit.missing_fields, path])
  }

  data.audit.empty_sections = unique([
    ...data.audit.empty_sections,
    ...REPORT_SECTION_ORDER.filter(section => sectionEmpty(data, section)),
  ])

  return data
}

function truncateRows(rows, section, audit, limit = DISPLAY_LIMIT) {
  if (!Array.isArray(rows)) return []
  if (rows.length <= limit) return rows
  audit.truncated.push({ section, original_count: rows.length, displayed_count: limit })
  return rows.slice(0, limit)
}

export function applyDisplayRules(normalized) {
  const data = {
    ...normalized,
    audit: cloneAudit(normalized.audit),
    display: {},
  }

  data.competitor_ranking = [...data.competitor_ranking]
    .sort((a, b) => (b.mention_rate ?? -Infinity) - (a.mention_rate ?? -Infinity))
  data.sources = [...data.sources]
    .sort((a, b) => (b.count ?? -Infinity) - (a.count ?? -Infinity))
  data.source_references = [...data.source_references]
    .sort((a, b) => (b.citation_count ?? -Infinity) - (a.citation_count ?? -Infinity))
  data.platforms = [...data.platforms]
    .sort((a, b) => (b.ai_recommend_score ?? -Infinity) - (a.ai_recommend_score ?? -Infinity))
  data.insights = [...data.insights]
  data.topics = [...data.topics]
  data.optimization_recommendations = [...data.optimization_recommendations]

  data.display.competitor_ranking = truncateRows(data.competitor_ranking, 'competitor_ranking', data.audit)
  data.display.sources = truncateRows(data.sources, 'sources', data.audit)
  data.display.source_references = truncateRows(data.source_references, 'source_references', data.audit)
  data.display.source_gap = truncateRows(data.source_gap, 'source_gap', data.audit)
  data.display.platforms = truncateRows(data.platforms, 'platforms', data.audit)
  data.display.insights = truncateRows(data.insights, 'insights', data.audit)
  data.display.topics = truncateRows(data.topics, 'topics', data.audit)
  data.display.optimization_recommendations = truncateRows(data.optimization_recommendations, 'optimization_recommendations', data.audit)

  data.audit.empty_sections = unique([
    ...data.audit.empty_sections,
    ...REPORT_SECTION_ORDER.filter(section => sectionEmpty(data, section)),
  ])

  return data
}

export function buildReportDisplayData(raw) {
  return applyDisplayRules(normalizeReportData(raw))
}

export function getReportDataState(raw, error = null) {
  if (error) return { status: 'error', message: '数据加载失败' }
  if (!raw) return { status: 'empty', message: '暂无巡检数据' }
  const validation = validateReportData(raw)
  if (!validation.valid) return { status: 'invalid', message: '报告数据结构异常', errors: validation.errors }
  return { status: 'ready', message: 'ready' }
}

export function isNullishValue(value) {
  return value === null || value === undefined
}
