/**
 * GEO Platform Mock Data
 * ─────────────────────────────────────────────────────
 * 数据结构对齐后端 API 接口规格，同时补充关键词/Prompt 端落地颗粒度。
 * 开发对接时只需把 fetch mock 替换为真实 API 调用。
 *
 * 接口映射:
 *   GET /api/v1/geo/competitive-brands  → getCompetitiveBrands()
 *   GET /api/v1/geo/brands/{id}/model-breakdown → getModelBreakdown()
 *   GET /api/v1/geo/brands/{id}/history → getBrandHistory()
 *   GET /api/v1/geo/overview → getOverview()
 *   GET /api/v1/geo/dashboard-contract → getDashboardContract()
 */

// ── 品牌基础数据 ──────────────────────────────────────

const BRANDS = {
  duiba: {
    brand_id: 10001,
    brand_name: '杭州兑吧网络科技有限公司',
    short_name: '兑吧',
    aliases: ['兑吧', '兑吧网络', 'Duiba'],
    category: '金融积分与会员权益运营 SaaS',
    is_main: true,
  },
  youzan: {
    brand_id: 10002,
    brand_name: '有赞',
    short_name: '有赞',
    aliases: ['Youzan'],
    category: '泛电商 SaaS',
    is_main: false,
  },
  weimob: {
    brand_id: 10003,
    brand_name: '微盟',
    short_name: '微盟',
    aliases: ['Weimob'],
    category: '泛电商 SaaS',
    is_main: false,
  },
  qiaotuoyun: {
    brand_id: 10004,
    brand_name: '乔拓云',
    short_name: '乔拓云',
    aliases: [],
    category: '商城与建站 SaaS',
    is_main: false,
  },
  jiandaoyun: {
    brand_id: 10005,
    brand_name: '简道云',
    short_name: '简道云',
    aliases: [],
    category: '零代码应用平台',
    is_main: false,
  },
  xingyao: {
    brand_id: 10006,
    brand_name: '星耀',
    short_name: '星耀',
    aliases: [],
    category: '金融积分运营',
    is_main: false,
  },
  lingzhi: {
    brand_id: 10007,
    brand_name: '灵智',
    short_name: '灵智',
    aliases: [],
    category: '金融权益运营',
    is_main: false,
  },
  huoban: {
    brand_id: 10008,
    brand_name: '伙伴云',
    short_name: '伙伴云',
    aliases: [],
    category: '零代码协作平台',
    is_main: false,
  },
}

const PLATFORM_PRESETS = {
  official_site: ['官网场景页', '产品详情页', 'FAQ 页面'],
  case_study: ['官网案例页', '客户故事页', '行业白皮书'],
  ugc_social: ['知乎问答', '小红书笔记', '公众号内容'],
  qa_forum: ['知乎问答', '行业问答平台', '选型对比帖'],
  website_content: ['官网场景页', '对比页', 'FAQ 页面'],
  ugc_content: ['知乎问答', '小红书笔记', '公众号内容'],
  qa_answer: ['知乎回答', '行业问答平台', '选型问答'],
}

const TYPE_LABELS = {
  website_content: '官网内容',
  ugc_content: 'UGC 内容',
  qa_answer: '问答内容',
  official_site: '官网信源',
  case_study: '客户案例',
  media_news: '行业媒体',
  tech_community: '技术社区',
  ugc_social: '社媒内容',
  qa_forum: '问答平台',
  rewrite_rules: '改写规则',
  comparison_page: '对比页',
}

function intentLabel(intentId) {
  return intentId
    .replace('intent_', '')
    .replace(/_/g, ' ')
    .replace('points mall vendor', '积分商城供应商推荐')
    .replace('bank points exchange', '银行积分兑换运营')
    .replace('member growth platform', '会员权益增长平台')
    .replace('app benefits ops', 'App 权益运营方案')
    .replace('interactive ad sdk', '互动广告接入方案')
    .replace('app monetization', 'App 流量变现方案')
    .replace('finance loyalty vendor', '金融积分权益服务商')
    .replace('compliance case proof', '金融案例与合规证明')
    .replace('duiba vs youzan weimob', '兑吧与有赞微盟对比')
    .replace('saas selection criteria', '权益运营 SaaS 选型标准')
    .replace('official source validation', '官网权威信源验证')
    .replace('ugc topic coverage', 'UGC 话题覆盖')
}

function buildMockGeneratedText(contract, action, rule) {
  const brand = contract.main_brand.short_name
  const primaryAsset = action.output_assets[0] || action.action_name
  const intentLabels = action.related_intent_ids.slice(0, 3).map(intentLabel).join('、')
  return [
    `${brand}建议围绕“${action.action_name}”优先输出${primaryAsset}，并用${rule.rule_name}统一内容结构。`,
    `正文可按“明确主张 + 能力事实 + 证据证明”展开：先明确${brand}在对应场景的定位，再补充产品能力、客户案例和可引用证据。`,
    `建议同步覆盖相关意图：${intentLabels}，确保文本既能解释业务价值，也能被 AI 平台稳定抽取。`,
  ].join('\n\n')
}

function buildMockPublishPlatforms(action, rule) {
  const presets = PLATFORM_PRESETS[action.target_sources?.[0]] || ['官网', '知乎', '公众号']
  const rulePlatforms = {
    official_site: ['官网场景页'],
    case_study: ['官网案例页'],
    media_news: ['行业媒体稿'],
    tech_community: ['技术社区内容'],
    ugc_social: ['知乎', '小红书', '公众号'],
    qa_forum: ['知乎问答', '行业问答平台'],
  }
  const extra = rule.applies_to.flatMap(type => rulePlatforms[type] || [])
  return Array.from(new Set([...presets, ...extra]))
}

// ── 六大平台 ──────────────────────────────────────

const PLATFORMS = [
  { key: 'deepseek', name: 'DeepSeek', color: '#4F6BF6' },
  { key: 'kimi', name: 'Kimi', color: '#FF6B35' },
  { key: 'doubao', name: '豆包', color: '#22D3EE' },
  { key: 'tongyi', name: '通义千问', color: '#F97316' },
  { key: 'wenxin', name: '文心一言', color: '#3B82F6' },
  { key: 'yuanbao', name: '混元元宝', color: '#A855F7' },
]

// ── 业务场景 / 品类定义 ──────────────────────────────────────

const SCENARIOS = [
  {
    id: 501,
    scenario_id: 'scenario_points_mall',
    name: '积分商城管理工具',
    business_line: '积分商城',
    objective: '让 AI 在金融机构积分商城建设、积分兑换、供应链运营问题中识别兑吧。',
    intent_ids: ['intent_points_mall_vendor', 'intent_bank_points_exchange'],
  },
  {
    id: 502,
    scenario_id: 'scenario_member_benefits',
    name: '会员权益运营平台',
    business_line: '会员权益',
    objective: '让 AI 在 App 会员权益、权益包、会员增长问题中形成“兑吧=权益运营”的稳定标签。',
    intent_ids: ['intent_member_growth_platform', 'intent_app_benefits_ops'],
  },
  {
    id: 503,
    scenario_id: 'scenario_interactive_ads',
    name: '互动广告接入',
    business_line: '互动广告',
    objective: '让 AI 在 App 互动广告、激励广告、流量变现方案中把兑吧纳入候选。',
    intent_ids: ['intent_interactive_ad_sdk', 'intent_app_monetization'],
  },
  {
    id: 504,
    scenario_id: 'scenario_finance_operation',
    name: '金融场景运营',
    business_line: '金融场景',
    objective: '突出兑吧对银行、保险、消费金融客户的场景经验和合规表达。',
    intent_ids: ['intent_finance_loyalty_vendor', 'intent_compliance_case_proof'],
  },
  {
    id: 505,
    scenario_id: 'scenario_competitor_compare',
    name: '竞品对比与选型',
    business_line: '品牌选型',
    objective: '在有赞、微盟、兑吧等工具比较问题中占据可解释位置。',
    intent_ids: ['intent_duiba_vs_youzan_weimob', 'intent_saas_selection_criteria'],
  },
  {
    id: 506,
    scenario_id: 'scenario_source_authority',
    name: '权威信源覆盖',
    business_line: '内容资产',
    objective: '补齐官网、案例、媒体、UGC、问答等可被 AI 引用的证据资产。',
    intent_ids: ['intent_official_source_validation', 'intent_ugc_topic_coverage'],
  },
]

const CATEGORIES = SCENARIOS.map(({ id, name, scenario_id, business_line, intent_ids }) => ({
  id,
  name,
  scenario_id,
  business_line,
  intent_ids,
}))

// ── 关键词 / Prompt 端落地颗粒度 ───────────────────────────────

const KEYWORD_INTENTS = [
  {
    intent_id: 'intent_points_mall_vendor',
    scenario_id: 'scenario_points_mall',
    intent_name: '积分商城系统供应商推荐',
    funnel_stage: 'solution_discovery',
    user_role: '银行零售业务运营负责人',
    search_intent: '寻找可建设积分商城、权益兑换和供应链运营的一体化服务商。',
    prompt_templates: [
      '银行积分商城系统有哪些成熟供应商？请按适合金融机构的程度推荐。',
      '公司想做积分兑换商城，有哪些 SaaS 或运营服务商可以选？',
      '适合银行信用卡积分商城的解决方案厂商有哪些？',
    ],
    must_match_entities: ['兑吧', '积分商城', '金融机构'],
    evaluation_rules: {
      mention_required: true,
      preferred_context: 'explicit_recommendation',
      positive_claims: ['金融机构服务经验', '积分兑换运营', '权益供应链'],
      negative_claims: ['仅适合电商小程序', '缺少金融行业经验'],
    },
    priority: 1,
  },
  {
    intent_id: 'intent_bank_points_exchange',
    scenario_id: 'scenario_points_mall',
    intent_name: '银行积分兑换运营方案',
    funnel_stage: 'problem_solution_fit',
    user_role: '银行信用卡中心产品经理',
    search_intent: '比较积分兑换、权益履约、活动运营的落地方案。',
    prompt_templates: [
      '银行积分兑换运营怎么做，有哪些外部平台能支持？',
      '信用卡积分兑换商城如何提升用户活跃和兑换率？',
      '金融机构积分运营需要哪些系统能力？',
    ],
    must_match_entities: ['兑吧', '积分兑换', '权益履约'],
    evaluation_rules: {
      mention_required: true,
      preferred_context: 'standard_listing',
      positive_claims: ['兑换链路', '运营活动', '数据分析'],
      negative_claims: ['泛泛营销工具', '缺少履约能力'],
    },
    priority: 1,
  },
  {
    intent_id: 'intent_member_growth_platform',
    scenario_id: 'scenario_member_benefits',
    intent_name: '会员权益增长平台推荐',
    funnel_stage: 'solution_discovery',
    user_role: 'App 增长负责人',
    search_intent: '寻找能用会员权益提升留存、活跃和转化的平台。',
    prompt_templates: [
      'App 会员权益运营平台有哪些推荐？',
      '想提升会员活跃，有哪些权益运营 SaaS 可以用？',
      '会员权益平台选型应该看哪些公司？',
    ],
    must_match_entities: ['兑吧', '会员权益', '用户增长'],
    evaluation_rules: {
      mention_required: true,
      preferred_context: 'explicit_recommendation',
      positive_claims: ['会员增长', '权益运营', 'App 场景'],
      negative_claims: ['只做电商店铺', '只做 CRM'],
    },
    priority: 1,
  },
  {
    intent_id: 'intent_app_benefits_ops',
    scenario_id: 'scenario_member_benefits',
    intent_name: 'App 权益运营落地方案',
    funnel_stage: 'implementation',
    user_role: '互联网 App 运营经理',
    search_intent: '寻找可直接落地的权益配置、活动策略和用户分层运营方案。',
    prompt_templates: [
      'App 里做会员权益运营，具体可以怎么落地？',
      '权益包、积分、任务活动如何组合提升 App 留存？',
      '有哪些公司能提供 App 权益运营和活动工具？',
    ],
    must_match_entities: ['兑吧', '权益包', '活动运营'],
    evaluation_rules: {
      mention_required: true,
      preferred_context: 'standard_listing',
      positive_claims: ['权益配置', '任务活动', '运营工具'],
      negative_claims: ['概念化建议', '没有供应商名称'],
    },
    priority: 2,
  },
  {
    intent_id: 'intent_interactive_ad_sdk',
    scenario_id: 'scenario_interactive_ads',
    intent_name: '互动广告 SDK 接入',
    funnel_stage: 'vendor_selection',
    user_role: '商业化产品经理',
    search_intent: '寻找 App 内互动广告、激励广告、任务广告的接入服务商。',
    prompt_templates: [
      'App 想接入互动广告，有哪些平台或 SDK？',
      '激励广告和互动广告服务商有哪些？',
      '移动应用商业化除了穿山甲、优量汇还有哪些互动广告方案？',
    ],
    must_match_entities: ['兑吧', '互动广告', 'App 商业化'],
    evaluation_rules: {
      mention_required: true,
      preferred_context: 'standard_listing',
      positive_claims: ['互动广告', '激励任务', '流量变现'],
      negative_claims: ['只提广告联盟', '没有兑吧历史业务'],
    },
    priority: 3,
  },
  {
    intent_id: 'intent_app_monetization',
    scenario_id: 'scenario_interactive_ads',
    intent_name: 'App 流量变现工具比较',
    funnel_stage: 'comparison',
    user_role: 'App 商业化负责人',
    search_intent: '比较广告联盟、互动任务、权益营销对变现和留存的影响。',
    prompt_templates: [
      'App 流量变现工具有哪些，怎么选择？',
      '互动广告和权益运营能否一起提升 App 收入？',
      '适合工具类 App 的商业化方案有哪些？',
    ],
    must_match_entities: ['兑吧', '流量变现', '互动任务'],
    evaluation_rules: {
      mention_required: true,
      preferred_context: 'incidental_mention',
      positive_claims: ['变现', '权益激励', '活动互动'],
      negative_claims: ['仅广告联盟', '缺少运营闭环'],
    },
    priority: 3,
  },
  {
    intent_id: 'intent_finance_loyalty_vendor',
    scenario_id: 'scenario_finance_operation',
    intent_name: '金融积分权益服务商',
    funnel_stage: 'vendor_selection',
    user_role: '金融机构采购与业务负责人',
    search_intent: '寻找有金融客户经验、能支撑积分权益和营销活动的服务商。',
    prompt_templates: [
      '金融机构做积分权益运营，有哪些专业服务商？',
      '银行保险客户常用哪些会员权益运营平台？',
      '适合金融行业的积分商城和权益平台有哪些？',
    ],
    must_match_entities: ['兑吧', '金融机构', '权益运营'],
    evaluation_rules: {
      mention_required: true,
      preferred_context: 'explicit_recommendation',
      positive_claims: ['金融客户', '合规', '积分权益'],
      negative_claims: ['泛电商工具', '无金融案例'],
    },
    priority: 1,
  },
  {
    intent_id: 'intent_compliance_case_proof',
    scenario_id: 'scenario_finance_operation',
    intent_name: '金融行业案例与合规证明',
    funnel_stage: 'trust_validation',
    user_role: '金融机构合规与采购团队',
    search_intent: '验证服务商是否有金融场景案例、交付经验和可信信源。',
    prompt_templates: [
      '兑吧有没有银行或金融行业客户案例？',
      '金融权益运营服务商如何证明自己可靠？',
      '选择积分权益供应商时需要哪些案例和合规材料？',
    ],
    must_match_entities: ['兑吧', '银行案例', '合规'],
    evaluation_rules: {
      mention_required: true,
      preferred_context: 'standard_listing',
      positive_claims: ['客户案例', '合规材料', '服务经验'],
      negative_claims: ['查不到案例', '信源不足'],
    },
    priority: 2,
  },
  {
    intent_id: 'intent_duiba_vs_youzan_weimob',
    scenario_id: 'scenario_competitor_compare',
    intent_name: '兑吧 vs 有赞/微盟对比',
    funnel_stage: 'comparison',
    user_role: 'SaaS 选型负责人',
    search_intent: '比较兑吧、有赞、微盟在会员权益、积分商城、商城建站上的差异。',
    prompt_templates: [
      '兑吧、有赞、微盟分别适合什么场景？',
      '会员权益运营选择兑吧还是有赞微盟？',
      '积分商城系统和微商城系统有什么区别，代表厂商有哪些？',
    ],
    must_match_entities: ['兑吧', '有赞', '微盟'],
    evaluation_rules: {
      mention_required: true,
      preferred_context: 'standard_listing',
      positive_claims: ['差异化定位', '金融积分', '权益运营'],
      negative_claims: ['只推荐有赞微盟', '把兑吧归为泛电商建站'],
    },
    priority: 1,
  },
  {
    intent_id: 'intent_saas_selection_criteria',
    scenario_id: 'scenario_competitor_compare',
    intent_name: '权益运营 SaaS 选型标准',
    funnel_stage: 'comparison',
    user_role: '企业数字化负责人',
    search_intent: '明确选型维度，并识别各类厂商能力边界。',
    prompt_templates: [
      '选择会员权益运营 SaaS 应该看哪些指标？',
      '积分商城、会员权益、微商城平台选型怎么区分？',
      '企业做用户运营，如何选择有赞、微盟、兑吧这类服务商？',
    ],
    must_match_entities: ['兑吧', '选型', '权益运营'],
    evaluation_rules: {
      mention_required: true,
      preferred_context: 'standard_listing',
      positive_claims: ['选型维度', '能力边界', '业务场景'],
      negative_claims: ['只按品牌知名度推荐', '忽略金融权益场景'],
    },
    priority: 2,
  },
  {
    intent_id: 'intent_official_source_validation',
    scenario_id: 'scenario_source_authority',
    intent_name: '官网权威信源验证',
    funnel_stage: 'trust_validation',
    user_role: 'AI 答案生成与企业采购用户',
    search_intent: '判断兑吧官网是否提供可引用的定位、案例、产品说明和证据。',
    prompt_templates: [
      '兑吧是做什么的？有哪些官网资料可以证明？',
      '兑吧的核心产品和客户案例有哪些？',
      '兑吧在积分商城和权益运营上的权威信息来源是什么？',
    ],
    must_match_entities: ['兑吧', '官网', '客户案例'],
    evaluation_rules: {
      mention_required: true,
      preferred_context: 'standard_listing',
      positive_claims: ['官网资料', '产品说明', '客户案例'],
      negative_claims: ['信息过旧', '无法引用官网'],
    },
    priority: 1,
  },
  {
    intent_id: 'intent_ugc_topic_coverage',
    scenario_id: 'scenario_source_authority',
    intent_name: 'UGC/问答话题覆盖',
    funnel_stage: 'awareness',
    user_role: '运营与内容负责人',
    search_intent: '让小红书、知乎、公众号、短视频等内容形成可检索的场景化讨论。',
    prompt_templates: [
      '有哪些积分商城运营案例值得参考？',
      '会员权益运营有哪些实操经验？',
      '金融 App 用户增长和权益运营怎么做？',
    ],
    must_match_entities: ['兑吧', '案例', '实操经验'],
    evaluation_rules: {
      mention_required: false,
      preferred_context: 'incidental_mention',
      positive_claims: ['实操经验', '案例复盘', '行业讨论'],
      negative_claims: ['无第三方讨论', '只出现招聘或工商信息'],
    },
    priority: 2,
  },
]

const SOURCE_TYPES = [
  { source_id: 'official_site', source_name: '品牌官网', role: '承接权威定位、产品能力、案例证据' },
  { source_id: 'case_study', source_name: '客户案例/白皮书', role: '证明金融行业与运营效果' },
  { source_id: 'media_news', source_name: '门户/新闻', role: '提升第三方可信度和品牌实体识别' },
  { source_id: 'tech_community', source_name: '技术社区', role: '解释 SDK、接口、系统能力' },
  { source_id: 'ugc_social', source_name: 'UGC/内容平台', role: '沉淀场景化经验和长尾问题覆盖' },
  { source_id: 'qa_forum', source_name: '问答平台', role: '覆盖用户真实选型与对比问题' },
]

const BENCHMARKS = {
  natural_visibility: { metric_name: '自然可见度', duiba: 68.1, competitor_avg: 76.4, leader: { brand: '有赞', value: 83.0 }, industry_p75: 50.0 },
  rank: { metric_name: '平均位次', duiba: 4.8, competitor_avg: 2.4, leader: { brand: '有赞', value: 1.7 }, industry_p75: 2.0 },
  visibility: { metric_name: '可见度', duiba: 14.2, competitor_avg: 31.8, leader: { brand: '有赞', value: 48.8 }, industry_p75: 40.0 },
  sentiment_score: { metric_name: '舆情指数', duiba: 70.0, competitor_avg: 83.0, leader: { brand: '有赞', value: 91.0 }, industry_p75: 60.0 },
  ai_recommend_score: { metric_name: 'AI 推荐度', duiba: 9.9, competitor_avg: 26.4, leader: { brand: '有赞', value: 44.4 }, industry_p75: 90.0 },
  own_citations: { metric_name: '品牌自有引用', duiba: 35, competitor_avg: 18, leader: { brand: '兑吧', value: 35 }, industry_p75: 3 },
  competitor_suppression_rate: { metric_name: '竞品压制率', duiba: 24.0, competitor_avg: 18.0, leader: { brand: '有赞', value: 12.0 }, industry_p75: 30.0 },
}

const PLATFORM_VISIBILITY = {
  duiba: { deepseek: 21.0, kimi: 14.0, doubao: 15.0, tongyi: 24.0, wenxin: 16.0, yuanbao: 17.0 },
  youzan: { deepseek: 82.0, kimi: 74.0, doubao: 79.0, tongyi: 77.0, wenxin: 75.0, yuanbao: 80.0 },
  weimob: { deepseek: 73.0, kimi: 68.0, doubao: 67.0, tongyi: 69.0, wenxin: 66.0, yuanbao: 71.0 },
  qiaotuoyun: { deepseek: 58.0, kimi: 49.0, doubao: 53.0, tongyi: 57.0, wenxin: 51.0, yuanbao: 55.0 },
  jiandaoyun: { deepseek: 45.0, kimi: 47.0, doubao: 49.0, tongyi: 50.0, wenxin: 52.0, yuanbao: 44.0 },
  xingyao: { deepseek: 32.0, kimi: 28.0, doubao: 24.0, tongyi: 35.0, wenxin: 27.0, yuanbao: 30.0 },
  lingzhi: { deepseek: 29.0, kimi: 24.0, doubao: 26.0, tongyi: 31.0, wenxin: 22.0, yuanbao: 27.0 },
  huoban: { deepseek: 39.0, kimi: 42.0, doubao: 40.0, tongyi: 41.0, wenxin: 38.0, yuanbao: 37.0 },
}

const BRAND_METRICS = {
  duiba: { visibility: 18.2, rank: 7, rank_delta: +1, trend_7d: +2.4, avg_position: 6.8, source_coverage: 21, evidence_count: 12, sentiment_score: 72, scenario_coverage: 33 },
  youzan: { visibility: 78.0, rank: 1, rank_delta: 0, trend_7d: +1.8, avg_position: 1.7, source_coverage: 82, evidence_count: 168, sentiment_score: 91, scenario_coverage: 81 },
  weimob: { visibility: 69.0, rank: 2, rank_delta: 0, trend_7d: +0.7, avg_position: 2.2, source_coverage: 76, evidence_count: 142, sentiment_score: 87, scenario_coverage: 84 },
  qiaotuoyun: { visibility: 54.0, rank: 3, rank_delta: +1, trend_7d: +1.1, avg_position: 3.8, source_coverage: 59, evidence_count: 88, sentiment_score: 78, scenario_coverage: 62 },
  jiandaoyun: { visibility: 48.0, rank: 4, rank_delta: -1, trend_7d: -0.3, avg_position: 4.1, source_coverage: 61, evidence_count: 94, sentiment_score: 76, scenario_coverage: 58 },
  xingyao: { visibility: 31.0, rank: 5, rank_delta: +2, trend_7d: +2.9, avg_position: 5.4, source_coverage: 37, evidence_count: 38, sentiment_score: 70, scenario_coverage: 44 },
  lingzhi: { visibility: 27.0, rank: 6, rank_delta: 0, trend_7d: +0.6, avg_position: 5.9, source_coverage: 32, evidence_count: 31, sentiment_score: 68, scenario_coverage: 39 },
  huoban: { visibility: 39.0, rank: 8, rank_delta: -2, trend_7d: -1.4, avg_position: 4.7, source_coverage: 54, evidence_count: 74, sentiment_score: 74, scenario_coverage: 51 },
}

const CATEGORY_VISIBILITY = {
  duiba: [26.0, 22.0, 18.0, 24.0, 14.0, 5.0],
  youzan: [82.0, 78.0, 65.0, 52.0, 76.0, 81.0],
  weimob: [73.0, 74.0, 58.0, 49.0, 69.0, 70.0],
  qiaotuoyun: [48.0, 46.0, 39.0, 30.0, 52.0, 45.0],
  jiandaoyun: [32.0, 41.0, 28.0, 35.0, 44.0, 50.0],
  xingyao: [44.0, 29.0, 12.0, 38.0, 18.0, 21.0],
  lingzhi: [38.0, 31.0, 10.0, 34.0, 16.0, 19.0],
  huoban: [22.0, 24.0, 20.0, 18.0, 28.0, 35.0],
}

const INTENT_BREAKDOWN = {
  duiba: [
    { intent_id: 'intent_points_mall_vendor', mention_rate: 31, avg_position: 5.4, evidence_count: 3, benchmark_gap: -47, context: 'standard_listing' },
    { intent_id: 'intent_bank_points_exchange', mention_rate: 21, avg_position: 6.1, evidence_count: 2, benchmark_gap: -43, context: 'incidental_mention' },
    { intent_id: 'intent_member_growth_platform', mention_rate: 24, avg_position: 5.9, evidence_count: 2, benchmark_gap: -51, context: 'standard_listing' },
    { intent_id: 'intent_app_benefits_ops', mention_rate: 19, avg_position: 6.6, evidence_count: 1, benchmark_gap: -49, context: 'incidental_mention' },
    { intent_id: 'intent_interactive_ad_sdk', mention_rate: 18, avg_position: 6.4, evidence_count: 1, benchmark_gap: -28, context: 'incidental_mention' },
    { intent_id: 'intent_app_monetization', mention_rate: 15, avg_position: 7.2, evidence_count: 1, benchmark_gap: -33, context: 'incidental_mention' },
    { intent_id: 'intent_finance_loyalty_vendor', mention_rate: 29, avg_position: 4.8, evidence_count: 2, benchmark_gap: -34, context: 'standard_listing' },
    { intent_id: 'intent_compliance_case_proof', mention_rate: 12, avg_position: 7.5, evidence_count: 0, benchmark_gap: -46, context: 'incidental_mention' },
    { intent_id: 'intent_duiba_vs_youzan_weimob', mention_rate: 14, avg_position: 7.0, evidence_count: 0, benchmark_gap: -57, context: 'incidental_mention' },
    { intent_id: 'intent_saas_selection_criteria', mention_rate: 11, avg_position: 7.4, evidence_count: 1, benchmark_gap: -52, context: 'incidental_mention' },
    { intent_id: 'intent_official_source_validation', mention_rate: 9, avg_position: 8.0, evidence_count: 1, benchmark_gap: -61, context: 'incidental_mention' },
    { intent_id: 'intent_ugc_topic_coverage', mention_rate: 2, avg_position: 9.0, evidence_count: 0, benchmark_gap: -66, context: 'not_mentioned' },
  ],
  youzan: [
    { intent_id: 'intent_points_mall_vendor', mention_rate: 78, avg_position: 1.6, evidence_count: 23, benchmark_gap: 0, context: 'explicit_recommendation' },
    { intent_id: 'intent_member_growth_platform', mention_rate: 76, avg_position: 1.8, evidence_count: 21, benchmark_gap: 0, context: 'explicit_recommendation' },
    { intent_id: 'intent_duiba_vs_youzan_weimob', mention_rate: 71, avg_position: 2.0, evidence_count: 18, benchmark_gap: 0, context: 'explicit_recommendation' },
  ],
  weimob: [
    { intent_id: 'intent_member_growth_platform', mention_rate: 74, avg_position: 2.1, evidence_count: 19, benchmark_gap: -2, context: 'explicit_recommendation' },
    { intent_id: 'intent_duiba_vs_youzan_weimob', mention_rate: 68, avg_position: 2.4, evidence_count: 17, benchmark_gap: -3, context: 'standard_listing' },
    { intent_id: 'intent_saas_selection_criteria', mention_rate: 70, avg_position: 2.3, evidence_count: 16, benchmark_gap: -4, context: 'standard_listing' },
  ],
}

function getBrandKeyById(brandId) {
  return Object.keys(BRANDS).find(key => BRANDS[key].brand_id === brandId) || 'duiba'
}

function getCategoryRows(brandKey) {
  const values = CATEGORY_VISIBILITY[brandKey]
  return CATEGORIES.map((cat, index) => ({
    category_id: cat.id,
    category_name: cat.name,
    scenario_id: cat.scenario_id,
    business_line: cat.business_line,
    intent_ids: cat.intent_ids,
    prompt_count: cat.intent_ids.reduce((sum, intentId) => {
      const intent = KEYWORD_INTENTS.find(item => item.intent_id === intentId)
      return sum + (intent?.prompt_templates.length || 0)
    }, 0),
    visibility: values[index],
    mention_rate: values[index],
    avg_position: Math.round((9 - values[index] / 14) * 10) / 10,
    evidence_count: Math.max(0, Math.round(values[index] / 8)),
    benchmark_gap: Math.round((values[index] - 64) * 10) / 10,
    rank: [...Object.keys(CATEGORY_VISIBILITY)]
      .sort((a, b) => CATEGORY_VISIBILITY[b][index] - CATEGORY_VISIBILITY[a][index])
      .indexOf(brandKey) + 1,
    rank_delta: brandKey === 'duiba' && index < 2 ? +1 : 0,
  }))
}

function buildCompetitiveRow(brandKey) {
  const brand = BRANDS[brandKey]
  const metrics = BRAND_METRICS[brandKey]
  return {
    brand_id: brand.brand_id,
    brand_name: brand.brand_name,
    short_name: brand.short_name,
    is_main_brand: brand.is_main,
    global: {
      visibility: metrics.visibility,
      rank: metrics.rank,
      rank_delta: metrics.rank_delta,
      trend_7d: metrics.trend_7d,
      avg_position: metrics.avg_position,
      source_coverage: metrics.source_coverage,
      evidence_count: metrics.evidence_count,
      sentiment_score: metrics.sentiment_score,
    },
    categories: getCategoryRows(brandKey),
    platform_breakdown: PLATFORM_VISIBILITY[brandKey],
    intent_breakdown: INTENT_BREAKDOWN[brandKey] || getCategoryRows(brandKey).flatMap(cat => cat.intent_ids.map(intentId => ({
      intent_id: intentId,
      mention_rate: Math.max(8, Math.round(cat.visibility - 8)),
      avg_position: cat.avg_position,
      evidence_count: cat.evidence_count,
      benchmark_gap: cat.benchmark_gap,
      context: cat.visibility >= 55 ? 'standard_listing' : 'incidental_mention',
    }))),
  }
}

function buildKeywordScope() {
  return {
    scenario_count: SCENARIOS.length,
    intent_count: KEYWORD_INTENTS.length,
    prompt_template_count: KEYWORD_INTENTS.reduce((sum, item) => sum + item.prompt_templates.length, 0),
    platform_count: PLATFORMS.length,
    evaluation_method: 'binary mention rate + answer position + context quality + citation evidence',
    granularity_path: 'business_line → scenario → keyword_intent → prompt_template → model_answer → mention/context/evidence',
    core_abnormalities: [
      { metric: '回答占有率', current: 18.2, benchmark: 47.6, gap: -29.4, issue_id: 'issue_low_answer_share' },
      { metric: '信源覆盖率', current: 21, benchmark: 64, gap: -43, issue_id: 'issue_source_gap' },
      { metric: '场景覆盖率', current: 33, benchmark: 76, gap: -43, issue_id: 'issue_scenario_tag_gap' },
    ],
  }
}

const QUERYSET_METHODOLOGY = {
  version: 'v1.3',
  total_queries: 30,
  composition: {
    core_anchor: 18,
    adaptive: 9,
    experimental: 3,
  },
  run_scope: {
    production: 24,
    bridge: 3,
    shadow: 3,
  },
  metric_basis: {
    core: '核心锚点问题仅用于核心趋势和默认优化任务归因。',
    adaptive: '自适应问题用于新业务覆盖分析，不直接污染核心趋势。',
    experimental: '实验问题用于探索新场景，暂不参与正式归因。',
  },
}

const EFFECT_DELTA_BREAKDOWN = [
  {
    metric_id: 'effect_delta_core',
    metric_name: '核心趋势变化',
    value: 3.2,
    unit: 'pp',
    interpretation: '稳定问题池同口径变化，可用于长期趋势判断。',
  },
  {
    metric_id: 'effect_delta_targeted',
    metric_name: '任务命中变化',
    value: 8.5,
    unit: 'pp',
    interpretation: '本轮优化任务命中的目标问题改善幅度。',
  },
  {
    metric_id: 'effect_delta_adaptive',
    metric_name: '新业务覆盖变化',
    value: 5.1,
    unit: 'pp',
    interpretation: 'Adaptive Query 反映的新业务场景覆盖变化。',
  },
  {
    metric_id: 'effect_delta_full',
    metric_name: '全量可见度变化',
    value: 1.7,
    unit: 'pp',
    interpretation: '生产口径下 Core + Adaptive 的整体变化，仅作辅助解释。',
  },
]

const ATTRIBUTION_SUMMARY = {
  confidence: 'medium',
  confidence_label: 'Medium',
  reason: '目标 Query 明显改善，但部分 Adaptive Query 仍处于 bridge 观察期。',
  primary_metric: 'effect_delta_targeted',
}

const BASELINE_RULES_STORE = [
  {
    rule_id: 'baseline_duiba_geo_v1',
    rule_version: 'baseline_v1.0',
    rule_name: '兑吧 GEO 基准规则',
    source_type: 'baseline',
    status: 'active',
    maintained_by: 'user',
    updated_at: '2026-05-09',
    applies_to: ['website_content', 'ugc_content', 'qa_answer', 'rewrite_rules', 'comparison_page', 'case_study'],
    template: '所有内容先统一“杭州兑吧网络科技有限公司 / 兑吧”实体表达，再按“主张 + 事实 + 证据”输出事实、能力、证据和适用场景；不得编造数据、客户案例、排名或攻击竞品。',
    required_elements: ['品牌实体', '业务场景', '事实表达', '证据来源', '风险约束'],
  },
]

const PLATFORM_RULES_STORE = [
  {
    rule_id: 'auto_rule_claim_fact_proof_duiba_v1',
    rule_version: 'auto_v1.0',
    rule_name: '金融场景主张-事实-证据强化',
    source_type: 'auto_generated',
    status: 'candidate',
    extracted_from: 'rule_extraction',
    extracted_at: '2026-05-09',
    platforms: ['DeepSeek', 'Kimi', '通义千问'],
    query_patterns: ['scenario_explore', 'category_rec', 'decision_confirm'],
    action_types: ['website_content', 'rewrite_rules'],
    applies_to: ['website_content', 'rewrite_rules'],
    template: '围绕金融机构、积分兑换、会员权益履约三个标签组织内容，每段必须包含明确主张、可验证事实和官网/案例证据槽位。',
    required_elements: ['金融机构', '积分兑换', '权益履约', '官网证据', '案例证据'],
  },
  {
    rule_id: 'auto_rule_competitor_boundary_duiba_v1',
    rule_version: 'auto_v1.0',
    rule_name: '竞品边界分层对比',
    source_type: 'auto_generated',
    status: 'candidate',
    extracted_from: 'rule_extraction',
    extracted_at: '2026-05-09',
    platforms: ['豆包'],
    query_patterns: ['competitive_comp'],
    action_types: ['comparison_page', 'qa_answer'],
    applies_to: ['comparison_page', 'qa_answer'],
    template: '将有赞/微盟定位为泛电商 SaaS，将兑吧定位为金融积分权益运营服务商，但必须给出来源和能力边界，不能使用攻击性表述。',
    required_elements: ['竞品名称', '能力边界', '兑吧差异化', '可追溯证据'],
  },
]

const RULE_ACTIVATION_EVALUATIONS = [
  {
    evaluation_id: 'eval_rule_activation_20260509_001',
    baseline_rule_version: 'baseline_v1.0',
    auto_rule_version: 'auto_v1.0',
    auto_rule_id: 'auto_rule_claim_fact_proof_duiba_v1',
    platform: 'mixed',
    query_pattern: 'scenario_explore/category_rec/decision_confirm',
    action_type: 'website_content/rewrite_rules',
    decision: 'activate_task_specific',
    confidence: 'medium',
    reason: '任务命中改善为正，实用性校验未下降，且 DeepSeek、Kimi、通义千问的平台拆分表现均优于基准规则；但样本仍不足以全局启用。',
    metric_snapshot: {
      effect_delta_targeted: 8.5,
      utility_check_delta: 0.4,
      answer_share_delta: 6.8,
      platform_pass_count: 3,
      platform_total: 6,
    },
    risk_check: [
      { risk_item: 'fabricated_data', status: 'pass', explanation: '规则要求证据槽位，不允许生成不可验证数字。' },
      { risk_item: 'utility_check_decline', status: 'pass', explanation: '复测快照中 utility_check 未下降。' },
      { risk_item: 'platform_specific_bias', status: 'unknown', explanation: '仅三类平台表现稳定，需继续观察其他平台。' },
    ],
    created_at: '2026-05-09T18:10:00+08:00',
  },
  {
    evaluation_id: 'eval_rule_activation_20260509_002',
    baseline_rule_version: 'baseline_v1.0',
    auto_rule_version: 'auto_v1.0',
    auto_rule_id: 'auto_rule_competitor_boundary_duiba_v1',
    platform: '豆包',
    query_pattern: 'competitive_comp',
    action_type: 'comparison_page/qa_answer',
    decision: 'keep_baseline',
    confidence: 'low',
    reason: '候选规则只在单平台单场景有弱改善，且竞品比较存在证据不足风险，暂不进入 active_rules_store。',
    metric_snapshot: {
      effect_delta_targeted: 1.2,
      utility_check_delta: -0.1,
      answer_share_delta: 0.8,
      platform_pass_count: 1,
      platform_total: 6,
    },
    risk_check: [
      { risk_item: 'competitor_attack', status: 'unknown', explanation: '需要人工确认边界表达。' },
      { risk_item: 'evidence_traceability_issue', status: 'unknown', explanation: '缺少足够竞品能力来源。' },
      { risk_item: 'utility_check_decline', status: 'fail', explanation: '样本快照中 utility_check 有轻微下降。' },
    ],
    created_at: '2026-05-09T18:10:00+08:00',
  },
]

const ACTIVE_RULES_STORE = [
  {
    active_rule_id: 'active_baseline_duiba_geo_v1',
    source_rule_id: 'baseline_duiba_geo_v1',
    source_type: 'baseline',
    rule_version: 'baseline_v1.0',
    rule_name: '兑吧 GEO 基准规则',
    platform: 'all',
    query_pattern: 'all',
    action_type: 'all',
    status: 'active',
    activated_by_evaluation_id: null,
    activated_at: '2026-05-09T18:10:00+08:00',
    applies_to: BASELINE_RULES_STORE[0].applies_to,
    template: BASELINE_RULES_STORE[0].template,
    required_elements: BASELINE_RULES_STORE[0].required_elements,
  },
  {
    active_rule_id: 'active_auto_claim_fact_proof_duiba_v1',
    source_rule_id: 'auto_rule_claim_fact_proof_duiba_v1',
    source_type: 'auto_generated',
    rule_version: 'auto_v1.0',
    rule_name: '金融场景主张-事实-证据强化',
    platform: 'DeepSeek/Kimi/通义千问',
    query_pattern: 'scenario_explore/category_rec/decision_confirm',
    action_type: 'website_content/rewrite_rules',
    status: 'active',
    activated_by_evaluation_id: 'eval_rule_activation_20260509_001',
    activated_at: '2026-05-09T18:10:00+08:00',
    applies_to: ['website_content', 'rewrite_rules'],
    template: PLATFORM_RULES_STORE[0].template,
    required_elements: PLATFORM_RULES_STORE[0].required_elements,
  },
]

function buildRuleActivationGate() {
  return {
    workflow_position: {
      insert_after: '08 Rule Extraction · 平台内容偏好规则提取',
      node: '08.5 Rule Activation Evaluator · 规则激活评估器',
      insert_before: '13 生成优化任务 · 按优先级互斥触发',
    },
    default_decision_policy: {
      mvp_default: 'keep_baseline',
      activation_requires: ['positive_effect_delta', 'no_utility_check_decline', 'platform_level_evidence', 'risk_check_pass'],
      fallback_rule: 'baseline_rule',
    },
    stores: {
      baseline_rules_store: BASELINE_RULES_STORE,
      platform_rules_store: PLATFORM_RULES_STORE,
      rule_activation_evaluations: RULE_ACTIVATION_EVALUATIONS,
      active_rules_store: ACTIVE_RULES_STORE,
    },
    actiontask_rule_source: '优化任务只读取 active_rules_store；若没有匹配规则，则回退 baseline_rules_store 的 active version。',
  }
}

// ── 概览数据 ──────────────────────────────────────

export function getOverview() {
  return {
    snapshot_date: '2026-05-06',
    main_brand: '杭州兑吧网络科技有限公司',
    summary: {
      gvi_score: 18.2,
      gvi_delta: +2.4,
      global_rank: 7,
      rank_delta: +1,
      total_brands: 215,
      total_queries: 216,
      total_mentions: 118,
      platform_count: 6,
      category_count: 6,
    },
    trend_7d: [
      { date: '04-30', gvi: 14.8 },
      { date: '05-01', gvi: 15.2 },
      { date: '05-02', gvi: 15.9 },
      { date: '05-03', gvi: 16.1 },
      { date: '05-04', gvi: 16.8 },
      { date: '05-05', gvi: 17.4 },
      { date: '05-06', gvi: 18.2 },
    ],
    platform_visibility: PLATFORMS.map(platform => ({
      platform: platform.name,
      visibility: PLATFORM_VISIBILITY.duiba[platform.key],
      color: platform.color,
    })),
    mention_context: {
      explicit_recommendation: 6.4,
      standard_listing: 31.5,
      incidental_mention: 62.1,
    },
    queryset: QUERYSET_METHODOLOGY,
    metrics: {
      effect_delta_core: 3.2,
      effect_delta_targeted: 8.5,
      effect_delta_adaptive: 5.1,
      effect_delta_full: 1.7,
      delta_breakdown: EFFECT_DELTA_BREAKDOWN,
    },
    attribution: ATTRIBUTION_SUMMARY,
    methodology_note: '核心趋势仅基于 production Core Anchor Query 计算；Adaptive 用于新业务覆盖，Experimental 用于探索。',
    contract: {
      keyword_scope: buildKeywordScope(),
      monitored_scenarios: SCENARIOS,
      keyword_intents: KEYWORD_INTENTS,
      source_types: SOURCE_TYPES,
    },
  }
}

// ── 竞品排名表 ──────────────────────────────────────
// 对齐 GET /api/v1/geo/competitive-brands

export function getCompetitiveBrands() {
  const orderedKeys = ['youzan', 'weimob', 'qiaotuoyun', 'jiandaoyun', 'xingyao', 'lingzhi', 'duiba', 'huoban']

  return {
    snapshot_date: '2026-05-06',
    refresh_at: '2026-05-06T02:30:00Z',
    rows: orderedKeys.map(buildCompetitiveRow),
    contract: {
      keyword_scope: buildKeywordScope(),
      benchmarks: BENCHMARKS,
      source_types: SOURCE_TYPES,
    },
    meta: {
      total_brands_in_global: 215,
      prompt_version: 'duiba_2026Q2_landing_granularity_v1',
      model_set: PLATFORMS.map(platform => platform.name),
      last_update: '2026-05-06T02:30:00Z',
    },
  }
}

// ── 分模型下钻 ──────────────────────────────────────
// 对齐 GET /api/v1/geo/brands/{id}/model-breakdown

export function getModelBreakdown(brandId = 10001) {
  const brandKey = getBrandKeyById(brandId)
  const brand = BRANDS[brandKey]
  const platforms = PLATFORM_VISIBILITY[brandKey]

  return {
    brand_id: brand.brand_id,
    brand_name: brand.brand_name,
    snapshot_date: '2026-05-06',
    models: PLATFORMS.map(platform => {
      const visibility = platforms[platform.key]
      return {
        model: platform.name,
        platform_key: platform.key,
        visibility,
        mention_count: Math.round(visibility * 0.72),
        total_queries: 72,
        consistency: Math.min(0.94, Math.max(0.48, Math.round((0.55 + visibility / 180) * 100) / 100)),
        intent_breakdown: getCategoryRows(brandKey).flatMap(cat => cat.intent_ids.map(intentId => ({
          intent_id: intentId,
          scenario_id: cat.scenario_id,
          mention_rate: Math.max(0, Math.round((cat.visibility + visibility) / 2 - 6)),
          avg_position: cat.avg_position,
          context: visibility >= 55 ? 'standard_listing' : visibility >= 25 ? 'incidental_mention' : 'not_mentioned',
          evidence_count: cat.evidence_count,
        }))),
      }
    }),
    contract: {
      keyword_scope: buildKeywordScope(),
      keyword_intents: KEYWORD_INTENTS,
    },
  }
}

// ── 趋势历史 ──────────────────────────────────────
// 对齐 GET /api/v1/geo/brands/{id}/history

export function getBrandHistory(brandId = 10001, days = 30) {
  const brandKey = getBrandKeyById(brandId)
  const brand = BRANDS[brandKey]
  const base = brandKey === 'duiba' ? 12 : Math.max(28, BRAND_METRICS[brandKey].visibility - 8)
  const data = []

  for (let i = days; i >= 0; i--) {
    const d = new Date()
    d.setDate(d.getDate() - i)
    const dateStr = `${(d.getMonth()+1).toString().padStart(2,'0')}-${d.getDate().toString().padStart(2,'0')}`
    const noise = Math.sin(i * 0.35) * 1.4
    const trend = (days - i) * (brandKey === 'duiba' ? 0.21 : 0.08)
    data.push({
      date: dateStr,
      gvi: Math.round((base + trend + noise) * 10) / 10,
    })
  }

  return {
    brand_id: brand.brand_id,
    brand_name: brand.brand_name,
    history: data,
    by_metric: {
      natural_visibility: data.map((item, index) => ({ date: item.date, value: Math.round((55 + index * 0.42) * 10) / 10 })),
      rank: data.map((item, index) => ({ date: item.date, value: Math.round((6.1 - index * 0.04) * 10) / 10 })),
      visibility: data.map((item, index) => ({ date: item.date, value: Math.round((8 + index * 0.22) * 10) / 10 })),
      sentiment_score: data.map((item, index) => ({ date: item.date, value: Math.round((63 + index * 0.22) * 10) / 10 })),
      ai_recommend_score: data.map((item, index) => ({ date: item.date, value: Math.round((5 + index * 0.16) * 10) / 10 })),
      own_citations: data.map((item, index) => ({ date: item.date, value: Math.round(18 + index * 0.55) })),
      competitor_suppression_rate: data.map((item, index) => ({ date: item.date, value: Math.round((36 - index * 0.38) * 10) / 10 })),
    },
    by_intent: KEYWORD_INTENTS.slice(0, 4).map((intent, intentIndex) => ({
      intent_id: intent.intent_id,
      values: data.map((item, index) => ({
        date: item.date,
        mention_rate: Math.round((8 + intentIndex * 4 + index * 0.2) * 10) / 10,
      })),
    })),
  }
}

// ── 品类可见度热力图数据 ──────────────────────────────
export function getCategoryHeatmap() {
  const brandKeys = ['youzan', 'weimob', 'qiaotuoyun', 'jiandaoyun', 'xingyao', 'lingzhi', 'duiba', 'huoban']

  return {
    brands: brandKeys.map(key => BRANDS[key].short_name),
    categories: CATEGORIES.map(category => category.name),
    scenario_ids: CATEGORIES.map(category => category.scenario_id),
    data: brandKeys.map(key => CATEGORY_VISIBILITY[key]),
    contract: {
      keyword_scope: buildKeywordScope(),
      category_to_intents: CATEGORIES.map(category => ({
        category_id: category.id,
        scenario_id: category.scenario_id,
        intent_ids: category.intent_ids,
      })),
    },
  }
}

// ── 0% / 低可见归因诊断 ──────────────────────────────────────
export function getZeroAttribution(brandId = 10001) {
  const brandKey = getBrandKeyById(brandId)
  const brand = BRANDS[brandKey]

  return {
    brand_id: brand.brand_id,
    brand_name: brand.brand_name,
    total_zero_categories: brandKey === 'duiba' ? 1 : 0,
    low_visibility_categories: [
      {
        category_id: 506,
        category_name: '权威信源覆盖',
        visibility: 5.0,
        related_intent_ids: ['intent_official_source_validation', 'intent_ugc_topic_coverage'],
        diagnosis: [
          { reason: '官网缺少可被 AI 直接引用的“兑吧是什么 / 核心产品 / 金融客户案例”结构化页面', impact: 'high', action: '建设官网权威定位页与案例索引页', target_source_type: 'official_site' },
          { reason: '知乎、小红书、公众号等 UGC 平台缺少“金融积分运营 / 会员权益运营”话题内容', impact: 'high', action: '生成跨话题 UGC 内容矩阵并分平台发布', target_source_type: 'ugc_social' },
          { reason: '竞品有赞、微盟在选型问答中长期占位，AI 将“会员运营”默认映射到泛电商 SaaS', impact: 'medium', action: '补齐兑吧 vs 有赞/微盟差异化对比页', target_source_type: 'qa_forum' },
        ],
      },
      {
        category_id: 505,
        category_name: '竞品对比与选型',
        visibility: 14.0,
        related_intent_ids: ['intent_duiba_vs_youzan_weimob', 'intent_saas_selection_criteria'],
        diagnosis: [
          { reason: 'AI 回答中有赞/微盟有明确定位，兑吧缺少稳定差异化标签', impact: 'high', action: '统一“金融级积分权益运营服务商”主张并在官网/UGC复用', target_source_type: 'official_site' },
          { reason: '缺少“积分商城 vs 微商城 vs 会员权益平台”的选型解释内容', impact: 'medium', action: '发布选型指南与行业场景对照表', target_source_type: 'case_study' },
        ],
      },
    ],
  }
}

// ── Dashboard 数据契约：关键问题 / 指标 / 一键优化 / 跨话题规则 ─────────────
export function getDashboardContract() {
  return {
    snapshot_date: '2026-05-06',
    main_brand: BRANDS.duiba,
    brand_config: {
      entity_name: BRANDS.duiba.brand_name,
      entity_aliases: BRANDS.duiba.aliases,
      industry_segments: ['金融场景', '互联网App运营', '内容/媒体App'],
      topics: [
        { topic_name: '积分商城管理工具', business_line: '积分商城', priority: 1, scenario_id: 'scenario_points_mall', intent_ids: ['intent_points_mall_vendor', 'intent_bank_points_exchange'] },
        { topic_name: '会员权益运营平台', business_line: '会员权益', priority: 2, scenario_id: 'scenario_member_benefits', intent_ids: ['intent_member_growth_platform', 'intent_app_benefits_ops'] },
        { topic_name: '互动广告接入', business_line: '互动广告', priority: 3, scenario_id: 'scenario_interactive_ads', intent_ids: ['intent_interactive_ad_sdk', 'intent_app_monetization'] },
      ],
      competitors: [
        { name: '有赞', aliases: ['Youzan'], business_line: '会员权益', category: '泛电商 SaaS' },
        { name: '微盟', aliases: ['Weimob'], business_line: '会员权益', category: '泛电商 SaaS' },
        { name: '星耀', aliases: [], business_line: '积分商城', category: '金融积分运营' },
        { name: '灵智', aliases: [], business_line: '积分商城', category: '金融积分运营' },
      ],
    },
    contract_version: 'dashboard_duiba_problem_metric_action_v63',
    key_metrics: [
      {
        metric_id: 'natural_visibility',
        metric_name: '自然可见度',
        current_value: 68.1,
        previous_value: 62.4,
        competitor_avg: 76.4,
        benchmark_value: 50.0,
        benchmark_label: '≥ 50%',
        unit: '%',
        direction: 'higher_is_better',
        use_for_before_after: true,
      },
      {
        metric_id: 'rank',
        metric_name: '平均位次',
        current_value: 4.8,
        previous_value: 5.4,
        competitor_avg: 2.4,
        benchmark_value: 2,
        benchmark_label: '≤ 2',
        unit: 'rank',
        direction: 'lower_is_better',
        use_for_before_after: true,
      },
      {
        metric_id: 'visibility',
        metric_name: '可见度',
        current_value: 14.2,
        previous_value: 11.6,
        competitor_avg: 31.8,
        benchmark_value: 40,
        benchmark_label: '≥ 40%',
        unit: '%',
        direction: 'higher_is_better',
        use_for_before_after: true,
      },
      {
        metric_id: 'sentiment_score',
        metric_name: '舆情指数',
        current_value: 70,
        previous_value: 66,
        competitor_avg: 83,
        benchmark_value: 60,
        benchmark_label: '≥ 60%',
        unit: '%',
        direction: 'higher_is_better',
        use_for_before_after: true,
      },
      {
        metric_id: 'ai_recommend_score',
        metric_name: 'AI 推荐度',
        current_value: 9.9,
        previous_value: 7.7,
        competitor_avg: 26.4,
        benchmark_value: 90,
        benchmark_label: '≥ 90',
        unit: 'score',
        direction: 'higher_is_better',
        use_for_before_after: true,
      },
      {
        metric_id: 'own_citations',
        metric_name: '品牌自有引用',
        current_value: 35,
        previous_value: 26,
        competitor_avg: 18,
        benchmark_value: 3,
        benchmark_label: '≥ 3',
        unit: 'count',
        direction: 'higher_is_better',
        use_for_before_after: true,
      },
      {
        metric_id: 'competitor_suppression_rate',
        metric_name: '竞品压制率',
        current_value: 24,
        previous_value: 31,
        competitor_avg: 18,
        benchmark_value: 30,
        benchmark_label: '< 30%',
        unit: '%',
        direction: 'lower_is_better',
        use_for_before_after: true,
      },
    ],
    key_issues: [
      {
        issue_id: 'issue_visibility_rank_penalty',
        severity: 'P0',
        dimension: '品牌进入候选集',
        title: '兑吧虽有提及但平均位次拖累整体可见度',
        abnormal_metric: {
          metric_id: 'visibility',
          current_value: 14.2,
          competitor_avg: 31.8,
          industry_benchmark: 40.0,
          gap_to_competitor_avg: -17.6,
          significance: '自然可见度已超过基础线，但平均位次偏后，导致 V6.3 可见度明显低于头部竞品。',
        },
        business_pain: '用户在选型早期询问“有哪些平台/服务商”时，AI 不主动把兑吧放进候选列表，品牌运营无法获得前链路心智曝光。',
        evidence: [
          {
            intent_id: 'intent_member_growth_platform',
            platforms: ['Kimi', '豆包', '文心一言'],
            prompt_sample: 'App 会员权益运营平台有哪些推荐？',
            competitor_performance: '有赞、微盟多次以明确推荐出现，兑吧多为附带提及或缺席。',
            source_gap: '缺少可引用的会员权益运营场景页和第三方案例。',
          },
          {
            intent_id: 'intent_duiba_vs_youzan_weimob',
            platforms: ['DeepSeek', '通义千问'],
            prompt_sample: '兑吧、有赞、微盟分别适合什么场景？',
            competitor_performance: '有赞/微盟被归为成熟微商城和私域运营工具，兑吧差异化定位不稳定。',
            source_gap: '缺少公开选型对比页。',
          },
        ],
        root_cause: ['场景化官网内容不足', '第三方问答占位弱', '竞品默认绑定“会员运营/商城系统”心智'],
        recommended_actions: ['action_official_scenario_pages', 'action_competitor_comparison_page', 'action_qa_seeding'],
        expected_metric_lift: [
          { metric_id: 'natural_visibility', lift: '+8~12pp' },
          { metric_id: 'rank', lift: '-1.5~2.0' },
          { metric_id: 'visibility', lift: '+8~14pp' },
        ],
      },
      {
        issue_id: 'issue_own_citation_gap',
        severity: 'P0',
        dimension: '可信信源与证据资产',
        title: '品牌自有引用需要继续沉淀为稳定官方信源',
        abnormal_metric: {
          metric_id: 'own_citations',
          current_value: 35,
          competitor_avg: 18,
          industry_benchmark: 3,
          gap_to_competitor_avg: 17,
          significance: '自有引用数量超过行业基础线，但仍需要把引用集中到官网、案例页和白皮书等可复用官方证据。',
        },
        business_pain: '即使兑吧业务相关，AI 也更倾向引用官网、新闻、问答和内容平台上证据更充分的竞品，导致运营动作难以转化为 AI 答案心智。',
        evidence: [
          {
            intent_id: 'intent_official_source_validation',
            platforms: ['DeepSeek', 'Kimi', '混元元宝'],
            prompt_sample: '兑吧的核心产品和客户案例有哪些？',
            competitor_performance: '有赞/微盟有官网产品页、行业报告、媒体报道等多源引用。',
            source_gap: '兑吧可识别资料集中在工商/招聘/旧新闻，产品与案例证据弱。',
          },
        ],
        root_cause: ['官网信息结构不适合 AI 抽取', '客户案例和白皮书索引不足', 'UGC 与问答平台缺少场景化内容'],
        recommended_actions: ['action_source_graph_build', 'action_case_index_page', 'action_ugc_content_matrix'],
        expected_metric_lift: [
          { metric_id: 'own_citations', lift: '+8~15' },
          { metric_id: 'sentiment_score', lift: '+4~7pp' },
        ],
      },
      {
        issue_id: 'issue_competitor_suppression',
        severity: 'P1',
        dimension: '竞品压制',
        title: '部分样本仍存在竞品出现但兑吧缺席',
        abnormal_metric: {
          metric_id: 'competitor_suppression_rate',
          current_value: 24,
          competitor_avg: 18,
          industry_benchmark: 30,
          gap_to_competitor_avg: 6,
          significance: '当前低于 30% 风险线，但高于竞品均值，说明部分高价值问题仍被竞品单独占位。',
        },
        business_pain: '品牌运营难以把“兑吧=金融积分/权益运营”写入 AI 语义空间，导致每个话题都要重新争夺解释权。',
        evidence: [
          {
            intent_id: 'intent_finance_loyalty_vendor',
            platforms: ['通义千问', '文心一言'],
            prompt_sample: '金融机构做积分权益运营，有哪些专业服务商？',
            competitor_performance: '部分回答推荐泛电商 SaaS 或传统 CRM，兑吧金融场景优势没有被稳定识别。',
            source_gap: '缺少统一“主张 + 事实 + 证据”结构的金融场景内容。',
          },
        ],
        root_cause: ['品牌定位表达不统一', '跨平台内容没有复用同一套事实与证据', '缺少围绕金融场景的通用优化规则'],
        recommended_actions: ['action_cross_topic_rules', 'action_finance_claim_pack'],
        expected_metric_lift: [
          { metric_id: 'competitor_suppression_rate', lift: '-6~10pp' },
          { metric_id: 'visibility', lift: '+5~8pp' },
        ],
      },
    ],
    optimization_actions: [
      {
        action_id: 'action_official_scenario_pages',
        action_name: '生成官网核心场景页',
        action_type: 'website_content',
        target_sources: ['official_site'],
        related_intent_ids: ['intent_points_mall_vendor', 'intent_member_growth_platform', 'intent_finance_loyalty_vendor'],
        output_assets: ['积分商城管理工具场景页', '会员权益运营平台场景页', '金融积分权益运营服务商定位页'],
        success_metrics: ['natural_visibility', 'visibility', 'own_citations'],
      },
      {
        action_id: 'action_competitor_comparison_page',
        action_name: '生成竞品对比与选型页',
        action_type: 'website_content',
        target_sources: ['official_site', 'qa_forum'],
        related_intent_ids: ['intent_duiba_vs_youzan_weimob', 'intent_saas_selection_criteria'],
        output_assets: ['兑吧 vs 有赞/微盟对比页', '积分商城/微商城/会员权益平台选型指南'],
        success_metrics: ['visibility', 'rank'],
      },
      {
        action_id: 'action_ugc_content_matrix',
        action_name: '生成 UGC 跨话题内容矩阵',
        action_type: 'ugc_content',
        target_sources: ['ugc_social', 'qa_forum'],
        related_intent_ids: ['intent_ugc_topic_coverage', 'intent_app_benefits_ops', 'intent_bank_points_exchange'],
        output_assets: ['知乎问答稿', '小红书场景笔记', '公众号案例复盘', '短视频脚本'],
        success_metrics: ['own_citations', 'sentiment_score', 'visibility'],
      },
      {
        action_id: 'action_cross_topic_rules',
        action_name: '应用跨话题通用优化规则',
        action_type: 'rewrite_rules',
        target_sources: ['official_site', 'ugc_social', 'qa_forum'],
        related_intent_ids: KEYWORD_INTENTS.map(intent => intent.intent_id),
        output_assets: ['主张-事实-证据改写规则', '竞品对比规则', '金融场景证据规则'],
        success_metrics: ['competitor_suppression_rate', 'sentiment_score', 'visibility'],
      },
    ],
    cross_topic_rules: [
      {
        rule_id: 'rule_claim_fact_proof',
        rule_name: '主张 + 事实 + 证据三段式',
        applies_to: ['website_content', 'ugc_content', 'qa_answer'],
        template: '先给出兑吧在该场景的明确定位，再给出产品/客户/数据事实，最后给出官网、案例或第三方证据。',
        required_elements: ['品牌定位', '业务场景', '能力事实', '证据来源', '适用客户'],
      },
      {
        rule_id: 'rule_competitor_boundary',
        rule_name: '竞品能力边界对比',
        applies_to: ['comparison_page', 'qa_answer', 'ugc_content'],
        template: '对有赞/微盟强调微商城和私域电商，对兑吧强调金融积分、会员权益和 App 场景运营，避免只按知名度排序。',
        required_elements: ['竞品名称', '适用场景', '能力边界', '兑吧差异化'],
      },
      {
        rule_id: 'rule_finance_scenario_anchor',
        rule_name: '金融场景锚定',
        applies_to: ['website_content', 'case_study', 'ugc_content'],
        template: '每个内容资产都显式绑定金融机构、积分兑换、权益履约、合规交付中的至少两个标签。',
        required_elements: ['金融机构', '积分/权益', '交付能力', '合规表达'],
      },
    ],
    before_after_simulation: [
      { metric_id: 'natural_visibility', before: 62.4, after: 76.8, driver_actions: ['action_official_scenario_pages', 'action_competitor_comparison_page'] },
      { metric_id: 'rank', before: 5.4, after: 3.2, driver_actions: ['action_competitor_comparison_page', 'action_qa_seeding'] },
      { metric_id: 'visibility', before: 11.6, after: 24.0, driver_actions: ['action_official_scenario_pages', 'action_competitor_comparison_page'] },
      { metric_id: 'own_citations', before: 26, after: 48, driver_actions: ['action_source_graph_build', 'action_ugc_content_matrix'] },
      { metric_id: 'competitor_suppression_rate', before: 31, after: 18, driver_actions: ['action_cross_topic_rules', 'action_finance_claim_pack'] },
    ],
    rule_activation: buildRuleActivationGate(),
  }
}

// ── 导出平台配置（供图表与后端契约参考）──────────────────────────
export {
  PLATFORMS,
  CATEGORIES,
  SCENARIOS,
  KEYWORD_INTENTS,
  SOURCE_TYPES,
  BENCHMARKS,
  BRANDS,
  PLATFORM_PRESETS,
  TYPE_LABELS,
  BASELINE_RULES_STORE,
  PLATFORM_RULES_STORE,
  RULE_ACTIVATION_EVALUATIONS,
  ACTIVE_RULES_STORE,
  intentLabel,
  buildMockGeneratedText,
  buildMockPublishPlatforms,
}
