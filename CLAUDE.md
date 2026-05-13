# GEO Platform — AI 可见度监测

## 项目定位
面向中国金融机构（银行、保险）的 SaaS 产品，监测品牌在六大国内 AI 平台（DeepSeek、Kimi、豆包、通义千问、文心一言、混元元宝）回答中的可见度（Answer Share）。

## 技术架构
```
前端: React 18 + Vite + Recharts
后端: Python/FastAPI（独立项目，未包含在此仓库）
数据: 诊断报告链路使用真实 /api/v1/geo/* 后端接口；mock 数据仅作为历史契约参考
接口: 标准 JSON，前后端通过 /api/v1/geo/* 通信，诊断报告契约见 docs/DIAGNOSTIC_API_CONTRACT.md
```

## 目录结构
```
src/
├── api/geo.js          # API 调用层（真实 /api/v1/geo/* client）
├── mock/data.js        # Mock 数据（对齐后端接口规格）
├── prompts/            # Agent / evaluator Prompt 资产
├── config/             # 规则评估器等流程配置
├── schemas/            # 结构化输出 Schema
├── components/
│   ├── Layout.jsx      # 侧边栏 + 主内容区布局
│   └── Layout.css
├── pages/
│   ├── VisibilityPage.jsx  # /monitor/visibility 主页面
│   └── VisibilityPage.css
├── styles/
│   └── global.css      # 全局样式 + CSS 变量
├── App.jsx             # 路由配置
└── main.jsx            # 入口
```

## 核心路由
- `/` → 重定向到 `/monitor/visibility`
- `/monitor/visibility` → AI 可见度监测面板

## API 对接指南
所有 API 调用集中在 `src/api/geo.js`。诊断报告链路已经切换为真实 API：

```javascript
export async function fetchOverview() {
  const res = await fetch('/api/v1/geo/overview')
  return res.json()
}
```

Vite 的 proxy 配置已在 `vite.config.js` 中设好，`/api` 前缀自动转发到 `localhost:8000`。

## API 接口清单
| 接口 | 对应函数 | 说明 |
|------|---------|------|
| GET /api/v1/geo/overview | fetchOverview() | 概览指标+趋势 |
| GET /api/v1/geo/competitive-brands | fetchCompetitiveBrands() | 竞品排名表 |
| GET /api/v1/geo/brands/{id}/model-breakdown | fetchModelBreakdown() | 分模型下钻 |
| GET /api/v1/geo/brands/{id}/history | fetchBrandHistory() | 历史趋势 |
| POST /api/v1/geo/brand-configs | createBrandConfig() | 提交品牌配置 |
| POST /api/v1/geo/diagnostic-runs | startDiagnosticRun() | 启动异步诊断 |
| GET /api/v1/geo/diagnostic-runs/{id} | fetchDiagnosticRun() | 查询诊断任务 |
| GET /api/v1/geo/diagnostic-report | fetchDiagnosticReportData() | 读取 report_data_v1 |

## 数据核心概念
- **GVI (AI Visibility Index)**: 品牌在 AI 平台回答中的可见度指数
- **Answer Share**: V1 使用 binary mention rate（被提到=1，否则=0）
- **mention_context**: 三级分类 — 明确推荐 / 标准列举 / 附带提及
- **consistency**: 跨平台一致性指标（各平台可见度的离散程度）
- **Rule Activation Evaluator**: 位于 `08 Rule Extraction` 与 `13 生成 ActionTask` 之间的 08.5 闸门；自动规则必须先与 Baseline Rule 比较，通过 `effect_delta`、`utility_check`、平台拆分和风险检查后，才进入 `active_rules_store`

## 规则激活资产
- Prompt: `src/prompts/rule_activation_evaluator_prompt_zh.md`、`src/prompts/rule_activation_evaluator_prompt_en.md`
- Config: `src/config/rule_activation_evaluator.config.json`
- Schema: `src/schemas/rule_activation_evaluation.schema.json`
- Docs: `docs/rule_activation_integration_guide.md`、`docs/rule_activation_flow_patch.md`
- Mock contract: `getDashboardContract().rule_activation`

## 启动
```bash
npm install
npm run dev
# 浏览器打开 http://localhost:5173/monitor/visibility
```

## 约束
- 不删除或重命名 mock 数据文件（后端开发仍可参考历史数据结构）
- API 返回的 JSON 结构必须与 `src/schemas/report_data.schema.json` 和 `docs/DIAGNOSTIC_API_CONTRACT.md` 保持一致
- 新增页面路由统一在 App.jsx 注册
