# 手动 Prompt 多平台 5 次调用功能计划

## 1. 目标

新增一个前端网页功能，用于手动输入 prompt，选择一个或多个模型平台，并对每个被选平台在无上下文状态下独立调用 5 次。页面最终按平台展示 5 次调用的模型回答和信源。

支持平台范围：

- GPT
- Claude
- 豆包
- DeepSeek
- Qwen

API key 允许暂时留空，页面和接口需要在 key 缺失时给出可读错误，不阻塞功能开发。

## 2. 功能边界

### V1 范围

- 用户在前端手动输入一个 prompt 文本。
- 用户通过多选控件选择平台。
- 用户点击运行后，后端对每个选中平台执行 5 次独立调用。
- 每次调用不携带历史消息、不读取品牌配置、不读取诊断上下文。
- 返回结果按平台分组，每个平台包含 5 条 invocation 结果。
- 每条 invocation 展示：
  - 调用序号
  - 状态：success / failed
  - 模型名
  - 原始回答文本
  - 信源列表
  - 错误信息，若失败
  - usage，若上游返回

### 暂不进入 V1

- 多 prompt 批量矩阵调用。
- 结果持久化到数据库。
- 用户级鉴权和配额。
- 流式输出。
- 上下文文件上传。
- 自动评分或回答质量评估。

## 3. 推荐命名

页面名称：`Prompt Lab`

路由：

```text
/prompt/lab
```

后端接口：

```text
POST /api/v1/geo/prompt-lab/runs
```

前端文件：

```text
src/pages/PromptLabPage.jsx
src/pages/PromptLabPage.css
```

后端服务文件：

```text
backend/service/prompt_lab.py
```

## 4. 接口契约

### Request

```json
{
  "prompt": "请介绍杭州兑吧网络科技有限公司的核心业务，并列出可验证来源。",
  "platforms": ["GPT", "claude", "豆包", "DeepSeek", "Qwen"],
  "rounds": 5,
  "web_search_enabled": true,
  "temperature": 0.2,
  "max_tokens": 1600
}
```

字段说明：

- `prompt`：必填，用户手动输入的 prompt。
- `platforms`：必填，至少 1 个平台。
- `rounds`：默认 5，V1 固定允许 5，后端可先保留参数但限制最大值为 5。
- `web_search_enabled`：默认 true。平台不支持信源或搜索时仍正常调用，信源返回空数组。
- `temperature`：默认 0.2。
- `max_tokens`：默认 1600。

### Response

```json
{
  "run_id": "plr_20260618_abcdef",
  "prompt": "请介绍杭州兑吧网络科技有限公司的核心业务，并列出可验证来源。",
  "rounds": 5,
  "created_at": "2026-06-18T10:00:00Z",
  "platform_results": [
    {
      "platform": "GPT",
      "configured_model": "gpt-5.5",
      "status": "completed",
      "invocations": [
        {
          "round": 1,
          "status": "success",
          "model": "gpt-5.5",
          "answer": "......",
          "citations": [
            {
              "title": "Example",
              "url": "https://example.com",
              "snippet": "..."
            }
          ],
          "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 400,
            "total_tokens": 500
          },
          "error": null
        }
      ]
    }
  ]
}
```

失败策略：

- 单次调用失败不影响同平台其他 4 次。
- 单个平台配置缺失时，该平台 5 条 invocation 都返回 failed，错误信息指出缺失的 env。
- 所有平台都失败时，接口仍返回 200，页面展示每个平台失败原因。
- 请求参数非法时返回 422。

## 5. 后端实现计划

### 5.1 平台注册

当前已有：

- `backend/service/platform_registry.py`
- `backend/service/platform_clients/openai_compatible.py`
- `backend/service/platform_clients/doubao_client.py`
- `backend/service/deepseek_client.py`

需要补充：

- 新增 `Qwen` 平台 spec。
- alias 支持：
  - `qwen`
  - `Qwen`
  - `通义千问`
  - `通义`
- 如果 Qwen 使用 DashScope OpenAI-compatible 模式，默认配置建议：

```env
QWEN_API_KEY=
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-plus
QWEN_CHAT_COMPLETIONS_ENDPOINT=/chat/completions
QWEN_WEB_SEARCH_ENABLED=false
```

API key 可留空。

### 5.2 Prompt Lab 服务

新增 `backend/service/prompt_lab.py`：

- 校验 prompt 非空。
- 校验 platforms 非空并规范化平台名。
- 限制 rounds 固定为 5 或 `1 <= rounds <= 5`。
- 通过 `create_platform_clients(platforms)` 创建客户端。
- 对每个平台执行 5 个无上下文调用。
- 调用优先复用 `OpenAICompatibleClient.invoke_task`。
- 每次调用传入：

```python
{
    "user_prompt": prompt,
    "options": {
        "web_search_enabled": web_search_enabled,
        "temperature": temperature,
        "max_tokens": max_tokens,
    },
}
```

注意：

- 不传 `system_prompt`，或仅传空字符串。
- 不传 brand_config、queryset、diagnostic run。
- 不共享 messages，保证每次调用都是独立请求。
- 使用 `asyncio.gather(..., return_exceptions=True)` 承接单次失败。
- 建议设置并发上限，例如 `PROMPT_LAB_MAX_CONCURRENCY=5`，避免一次选择 5 个平台时打出 25 个并发请求。

### 5.3 Router

在 `backend/router/geo.py` 新增：

```python
@router.post("/prompt-lab/runs")
async def post_prompt_lab_run(payload: dict) -> dict:
    ...
```

错误处理沿用现有 `_error_response` / `_log_endpoint_exception` 风格。

### 5.4 Env 示例

更新 `backend/.env.example`，保留 key 空白：

```env
PROMPT_LAB_ROUNDS=5
PROMPT_LAB_MAX_CONCURRENCY=5

GPT_API_KEY=
CLAUDE_API_KEY=
DOUBAO_API_KEY=
DEEPSEEK_API_KEY=
QWEN_API_KEY=
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-plus
```

## 6. 前端实现计划

### 6.1 API Client

在 `src/api/geo.js` 新增：

```js
export async function runPromptLab(payload, options = {}) {
  return request('/prompt-lab/runs', {
    method: 'POST',
    body: payload,
    signal: options.signal,
  })
}
```

### 6.2 页面入口

在 `src/App.jsx` 新增路由：

```jsx
<Route path="prompt/lab" element={<PromptLabPage />} />
```

在 `src/components/Layout.jsx` 新增导航：

```text
Prompt Lab
```

建议放在“工作台”分组。

### 6.3 页面交互

页面结构：

- 左侧或顶部输入区：
  - prompt textarea
  - 平台多选：GPT / Claude / 豆包 / DeepSeek / Qwen
  - web search toggle
  - temperature input 或 slider
  - max tokens input
  - 运行按钮
- 右侧或下方结果区：
  - 按平台分组。
  - 每个平台展示状态、模型名、成功次数、失败次数。
  - 每个平台下展示 5 个结果卡片。
  - 每个结果卡片包含回答、信源、usage、错误。

运行状态：

- submit 后禁用运行按钮。
- 支持 AbortController 取消当前请求。
- 接口返回前展示 loading。
- 返回后保留上一次结果，直到下一次运行成功或用户清空。

### 6.4 UI 细节

- 平台选择使用 checkbox 或 segmented multi-select。
- 每个平台结果使用 tab 或紧凑分组卡片。
- 信源用链接列表展示，字段优先级：
  - `title`
  - `url`
  - `snippet`
- 无信源时展示“未返回信源”。
- 单次失败时只在该 invocation 卡片展示错误，不把整页置为失败。

## 7. 数据和信源处理

信源来源优先复用现有客户端：

- `OpenAICompatibleClient.invoke_task` 返回 `citations`。
- OpenAI Responses API 的 annotations 可被 `_extract_citations` 解析。
- 豆包若返回 search/ref 字段，继续沿用现有抽取逻辑或在 `DoubaoClient` 中补齐。
- DeepSeek 通常不返回信源，V1 可返回空数组。
- Qwen 若采用 OpenAI-compatible chat completions，V1 先返回空数组；后续再补 DashScope citation 字段映射。

建议统一 citation schema：

```json
{
  "title": "string",
  "url": "string",
  "snippet": "string",
  "source": "api_annotation"
}
```

## 8. 测试计划

### 后端单测

新增：

```text
backend/tests/test_prompt_lab.py
```

覆盖：

- prompt 为空返回 422。
- platforms 为空返回 422。
- rounds 超过 5 返回 422。
- 平台 alias 可规范化。
- API key 缺失时返回平台级 failed invocation。
- mock client 下每个平台调用 5 次。
- 单次调用失败不影响其他 invocation。

### 前端测试

可在现有测试体系下补充：

- prompt 输入和平台选择状态。
- 点击运行会调用 `runPromptLab`。
- 成功结果按平台渲染 5 条。
- 单次失败结果能展示错误。
- Abort 后按钮恢复。

### 手工验收

- 只选 GPT，返回 GPT 下 5 条结果。
- 同时选 GPT / 豆包 / DeepSeek，返回 3 个平台分组，每组 5 条。
- 删除所有 API key，页面能展示配置缺失错误。
- DeepSeek 不返回信源时页面显示“未返回信源”。
- Qwen key 留空时该平台显示缺失配置，不影响其他平台。

## 9. 风险和决策点

- Claude 当前项目配置是 OpenAI-compatible 上游，不是 Anthropic native Messages API；V1 先沿用现状。
- Qwen 需要确认实际接入方式，推荐先走 DashScope OpenAI-compatible endpoint。
- 信源能力强依赖平台和 web search 配置，不保证所有平台都有 source。
- 一次选择 5 个平台会产生最多 25 次上游请求，需要并发上限和清晰 loading 状态。
- 若未来要做批量 prompts，需要重新设计结果矩阵：`platform -> prompt -> 5 invocations`。

## 10. 实施顺序

1. 新增 Qwen provider spec 和 `.env.example` 占位。
2. 新增 `backend/service/prompt_lab.py`。
3. 新增 `POST /api/v1/geo/prompt-lab/runs`。
4. 新增后端单测。
5. 在 `src/api/geo.js` 新增 `runPromptLab`。
6. 新增 `PromptLabPage.jsx` 和 CSS。
7. 接入 `App.jsx` 路由和 `Layout.jsx` 导航。
8. 做本地 mock 验收。
9. 在有 key 的环境做真实平台 smoke test。

## 11. V1 验收标准

- 前端能输入 prompt 并选择 GPT / Claude / 豆包 / DeepSeek / Qwen。
- 每个被选平台都会发起 5 次独立、无上下文调用。
- 页面按平台展示 5 次回答。
- 每次回答能展示信源；无信源时明确显示空态。
- API key 为空时不崩溃，返回并展示配置缺失错误。
- 单次或单平台失败不会吞掉其他平台结果。
- 代码复用现有平台客户端，不复制一套新的 HTTP 调用体系。
