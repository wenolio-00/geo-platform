import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { generateReportHtml } from '../src/lib/reportGenerator.js'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = join(__dirname, '..')
const base = JSON.parse(readFileSync(join(root, 'src/fixtures/reportData.uploaded.demo.json'), 'utf8'))

const queryset = [
  { category: '寿险保障', sentiment: '中性', queries: ['寿险 怎么样', '定期寿险 真实评价', '终身寿险 值不值得买', '寿险 买前必看'] },
  { category: '寿险保障', sentiment: '正向', queries: ['寿险 推荐', '定期寿险 性价比高', '终身寿险 哪款好', '家庭支柱 寿险推荐'] },
  { category: '寿险保障', sentiment: '负向', queries: ['寿险 坑不坑', '寿险 理赔难不难', '寿险 有没有必要买', '寿险 后悔买吗'] },
  { category: '健康医疗险', sentiment: '中性', queries: ['医疗险 怎么样', '重疾险 真实评价', '百万医疗险 值不值得买', '医疗险 买前必看'] },
  { category: '健康医疗险', sentiment: '正向', queries: ['医疗险 推荐', '重疾险 性价比高', '百万医疗险 哪款好', '健康险 值得入手吗'] },
  { category: '健康医疗险', sentiment: '负向', queries: ['医疗险 坑不坑', '重疾险 不赔是真的吗', '医疗险 理赔麻烦吗', '健康险 劝退'] },
  { category: '养老年金', sentiment: '中性', queries: ['年金险 怎么样', '养老险 真实评价', '养老年金 值不值得买', '年金险 买前必看'] },
  { category: '养老年金', sentiment: '正向', queries: ['年金险 推荐', '养老险 哪款好', '年金险 收益怎么样', '养老规划 保险推荐'] },
  { category: '养老年金', sentiment: '负向', queries: ['年金险 坑不坑', '年金险 收益低吗', '养老险 后悔买吗', '年金险 劝退'] },
]

const queries = queryset.flatMap(group =>
  group.queries.map((query, index) => ({
    id: `zy_${group.category}_${group.sentiment}_${index + 1}`,
    text: query,
    category: group.category,
    sentiment: group.sentiment,
  }))
)

const report = structuredClone(base)
report.meta = {
  ...report.meta,
  report_id: 'zhongyi_life_reuse_latest_20260609',
  generated_at: '2026-06-09T16:30:00+08:00',
  brand_name: '中意人寿',
  brand_tagline: '寿险保障 / 健康医疗险 / 养老年金',
  report_date: '2026.06.09',
  total_queries: queries.length,
  total_competitors: 4,
}
const competitors = [
  { name: '中国人寿', aliases: ['国寿'], business_line: '寿险', category: '头部寿险公司' },
  { name: '平安人寿', aliases: ['中国平安人寿'], business_line: '寿险', category: '头部寿险公司' },
  { name: '太平洋人寿', aliases: ['太保寿险'], business_line: '寿险', category: '头部寿险公司' },
  { name: '泰康人寿', aliases: ['泰康'], business_line: '寿险', category: '头部寿险公司' },
]

report.brand_config = {
  entity_name: '中意人寿',
  entity_aliases: ['中意人寿保险有限公司', '中意人寿保险', '中意人寿'],
  industry_segments: ['保险', '人寿保险', '健康险', '养老年金'],
  topics: [
    { topic_name: '寿险保障', business_line: '寿险', priority: 1 },
    { topic_name: '健康医疗险', business_line: '健康险', priority: 1 },
    { topic_name: '养老年金', business_line: '养老险', priority: 1 },
  ],
  competitors,
  queries,
  aliases_count: 3,
  topics_monitored: 3,
  competitors_count: competitors.length,
  queries_count: queries.length,
}
report.competitor_ranking = [
  { name: '中意人寿', visibility: 0.681, mention_rate: 0.681, is_self: true },
  { name: '中国人寿', visibility: 0.304, mention_rate: 0.304, is_self: false },
  { name: '平安人寿', visibility: 0.297, mention_rate: 0.297, is_self: false },
  { name: '太平洋人寿', visibility: 0.297, mention_rate: 0.297, is_self: false },
  { name: '泰康人寿', visibility: 0.261, mention_rate: 0.261, is_self: false },
]
report.sources = []
report.source_references = []
report.source_gap = []
report.source_gap_by_domain = []
report.lineage = {
  ...report.lineage,
  brand_config_id: 'zhongyi_life_local_brand_config',
  entity_id: 'zhongyi_life_local_entity',
  queryset_id: 'local_zhongyi_life_reuse_latest_queryset',
  queryset_version: 'zhongyi_life_reuse_latest_v20260609',
  parent_queryset_id: null,
  queryset_policy: 'reuse_latest',
  queryset_governance: {
    source: 'local_fixture',
    trigger: 'brand=中意人寿 && queryset_policy=reuse_latest',
    categories: queryset.map(group => group.category).filter((category, index, arr) => arr.indexOf(category) === index),
  },
  inspection_batch_id: 'zhongyi_life_local_batch_20260609',
  inspection_started_at: '2026-06-09T16:00:00+08:00',
  inspection_completed_at: '2026-06-09T16:30:00+08:00',
}
report.insights = [
  { priority: 'P0', text: '本地快速报告已使用“中意人寿”复用上一次 QuerySet，共覆盖寿险保障、健康医疗险、养老年金 3 类 36 条 query。' },
  { priority: 'P1', text: '当前报告基于本地 fixture 模板渲染，用于快速出稿；真实 AI 采集结果需要后端诊断任务完成后替换。' },
  { priority: 'P0', text: 'AI 推荐度 70，距离行业推荐线（90+）仍有提升空间。当前 AI 对中意人寿的提及中，仍有较多列举式内容，需要补充更明确的推荐理由和可验证证据。' },
  { priority: 'P1', text: '本轮 queryset 已覆盖用户在选购寿险、医疗险、养老年金时最常见的中性了解、正向推荐和负向顾虑场景，可直接用于快速回检。' },
]
report.topic_platform_visibility = [
  {
    topic: '寿险保障',
    platforms: [
      {
        platform: 'DeepSeek',
        samples: 12,
        visibility_eligible_samples: 10,
        visibility: 0.625,
        competitor_rank: 1,
        competitors: [
          { name: '中意人寿', visibility: 0.625, mention_rate: 0.7, rank: 1, is_self: true },
          { name: '中国人寿', visibility: 0.375, mention_rate: 0.4, rank: 2, is_self: false },
          { name: '平安人寿', visibility: 0.25, mention_rate: 0.3, rank: 3, is_self: false },
        ],
      },
      {
        platform: 'Kimi',
        samples: 12,
        visibility_eligible_samples: 9,
        visibility: 0.5714,
        competitor_rank: 2,
        competitors: [
          { name: '中国人寿', visibility: 0.7143, mention_rate: 0.6667, rank: 1, is_self: false },
          { name: '中意人寿', visibility: 0.5714, mention_rate: 0.6667, rank: 2, is_self: true },
          { name: '泰康人寿', visibility: 0.2857, mention_rate: 0.3333, rank: 3, is_self: false },
        ],
      },
    ],
  },
  {
    topic: '健康医疗险',
    platforms: [
      {
        platform: '通义千问',
        samples: 12,
        visibility_eligible_samples: 9,
        visibility: 0.5,
        competitor_rank: 2,
        competitors: [
          { name: '平安人寿', visibility: 0.6667, mention_rate: 0.75, rank: 1, is_self: false },
          { name: '中意人寿', visibility: 0.5, mention_rate: 0.625, rank: 2, is_self: true },
          { name: '太平洋人寿', visibility: 0.3333, mention_rate: 0.5, rank: 3, is_self: false },
        ],
      },
    ],
  },
  {
    topic: '养老年金',
    platforms: [
      {
        platform: '豆包',
        samples: 12,
        visibility_eligible_samples: 8,
        visibility: 0.5,
        competitor_rank: 2,
        competitors: [
          { name: '泰康人寿', visibility: 0.625, mention_rate: 0.625, rank: 1, is_self: false },
          { name: '中意人寿', visibility: 0.5, mention_rate: 0.5, rank: 2, is_self: true },
          { name: '中国人寿', visibility: 0.25, mention_rate: 0.25, rank: 3, is_self: false },
        ],
      },
    ],
  },
]
report.sentiment = {
  positive_ratio: 0.48,
  neutral_ratio: 0.41,
  negative_ratio: 0.11,
  ai_recommend_score: 48,
  topic_breakdown: [
    { topic: '寿险保障', positive_ratio: 0.52, neutral_ratio: 0.38, negative_ratio: 0.10, verdict: 'up' },
    { topic: '健康医疗险', positive_ratio: 0.44, neutral_ratio: 0.42, negative_ratio: 0.14, verdict: 'flat' },
    { topic: '养老年金', positive_ratio: 0.39, neutral_ratio: 0.45, negative_ratio: 0.16, verdict: 'down' },
  ],
}
report.recommendations = [
  { stage: '01', title: '优先补强寿险与健康险场景中的品牌推荐理由', body: '围绕理赔服务、产品适配人群、保障范围差异，补充更容易被 AI 直接引用的结构化 FAQ 与对比页。' },
  { stage: '02', title: '为养老年金类 query 增加收益解释与风险边界表达', body: '针对“收益低吗”“后悔买吗”一类负向 query，补齐常见误解澄清、收益测算口径和适用人群说明。' },
]
report.audit = {
  missing_fields: [],
  empty_sections: ['sources', 'source_references', 'source_gap'],
  truncated: [],
  validation_errors: [],
  schema_version: 'report_data_schema_v1',
  source: 'local_fixture',
}
report.platforms = [
  { name: '元宝', samples: 36, mention_rate: 0.87, ai_recommend_score: 81, own_citations: 10, competitor_rank: 1 },
  { name: 'Kimi', samples: 36, mention_rate: 0.783, ai_recommend_score: 78, own_citations: 7, competitor_rank: 2 },
  { name: '通义千问', samples: 36, mention_rate: 0.739, ai_recommend_score: 69, own_citations: 6, competitor_rank: 2 },
  { name: 'DeepSeek', samples: 36, mention_rate: 0.652, ai_recommend_score: 66, own_citations: 5, competitor_rank: 1 },
  { name: '豆包', samples: 36, mention_rate: 0.652, ai_recommend_score: 70, own_citations: 7, competitor_rank: 2 },
  { name: '文心一言', samples: 36, mention_rate: 0.391, ai_recommend_score: 56, own_citations: 0, competitor_rank: 3 },
]
report.global = {
  natural_visibility: 0.681,
  rank: 1.37,
  sentiment_score: 0.7,
  ai_recommend_score: 70,
  own_citations: 0,
}
report.executive_summary = '本报告为中意人寿本地快速版 GEO 诊断，用于先行展示“复用上一次”queryset 的覆盖范围与报告版式，当前分数和平台表现为本地模板值，真实结果需以后端巡检替换。'
report.summary = report.executive_summary
report.source_references = []
report.source_comparison = []
report.source_gap_by_domain = []
report.sources = []
report.source_domains = []
report.top_sources = []
report.own_source_domains = []
report.competitor_source_domains = []
report.high_frequency_citations = []
report.quote_references = []
report.citation_references = []
report.url_references = []
report.brand_name = '中意人寿'
report.entity_name = '中意人寿'
report.name = '中意人寿'
report.report_name = '中意人寿 GEO 诊断报告'
report.diagnostic_run = { run_id: 'zhongyi_local_run_20260609' }
report.latest_run_id = 'zhongyi_local_run_20260609'
report.report = { run_id: 'zhongyi_local_run_20260609' }
report.report_data = report.report_data || {}
report.report_data.brand_name = '中意人寿'
report.report_data.queries = queries
report.queryset = {
  id: 'local_zhongyi_life_reuse_latest_queryset',
  version: 'zhongyi_life_reuse_latest_v20260609',
  total_queries: queries.length,
  composition: {
    core_anchor: 12,
    adaptive: 12,
    experimental: 12,
  },
  run_scope: {
    production: 36,
    bridge: 0,
    shadow: 0,
  },
}
report.queries = queries
report.query_list = queries
report.queryset_queries = queries
report.competitor_ranking = report.competitor_ranking.map((item, index) => ({ ...item, rank: index + 1 }))
for (const topic of report.topic_platform_visibility) {
  for (const platform of topic.platforms) {
    platform.competitors = platform.competitors.map((item, index) => ({ ...item, rank: index + 1 }))
  }
}

const jsonPath = join(root, 'src/fixtures/reportData.zhongyi-life.local.json')
const htmlPath = join(root, 'dist/zhongyi-life-geo-report.html')
writeFileSync(jsonPath, `${JSON.stringify(report, null, 2)}\n`)
writeFileSync(htmlPath, generateReportHtml(report))
console.log(`JSON: ${jsonPath}`)
console.log(`HTML: ${htmlPath}`)
console.log(`Queries: ${queries.length}`)
