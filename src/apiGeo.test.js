import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { parseResponse } from './api/geo.js'

describe('geo api parseResponse', () => {
  it('throws structured backend error context', async () => {
    const response = new Response(JSON.stringify({
      detail: 'diagnostic report is not ready: aggregating',
      error_code: 'diagnostic_report_not_ready',
      endpoint: 'GET /diagnostic-report',
      stage: 'check_status',
      run_id: 'run_test',
    }), {
      status: 409,
      headers: { 'content-type': 'application/json' },
    })

    await assert.rejects(
      () => parseResponse(response),
      error => {
        assert.equal(error.message, 'diagnostic report is not ready: aggregating')
        assert.equal(error.status, 409)
        assert.equal(error.error_code, 'diagnostic_report_not_ready')
        assert.equal(error.endpoint, 'GET /diagnostic-report')
        assert.equal(error.stage, 'check_status')
        assert.equal(error.run_id, 'run_test')
        return true
      },
    )
  })

  it('uses transport message for empty 500 bodies', async () => {
    const response = new Response('', { status: 500 })

    await assert.rejects(
      () => parseResponse(response),
      error => {
        assert.equal(error.message, 'Backend returned 500 without structured error context.')
        assert.equal(error.status, 500)
        assert.equal(error.hasStructuredContext, false)
        return true
      },
    )
  })
})
