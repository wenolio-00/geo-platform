# Prompt Lab — 手动多平台 5 次调用功能计划（优化版）

> 面向同事内部测试的工具页：手动输入一个 prompt，选择 1~N 个平台，对每个平台在**无上下文**状态下独立调用 5 次，按平台分组展示回答与信源。
> 本版已对齐仓库真实代码（`platform_registry.py` / `openai_compatible.py` / `router/geo.py` / `src/api/geo.js` / `node:test`），修正了原计划中 Qwen 平台重复、响应字段不对齐、扇出成本/取消语义缺失三处问题。

## 1. 目标

新增前端页面 `Prompt Lab`：用户手动输入 prompt → 多选平台 → 每个被选平台无上下文独立调用 5 次 → 按平台展示 5 次回答和信源。

支持平台（对齐 `PLATFORM_SPECS` 真实键名 + 中文展示名）：

| 展示名 | registry 平台键 | env_prefix | client_kind |
|--------|----------------|-----------|-------------|
| GPT | `GPT` | `GPT` | openai_compatible |
| Claude | `claude` | `CLAUDE` | openai_compatible |
| 豆包 | `豆包` | `DOUBAO` | doubao |
| DeepSeek | `DeepSeek` | `DEEPSEEK` | deepseek |
| 通义千问(Qwen) | `Tongyi` | `TONGYI` | openai_compatible（DashScope） |

API key 允许留空：缺失时该平台 5 条 invocation 全部返回 `failed`，错误信息指明缺失的 env，不阻塞其他平台。

## 2. 功能边界

### V1 范围
- 手动输入一个 prompt 文本。
- 多选平台（上表 5 个）。
- 运行后，后端对每个选中平台执行 5 次**独立、无上下文**调用：不带历史消息、不读品牌配置、不读诊断上下文。
- 结果按平台分组，每组 5 条 invocation。
- 每条 invocation 展示：调用序号、状态（success/failed）、模型名、原始回答、信源列表、错误信息（失败时）、usage（上游返回时）。

### 暂不进入 V1
- 多 prompt 批量矩阵调用。
- 结果持久化到数据库（运行结果仅返回，不落盘）。
- 用户级鉴权和配额。
- 流式输出。
- 上下文/文件上传。
- 自动评分或回答质量评估。

## 3. 命名与文件

- 页面名：`Prompt Lab`
- 路由：`/prompt/lab`
- 后端接口：`POST /api/v1/geo/prompt-lab/runs`
- 前端：`src/pages/PromptLabPage.jsx`、`src/pages/PromptLabPage.css`
- 后端服务：`backend/service/prompt_lab.py`
- 测试：`backend/tests/test_prompt_lab.py`、`src/promptLab.test.js`

## 4. 接口契约

### Request

```json
{
  "prompt": "请介绍杭州兑吧网络科技有限公司的核心业务，并列出可验证来源。",
  "platforms": ["GPT", "claude", "豆包", "DeepSeek", "通义千问"],
  "rounds": 5,
  "web_search_enabled": true,
  "temperature": 0.2,
  "max_tokens": 1600
}
```

字段说明：
- `prompt`：必填，非空。
- `platforms`：必填，至少 1 个；服务端用 `platform_registry` 的 alias 规范化，无法识别的直接 422。
- `rounds`：默认 `PROMPT_LAB_ROUNDS`（=5），约束 `1 <= rounds <= 5`，超界 422。
- `web_search_enabled`：默认 true；平台不支持搜索时仍正常调用，信源返回空数组。
- `temperature`：默认 0.2。
- `max_tokens`：默认 1600。

### Response（200，即便全部失败也返回 200）

> 关键修正：`answer` 来自客户端的 `raw_text`；`citations[].snippet` 来自客户端的 `quoted_text`。见 §7 字段映射。

```json
{
  "run_id": "plr_20260618_abcdef",
  "prompt": "……",
  "rounds": 5,
  "web_search_enabled": true,
  "created_at": "2026-06-18T10:00:00Z",
  "platform_results": [
    {
      "platform": "GPT",
      "display_name": "GPT",
      "configured_model": "gpt-5.5",
      "status": "completed",
      "success_count": 4,
      "failed_count": 1,
      "invocations": [
        {
          "round": 1,
          "status": "success",
          "model": "gpt-5.5",
          "answer": "……",
          "citations": [
            { "title": "Example", "url": "https://example.com", "snippet": "……", "domain": "example.com", "source": "api_annotation" }
          ],
          "usage": { "prompt_tokens": 100, "completion_tokens": 400, "total_tokens": 500 },
          "error": null
        }
      ]
    }
  ]
}
```

失败策略：
- 单次调用失败不影响同平台其他 4 次（`asyncio.gather(..., return_exceptions=True)`）。
- 单平台配置缺失（key/base_url/model 任一为空）：该平台 5 条全部 `failed`，`error` 指出缺失 env；`platform_results[].status="failed"`。
- 所有平台都失败：接口仍 200，页面逐平台展示失败原因。
- 请求参数非法（prompt 空 / platforms 空 / rounds 越界 / 平台无法识别）：返回 422，沿用 `_error_response`。

## 5. 后端实现计划

### 5.1 平台注册（修正点①：复用 Tongyi，不新增 Qwen）

`platform_registry.py` 已有 `Tongyi` spec（`env_prefix="TONGYI"`）及 alias `tongyi/通义/通义千问`，但 `default_base_url`、`default_model`、`client_kind` 为空。改动：

```python
"Tongyi": ProviderSpec(
    platform="Tongyi",
    env_prefix="TONGYI",
    default_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    default_model="qwen-plus",
    client_kind="openai_compatible",
    capabilities={"supports_web_search": False, "task_modes": ["inspect"]},
),
```

并在 `ALIASES` 增补一行（其余 `通义/通义千问` 已存在，无需重复）：

```python
"qwen": "Tongyi",
```

> 不要新增并列的 `Qwen` 平台键——会与现有 `通义/通义千问` alias 冲突。DashScope 走 OpenAI-compatible chat completions，V1 citations 先返回空数组，后续再补 DashScope 字段映射。

### 5.2 Prompt Lab 服务（`backend/service/prompt_lab.py`）

职责：参数校验 + 规范化 + 扇出调用 + 字段映射。

```python
async def run_prompt_lab(payload: dict, *, is_disconnected=None) -> dict:
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt is required")

    raw_platforms = payload.get("platforms") or []
    platforms = [_canonical_platform(p) for p in raw_platforms]
    platforms = [p for p in dict.fromkeys(platforms) if p]   # 去重 + 去空
    if not platforms:
        raise ValueError("platforms is required and must contain a known platform")

    rounds = int(payload.get("rounds", _env_int("PROMPT_LAB_ROUNDS", 5)))
    if not (1 <= rounds <= 5):
        raise ValueError("rounds must be between 1 and 5")

    options = {
        "web_search_enabled": bool(payload.get("web_search_enabled", True)),
        "temperature": float(payload.get("temperature", 0.2)),
        "max_tokens": int(payload.get("max_tokens", 1600)),
    }
    ...
```

调用要点：
- 用 `create_platform_clients(platforms)` 建客户端（`DeepSeekClient`/`DoubaoClient` 已继承 `OpenAICompatibleClient.invoke_task`，无需新 HTTP 体系）。
- 每次调用构造 task（不传 system_prompt，保证无上下文）：

```python
task = {
    "user_prompt": prompt,
    "options": {
        "web_search_enabled": options["web_search_enabled"],
        "temperature": options["temperature"],
        "max_tokens": options["max_tokens"],
    },
}
result = await client.invoke_task(task)   # 返回 raw_text/citations/usage/model
```

- 不传 brand_config / queryset / diagnostic run；不共享 messages。
- 用 `asyncio.gather(*invocations, return_exceptions=True)` 承接单次失败。

### 5.3 扇出成本与取消（修正点③：把 25 请求工程化）

真实风险：`invoke_task` → `_post_with_retry` 对每次调用最多重试 3 次，限流退避最长约 90s/次。5 平台 × 5 次 = 25 次，最坏放大到 ~75 次上游请求、单次运行挂数分钟。须做三件事：

1. **并发闸**：用 `asyncio.Semaphore(PROMPT_LAB_MAX_CONCURRENCY)`（默认 5）包住每次 `invoke_task`，避免一次性 25 并发。

```python
sem = asyncio.Semaphore(_env_int("PROMPT_LAB_MAX_CONCURRENCY", 5))
async def _one(client, rnd):
    async with sem:
        if is_disconnected and await is_disconnected():
            raise asyncio.CancelledError()
        return await client.invoke_task(task)
```

2. **降低重试 / 整体预算**：Lab 是手动工具，重试价值低、反馈慢更糟。通过 env 把 Lab 走的平台 `*_TIMEOUT_SECONDS` 收紧（如 30s），并用 `asyncio.wait_for(gather(...), timeout=PROMPT_LAB_DEADLINE_SECONDS)`（默认 120s）给整次运行兜底；超时未完成的 invocation 记为 `failed`，`error="prompt lab deadline exceeded"`。
3. **后端断连检测**：FastAPI 不会因前端 Abort 自动停掉已发起的上游请求。在 router 拿到 `Request`，把 `request.is_disconnected` 传入服务，在每个信号量临界区开头检查；客户端断开后不再发起后续 round。

> 注意如实告知同事：前端 Abort 主要是**重置 UI 并停止接收**；后端已在途的单个上游请求要等其自身超时才真正结束，但不会再继续发起新的 round。

### 5.4 Router（`backend/router/geo.py`）

沿用现有 `_error_response` / `_log_endpoint_exception` 风格，payload 用 raw `dict`（与 `/prefill`、`/rule-activation` 一致）：

```python
@router.post("/prompt-lab/runs")
async def post_prompt_lab_run(payload: dict, request: Request) -> dict:
    endpoint = "POST /prompt-lab/runs"
    try:
        return await run_prompt_lab(payload, is_disconnected=request.is_disconnected)
    except ValueError as exc:
        return _error_response(422, str(exc), "prompt_lab_invalid_input", endpoint, "validate_input")
    except Exception:
        _log_endpoint_exception("prompt_lab_failed", endpoint, "run")
        return _error_response(500, "Prompt lab run failed.", "prompt_lab_failed", endpoint, "run")
```

（需在文件顶部 import 增补 `Request`。）

### 5.5 Env 示例（`backend/.env.example`，key 留空）

```env
PROMPT_LAB_ROUNDS=5
PROMPT_LAB_MAX_CONCURRENCY=5
PROMPT_LAB_DEADLINE_SECONDS=120

GPT_API_KEY=
CLAUDE_API_KEY=
CLAUDE_BASE_URL=
CLAUDE_MODEL=
DOUBAO_API_KEY=
DEEPSEEK_API_KEY=
TONGYI_API_KEY=
TONGYI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
TONGYI_MODEL=qwen-plus
```

> `claude` 平台 registry 默认 `base_url` 为空，必须由 `CLAUDE_BASE_URL`/`CLAUDE_MODEL` 提供，否则按"配置缺失"返回平台级 failed。

## 6. 前端实现计划

### 6.1 API Client（`src/api/geo.js`）

```js
export async function runPromptLab(payload, options = {}) {
  return request('/prompt-lab/runs', {
    method: 'POST',
    body: payload,
    signal: options.signal,
  })
}
```

`request` 已支持 `signal`（AbortController）和结构化错误，无需新增 fetch 体系。

### 6.2 路由与导航
- `src/App.jsx`：在 Layout 子路由内新增 `<Route path="prompt/lab" element={<PromptLabPage />} />`，并 `import PromptLabPage`。
- `src/components/Layout.jsx`：在"工作台"分组（`nav-section-label`）下加一个 `NavLink to="/prompt/lab"`，沿用现有 `nav-item` active 写法。

### 6.3 页面交互（`PromptLabPage.jsx`）
- 输入区：prompt textarea、平台多选（GPT/Claude/豆包/DeepSeek/通义千问 checkbox）、web search toggle、temperature、max_tokens、运行按钮。
- 运行：提交后禁用按钮 + loading；持有 `AbortController`，支持取消；返回前保留上一次结果，直到下次成功或用户清空。
- 结果区：按平台分组，每组头部显示 状态 / 模型名 / 成功数 / 失败数；组内 5 个结果卡片含 回答 / 信源 / usage / 错误。
- 校验：平台一个都没选时禁用运行；后端 422 错误用 `error.detail` 展示。

### 6.4 UI 细节
- 平台用 checkbox 多选。
- 信源链接列表，字段优先级 `title` → `url`，正文取 `snippet`（已由后端从 `quoted_text` 映射），并展示 `domain`。
- 无信源显示"未返回信源"。
- 单次失败只在该 invocation 卡片显示 `error`，不把整页置为失败。
- Abort 后按钮恢复可用，并提示"后端在途请求会在自身超时后结束"。

## 7. 数据与信源字段映射（修正点②：对齐真实返回）

`invoke_task` 实际返回：`{ platform, provider, web_search_enabled, web_search_mode, model, raw_text, usage, citations, raw_response }`。
`_extract_citations` 产出的单条 citation：`{ url, domain, title, is_official, quoted_text, answer_excerpt }`。

服务层在 `prompt_lab.py` 做一次显式映射，**不要**直接把客户端结构透传给前端：

| 响应字段 | 来源 | 说明 |
|----------|------|------|
| `answer` | `result["raw_text"]` | 原计划写 `answer`，客户端实际是 `raw_text` |
| `model` | `result["model"]` | 上游返回的真实 model |
| `usage` | `result["usage"]` | 上游有则透传，无则 `{}` |
| `citations[].title` | `c["title"]` | 可空 |
| `citations[].url` | `c["url"]` | 可空 |
| `citations[].snippet` | `c["quoted_text"]` | 原计划的 `snippet` 在客户端叫 `quoted_text` |
| `citations[].domain` | `c["domain"]` | 便于前端兜底展示 |
| `citations[].source` | 固定 `"api_annotation"` | 统一标注来源 |

各平台信源现状：GPT/Claude 走 annotations（`_parse_openai_annotation_citations`）；豆包有自定义 `_extract_citations`（search_info/ref_content）；DeepSeek 通常无信源 → 空数组；Tongyi(Qwen) V1 先空数组。前端对空数组统一显示"未返回信源"。
## 8. 测试计划（对齐真实测试体系）

### 8.1 后端单测 `backend/tests/test_prompt_lab.py`（pytest + TestClient + monkeypatch）
仿 `test_geo_router.py`：用 `monkeypatch.setattr` 把 `prompt_lab` 里创建客户端的入口替换为 mock client（其 `invoke_task` 返回固定 `raw_text`/`citations`，或按 round 抛异常）。覆盖：
- prompt 为空 → 422。
- platforms 为空 / 全是无法识别的名字 → 422。
- rounds=6 → 422；rounds=5 正常。
- alias 规范化：`qwen`/`通义千问` → `Tongyi`，`doubao`/`豆包` → `豆包`。
- key 缺失（`invoke_task` 抛 `RuntimeError("..._API_KEY is not configured...")`）→ 该平台 5 条 `failed` 且 `error` 含 env 名，接口仍 200。
- mock client 下每平台正好调用 `rounds` 次。
- 单次（某 round）抛异常 → 仅该条 `failed`，其余 success。
- 字段映射：响应里有 `answer`（=raw_text）、`citations[].snippet`（=quoted_text）。

### 8.2 前端测试 `src/promptLab.test.js`（`node:test`，仿 `apiGeo.test.js`）
> 仓库无 vitest/jest、无组件测试设施，故前端测试落在 API 层而非组件渲染：
- mock `fetch`，断言 `runPromptLab` 发出 `POST /prompt-lab/runs`、body 含 prompt+platforms、透传 `signal`。
- 后端返回 422 时 `runPromptLab` 抛出带 `detail`/`error_code` 的结构化错误（复用 `parseResponse` 路径）。

组件层（输入状态、按平台渲染 5 条、Abort 恢复）作为**手工验收**项，不写自动化组件测试（无设施）。

### 8.3 手工验收
- 只选 GPT → 返回 GPT 下 5 条。
- 选 GPT/豆包/DeepSeek → 3 组、每组 5 条。
- 清空所有 key → 每平台显示配置缺失错误，页面不崩。
- DeepSeek 无信源 → 显示"未返回信源"。
- 通义千问(Qwen) key 留空 → 该平台显示缺失配置，不影响其他平台。
- 运行中点取消 → 按钮恢复、不再发起新 round。

## 9. 风险与决策点
- Claude 当前是 OpenAI-compatible 上游（非 Anthropic native Messages API），V1 沿用现状；需配 `CLAUDE_BASE_URL`/`CLAUDE_MODEL`。
- 通义千问走 DashScope OpenAI-compatible endpoint，V1 信源先空。
- 信源能力强依赖平台与 web search，不保证都有。
- 25 次扇出 + 内置重试 = 真实成本；已用 Semaphore + deadline + 断连检测控制。
- Abort 只能停"未发起的 round"，已在途上游请求需等自身超时——已在 UI 文案说明。
- 未来做批量 prompts，需重设计结果矩阵 `platform -> prompt -> N invocations`。

## 10. 实施顺序
1. 补全 `Tongyi` spec（DashScope）+ 加 `qwen` alias；更新 `.env.example`。
2. 新增 `backend/service/prompt_lab.py`（校验 + 规范化 + Semaphore 扇出 + deadline + 字段映射）。
3. router 新增 `POST /prompt-lab/runs`（传入 `request.is_disconnected`）。
4. 后端单测 `test_prompt_lab.py`。
5. `src/api/geo.js` 新增 `runPromptLab` + `src/promptLab.test.js`。
6. `PromptLabPage.jsx` + CSS。
7. 接入 `App.jsx` 路由、`Layout.jsx` 导航。
8. 本地 mock 验收 → 有 key 环境真实平台 smoke test。

## 11. V1 验收标准
- 能输入 prompt 并选择 GPT/Claude/豆包/DeepSeek/通义千问。
- 每个被选平台发起 5 次独立、无上下文调用。
- 页面按平台展示 5 次回答；信源可见，无信源时明确空态。
- key 为空不崩，返回并展示配置缺失错误。
- 单次或单平台失败不吞掉其他平台结果。
- 复用现有平台客户端与 `request` 体系，不复制新 HTTP 调用栈。
- 25 次扇出有并发上限与整体超时；取消语义对使用者透明。

