import assert from 'node:assert/strict'
import { afterEach, describe, it } from 'node:test'
import { runPromptLab } from './api/geo.js'

const originalFetch = globalThis.fetch

afterEach(() => {
  globalThis.fetch = originalFetch
})

describe('prompt lab api client', () => {
  it('posts prompt lab runs and forwards abort signal', async () => {
    const controller = new AbortController()
    let captured
    globalThis.fetch = async (url, options) => {
      captured = { url, options }
      return new Response(JSON.stringify({ run_id: 'plr_test', platform_results: [] }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    }

    const result = await runPromptLab({
      prompt: 'hello',
      platforms: ['GPT', 'claude'],
      rounds: 5,
    }, { signal: controller.signal })

    assert.equal(result.run_id, 'plr_test')
    assert.equal(captured.url, '/api/v1/geo/prompt-lab/runs')
    assert.equal(captured.options.method, 'POST')
    assert.equal(captured.options.signal, controller.signal)
    assert.deepEqual(JSON.parse(captured.options.body), {
      prompt: 'hello',
      platforms: ['GPT', 'claude'],
      rounds: 5,
    })
  })

  it('throws structured prompt lab errors', async () => {
    globalThis.fetch = async () => new Response(JSON.stringify({
      detail: 'rounds must be between 1 and 5',
      error_code: 'prompt_lab_invalid_input',
      endpoint: 'POST /prompt-lab/runs',
      stage: 'validate_input',
    }), {
      status: 422,
      headers: { 'content-type': 'application/json' },
    })

    await assert.rejects(
      () => runPromptLab({ prompt: 'hello', platforms: ['GPT'], rounds: 6 }),
      error => {
        assert.equal(error.message, 'rounds must be between 1 and 5')
        assert.equal(error.status, 422)
        assert.equal(error.error_code, 'prompt_lab_invalid_input')
        assert.equal(error.endpoint, 'POST /prompt-lab/runs')
        assert.equal(error.stage, 'validate_input')
        return true
      },
    )
  })
})
