/**
 * GEO API client
 * ─────────────────────────────────────────────────────
 * All diagnostic data now comes from the backend contract under /api/v1/geo.
 * The frontend does not fall back to fixtures or mock report data.
 */

const API_BASE = '/api/v1/geo'

function buildQuery(params = {}) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      query.set(key, String(value))
    }
  })
  const text = query.toString()
  return text ? `?${text}` : ''
}

function extractErrorPayload(payload) {
  if (!payload || typeof payload !== 'object') return {}
  if (payload.detail && typeof payload.detail === 'object' && !Array.isArray(payload.detail)) {
    return { ...payload.detail, ...payload }
  }
  return payload
}

function createApiError(res, payload) {
  const structured = extractErrorPayload(payload)
  const hasStructuredContext = Boolean(
    structured.error_code || structured.endpoint || structured.stage || structured.run_id
  )
  const detail =
    typeof structured.detail === 'string'
      ? structured.detail
      : Array.isArray(structured.detail)
        ? structured.detail.map(item => item?.msg || JSON.stringify(item)).join('；')
        : null
  const textPayload = typeof payload === 'string' ? payload.trim() : ''
  const message =
    structured.message ||
    detail ||
    structured.error ||
    textPayload ||
    (res.status >= 500 && !hasStructuredContext
      ? `Backend returned ${res.status} without structured error context.`
      : `API request failed with ${res.status}`)
  const error = new Error(message)
  error.status = res.status
  error.statusText = res.statusText
  error.payload = payload
  error.error_code = structured.error_code
  error.endpoint = structured.endpoint
  error.stage = structured.stage
  error.run_id = structured.run_id
  error.brand_config_id = structured.brand_config_id
  error.brand_id = structured.brand_id
  error.action_id = structured.action_id
  error.rule_id = structured.rule_id
  error.terminal_reason = structured.terminal_reason
  error.retriable = structured.retriable
  error.run_error = structured.run_error
  error.hasStructuredContext = hasStructuredContext
  return error
}

export async function parseResponse(res) {
  if (res.status === 204) return null

  const contentType = res.headers.get('content-type') || ''
  let payload = ''
  if (contentType.includes('application/json')) {
    try {
      payload = await res.json()
    } catch {
      payload = ''
    }
  } else {
    payload = await res.text()
  }

  if (!res.ok) {
    throw createApiError(res, payload)
  }

  return payload
}

async function request(path, { method = 'GET', body, params, signal } = {}) {
  let res
  try {
    res = await fetch(`${API_BASE}${path}${buildQuery(params)}`, {
      method,
      signal,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch (error) {
    if (error?.name === 'AbortError') throw error
    throw new Error('无法连接后端服务，请确认后端已启动且前端代理端口配置正确。')
  }
  return parseResponse(res)
}

export async function prefillBrandConfig(payload, options = {}) {
  return request('/prefill/brand-config', {
    method: 'POST',
    body: payload,
    signal: options.signal,
  })
}

export async function evaluateRuleActivation(payload, options = {}) {
  return request('/rule-activation/evaluate', {
    method: 'POST',
    body: payload,
    signal: options.signal,
  })
}

export async function runPromptLab(payload, options = {}) {
  return request('/prompt-lab/runs', {
    method: 'POST',
    body: payload,
    signal: options.signal,
  })
}

export async function fetchIterationPriorityBoard(options = {}) {
  return request('/iteration-priority-board', {
    signal: options.signal,
  })
}

export async function saveIterationPriorityBoard(payload, options = {}) {
  return request('/iteration-priority-board', {
    method: 'PUT',
    body: payload,
    signal: options.signal,
  })
}

export async function createBrandConfig(payload, options = {}) {
  return request('/brand-configs', {
    method: 'POST',
    body: payload,
    signal: options.signal,
  })
}

export async function startDiagnosticRun(payload, options = {}) {
  return request('/diagnostic-runs', {
    method: 'POST',
    body: payload,
    signal: options.signal,
  })
}

export async function fetchDiagnosticRun(runId, options = {}) {
  if (!runId) throw new Error('run_id is required')
  return request(`/diagnostic-runs/${encodeURIComponent(runId)}`, {
    signal: options.signal,
  })
}

export async function fetchDiagnosticReportData(params = {}, options = {}) {
  const runId = params.run_id || params.runId
  if (!runId) throw new Error('run_id is required')
  return request('/diagnostic-report', {
    params: { run_id: runId },
    signal: options.signal,
  })
}

export async function fetchOverview(params = {}, options = {}) {
  return request('/overview', { params, signal: options.signal })
}

export async function fetchCompetitiveBrands(params = {}, options = {}) {
  return request('/competitive-brands', { params, signal: options.signal })
}

export async function fetchModelBreakdown(brandId, options = {}) {
  if (!brandId) throw new Error('brand_id is required')
  return request(`/brands/${encodeURIComponent(brandId)}/model-breakdown`, {
    signal: options.signal,
  })
}

export async function fetchBrandHistory(brandId, days = 30, options = {}) {
  if (!brandId) throw new Error('brand_id is required')
  return request(`/brands/${encodeURIComponent(brandId)}/history`, {
    params: { days },
    signal: options.signal,
  })
}

export async function fetchCategoryHeatmap(params = {}, options = {}) {
  return request('/category-heatmap', { params, signal: options.signal })
}

export async function fetchZeroAttribution(brandId, options = {}) {
  if (!brandId) throw new Error('brand_id is required')
  return request(`/brands/${encodeURIComponent(brandId)}/zero-attribution`, {
    signal: options.signal,
  })
}

export async function fetchDashboardContract(params = {}, options = {}) {
  return request('/dashboard-contract', { params, signal: options.signal })
}

export async function fetchContentGenerationContext(params = {}, options = {}) {
  const brandId = params.brand_id || params.brandId
  const brandConfigId = params.brand_config_id || params.brandConfigId
  return request('/content/context', {
    params: {
      brand_id: brandId,
      brand_config_id: brandConfigId,
      action_id: params.action_id || params.actionId,
      rule_id: params.rule_id || params.ruleId,
    },
    signal: options.signal,
  })
}

export async function generateOptimizedDraft(payload, options = {}) {
  return request('/content/generate', {
    method: 'POST',
    body: payload,
    signal: options.signal,
  })
}

export async function saveContentVersionEdit(contentVersionId, payload, options = {}) {
  if (!contentVersionId) throw new Error('content_version_id is required')
  return request(`/content/versions/${encodeURIComponent(contentVersionId)}/edits`, {
    method: 'POST',
    body: payload,
    signal: options.signal,
  })
}

export async function submitContentFeedback(contentVersionId, payload, options = {}) {
  if (!contentVersionId) throw new Error('content_version_id is required')
  return request(`/content/versions/${encodeURIComponent(contentVersionId)}/feedback`, {
    method: 'POST',
    body: payload,
    signal: options.signal,
  })
}

export async function computeContentEffectAttribution(contentVersionId, payload = {}, options = {}) {
  if (!contentVersionId) throw new Error('content_version_id is required')
  return request(`/content/versions/${encodeURIComponent(contentVersionId)}/effect-attribution`, {
    method: 'POST',
    body: payload,
    signal: options.signal,
  })
}
