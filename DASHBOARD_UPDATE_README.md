# GEO Platform Dashboard 更新说明

本次 Dashboard 已对齐报告生成器的模块结构与卡片/表格表现形式，并在页面内接入 HTML 报告生成。

## 路由

- `/brand/config`：品牌配置页
- `/dashboard`：Dashboard + 报告预览入口
- `/brand/dashboard`：Dashboard 兼容路径
- `/monitor/visibility`：原 AI 可见度页保留

## Dashboard 与报告的关系

Dashboard 现在按报告的顺序展示：

1. Hero
2. 全局指标 / gauge
3. 关键问题
4. 信源引用情况
5. 六平台健康度
6. 业务话题表现
7. 优化方向
8. 优化前后模拟

页面上的“生成 HTML 报告”按钮会调用 `src/lib/reportGenerator.js`，把当前 Dashboard 数据导出为独立 HTML 报告。

## 运行方式

```bash
npm install
npm run dev
```

打开：

```text
http://localhost:5173/dashboard
```

## 主要改动文件

- `src/App.jsx`
- `src/components/Layout.jsx`
- `src/lib/reportGenerator.js`
- `src/pages/DashboardPage.jsx`
- `src/pages/DashboardPage.css`
- `src/styles/global.css`
