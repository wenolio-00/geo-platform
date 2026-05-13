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

async function parseResponse(res) {
  if (res.status === 204) return null

  const contentType = res.headers.get('content-type') || ''
  const payload = contentType.includes('application/json') ? await res.json() : await res.text()

  if (!res.ok) {
    const message =
      typeof payload === 'object'
        ? payload?.message || payload?.detail || payload?.error
        : payload
    throw new Error(message || `API request failed with ${res.status}`)
  }

  return payload
}

async function request(path, { method = 'GET', body, params, signal } = {}) {
  const res = await fetch(`${API_BASE}${path}${buildQuery(params)}`, {
    method,
    signal,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  return parseResponse(res)
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

export async function fetchContentGenerationContext({ brand_id }, options = {}) {
  if (!brand_id) throw new Error('brand_id is required')
  return request('/content/context', {
    params: { brand_id },
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
