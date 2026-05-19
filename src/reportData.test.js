import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import fixture from '../src/fixtures/reportData.uploaded.demo.json' with { type: 'json' }
import { applyDisplayRules, computeAiRecommendScoreV63, computeVisibilityV63, normalizeReportData } from '../src/lib/reportDataAdapter.js'
import { generateReportHtml } from '../src/lib/reportGenerator.js'

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

describe('report data contract', () => {
  it('valid report_data fixture renders full report', () => {
    const html = generateReportHtml(fixture)
    assert.match(html, /关键问题&amp;优化建议/)
    assert.match(html, /信源引用情况/)
    assert.match(html, /六平台健康度/)
    assert.match(html, /竞品排名与差距/)
    assert.match(html, /品牌调性分析/)
    assert.match(html, /较上期变化/)
    assert.match(html, /query 不提及品牌时，回答中提及品牌的概率/)
    assert.match(html, /品牌配置/)
    assert.match(html, /文心一言/)
    assert.doesNotMatch(html, /<th>判断<\/th>/)
    assert.doesNotMatch(html, /优化动作与复测计划/)
    assert.doesNotMatch(html, /指标计算与数据说明/)
    assert.doesNotMatch(html, /百度AI/)
  })

  it('normalizes legacy Baidu AI platform name to Wenxin Yiyan', () => {
    const data = clone(fixture)
    data.platforms[0].name = '百度ai'
    const normalized = normalizeReportData(data)
    assert.equal(normalized.platforms[0].name, '文心一言')
  })

  it('brand_config renders the master KPI module from upstream input', () => {
    const data = clone(fixture)
    data.brand_config = {
      aliases_count: 3,
      topics_monitored: 3,
      competitors_count: 4,
      queries_count: 216,
    }
    const html = generateReportHtml(data)
    assert.match(html, /别名数量/)
    assert.match(html, /监测话题/)
    assert.match(html, /横评竞品/)
    assert.match(html, /场景问题/)
    assert.match(html, />216</)
  })

  it('missing platforms renders empty platform section and records missing field', () => {
    const data = clone(fixture)
    delete data.platforms
    const normalized = normalizeReportData(data)
    const html = generateReportHtml(data)
    assert.ok(normalized.audit.missing_fields.includes('platforms'))
    assert.match(html, /暂无平台健康度/)
  })

  it('missing sources renders empty source section and records missing field', () => {
    const data = clone(fixture)
    delete data.sources
    delete data.source_gap
    const normalized = normalizeReportData(data)
    const html = generateReportHtml(data)
    assert.ok(normalized.audit.missing_fields.includes('sources'))
    assert.ok(normalized.audit.missing_fields.includes('source_gap'))
    assert.match(html, /暂无信源数据/)
  })

  it('missing insights renders empty issue section and records missing field', () => {
    const data = clone(fixture)
    delete data.insights
    const normalized = normalizeReportData(data)
    const html = generateReportHtml(data)
    assert.ok(normalized.audit.missing_fields.includes('insights'))
    assert.match(html, /暂无关键问题/)
  })

  it('zero values are rendered as 0, not empty', () => {
    const data = clone(fixture)
    data.global.ai_recommend_score = 0
    data.platforms[0].own_citations = 0
    const html = generateReportHtml(data)
    assert.match(html, />0</)
    assert.doesNotMatch(html, /暂无平台健康度/)
  })

  it('normalizes visibility and AI recommendation formulas', () => {
    const data = clone(fixture)
    data.global.visibility = 0.5
    data.global.rank = 2
    data.global.sentiment_score = 0.6
    data.global.ai_recommend_score = 99
    const normalized = normalizeReportData(data)
    assert.equal(computeVisibilityV63(0.5), 0.5)
    assert.equal(computeAiRecommendScoreV63(0.5, 0.6), 30)
    assert.equal(normalized.global.visibility, 0.5)
    assert.equal(normalized.global.ai_recommend_score, 30)
  })

  it('keeps explicit visibility when rank is missing', () => {
    const data = clone(fixture)
    data.global.visibility = 0.5
    data.global.rank = null
    const normalized = normalizeReportData(data)
    assert.equal(normalized.global.visibility, 0.5)
    assert.equal(normalized.global.ai_recommend_score, 35)
  })

  it('normalizes sentiment topic change for period-over-period display', () => {
    const data = clone(fixture)
    data.topics = [
      { name: '正向话题', positive: 80, neutral: 20, negative: 0, verdict: 'up' },
      { name: '风险话题', positive: 20, neutral: 20, negative: 60, period_change: '↓' },
      { name: '稳定话题', positive: 0, neutral: 100, negative: 0, change: '-' },
    ]
    const normalized = normalizeReportData(data)
    assert.deepEqual(normalized.topics.map(topic => topic.change), ['up', 'down', 'flat'])
  })

  it('uses brand_config business_line as sentiment topic display input', () => {
    const data = clone(fixture)
    data.brand_config.topics = [
      { topic_name: '积分商城管理工具', business_line: '积分商城', priority: 1 },
      { topic_name: '会员权益运营平台', business_line: '会员权益', priority: 2 },
    ]
    data.topics = [
      { name: '积分商城管理工具', positive: 67, neutral: 33, negative: 0, verdict: 'up' },
      { name: '会员权益', positive: 50, neutral: 50, negative: 0, verdict: 'flat' },
    ]
    const normalized = normalizeReportData(data)
    assert.deepEqual(normalized.topics.map(topic => topic.name), ['积分商城', '会员权益'])
  })

  it('keeps business-line-only brand_config topics in the normalized config', () => {
    const data = clone(fixture)
    data.brand_config.topics = [{ business_line: '互动广告', priority: 1 }]
    const normalized = normalizeReportData(data)
    assert.equal(normalized.brand_config.topics[0].business_line, '互动广告')
    assert.equal(normalized.brand_config.topics_monitored, 1)
  })

  it('null values are rendered as 未采集', () => {
    const data = clone(fixture)
    data.global.ai_recommend_score = null
    data.platforms[0].mention_rate = null
    const html = generateReportHtml(data)
    assert.match(html, /未采集/)
  })

  it('report generator output contains no hardcoded mock brand names unless present in input', () => {
    const data = clone(fixture)
    data.meta.brand_name = '测试品牌A'
    data.competitor_ranking = [{ name: '测试品牌A', mention_rate: 0.2, is_self: true }]
    data.sources = []
    data.source_gap = []
    const inputText = JSON.stringify(data)
    const html = generateReportHtml(data)
    for (const name of ['兑吧', '有赞', '微盟']) {
      if (!inputText.includes(name)) assert.doesNotMatch(html, new RegExp(name))
    }
  })

  it('applyDisplayRules truncates arrays and writes audit.truncated', () => {
    const data = normalizeReportData(fixture)
    data.sources = Array.from({ length: 8 }, (_, index) => ({ domain: `source-${index}.test`, type: 'UGC', count: index }))
    data.source_references = Array.from({ length: 8 }, (_, index) => ({
      url: `https://source-${index}.test/case`,
      domain: `source-${index}.test`,
      citation_count: index,
      references: [{ quoted_text: `引用片段 ${index}` }],
    }))
    const display = applyDisplayRules(data)
    assert.equal(display.display.sources.length, 6)
    assert.equal(display.display.source_references.length, 6)
    assert.equal(display.display.source_references[0].url, 'https://source-7.test/case')
    assert.ok(display.audit.truncated.some(item => item.section === 'sources'))
    assert.ok(display.audit.truncated.some(item => item.section === 'source_references'))
  })

  it('renders URL-level source references with collapsible quoted text', () => {
    const data = clone(fixture)
    data.source_references = [
      {
        url: 'https://example.com/case',
        domain: 'example.com',
        title: '案例页',
        type: '第三方',
        citation_count: 2,
        references: [
          {
            platform: 'DeepSeek',
            topic: '积分商城',
            query_id: 'q_001',
            query_text: '金融场景积分商城管理工具有哪些？',
            quoted_text: '兑吧适合金融场景积分商城运营。',
          },
        ],
      },
    ]
    const normalized = normalizeReportData(data)
    const html = generateReportHtml(data)
    assert.equal(normalized.source_references[0].citation_count, 2)
    assert.match(html, /高频引用网址/)
    assert.match(html, /兑吧适合金融场景积分商城运营。/)
    assert.match(html, /<details class="url-ref">/)
  })

  it('normalizeReportData records audit.missing_fields but does not fabricate business data', () => {
    const data = clone(fixture)
    delete data.competitor_ranking
    delete data.insights
    const normalized = normalizeReportData(data)
    assert.deepEqual(normalized.competitor_ranking, [])
    assert.deepEqual(normalized.insights, [])
    assert.ok(normalized.audit.missing_fields.includes('competitor_ranking'))
    assert.ok(normalized.audit.missing_fields.includes('insights'))
  })
})
