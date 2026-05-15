# Report Generator SOP

## 当前接入方式

诊断报告页面已接入真实 API 任务流程：

1. 打开 `/brand/config`
2. 填写品牌配置、业务线和竞品
3. 点击“生成诊断报告”
4. 前端调用 `POST /api/v1/geo/brand-configs`
5. 前端调用 `POST /api/v1/geo/diagnostic-runs`
6. 后端调用矩阵模块 API 生成 `rule_matrix_v1` QuerySet
7. 后端对每条 query 调用配置的多平台 API，写入 inspection result
8. 后端按成功的平台结果聚合 `report_data_v1`，失败平台写入 audit
9. 页面跳转到 `/report/diagnostic?run_id=...`
10. 报告页轮询 `GET /api/v1/geo/diagnostic-runs/{run_id}`
11. 完成后读取 `GET /api/v1/geo/diagnostic-report?run_id=...`
12. 页面调用 `src/lib/reportGenerator.js` 中的 `generateReportHtml(input)` 导出独立 HTML

## 数据来源

当前报告输入只来自后端返回的 `report_data_v1`。不允许诊断报告页读取 fixture 或 mock report data。QuerySet 只来自矩阵模块 API；多平台巡检允许部分成功，成功样本参与聚合，失败平台和缺失样本必须写入 `audit`。

QuerySet 后端流程、Pydantic schema 顺序、immutable snapshot、inspection lineage、report lineage 和 quality gate 统一见 `docs/QUERYSET_MATRIX_SPEC.md`。

- API 数据集中在 `src/api/geo.js`
- 页面只消费 API 层函数
- 报告生成只调用 `src/lib/reportGenerator.js`
- 后端接口契约见 `docs/DIAGNOSTIC_API_CONTRACT.md`

## 视觉规则

有相同模块时，以报告生成器样式为准：

- 全局排名卡片
- 健康评分 gauge
- 关键问题 insight list
- 信源引用排行
- 平台健康度表格
- 业务话题表现表格
- 优化方向 strategy cards

Dashboard 只做数据编排和交互入口，不另行发明独立图表样式。

## 参考包

本次参考包：

```text
~/Downloads/geo_report_generator_duiba_goose_yellow_20260509.zip
```

包内关键文件：

```text
geo_report_generator/generate_report.py
geo_report_generator/data/report_data.json
geo_report_generator/output/duiba_geo_report_generator_goose_yellow.html
```
