import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { generateReportHtml } from '../src/lib/reportGenerator.js'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = join(__dirname, '..')
const runId = process.argv[2]

if (!runId) {
  console.error('Usage: node scripts/generate-report-from-run.mjs <run_id>')
  process.exit(1)
}

const runs = JSON.parse(readFileSync(join(root, 'backend/storage/diagnostic_runs.json'), 'utf8'))
const run = runs[runId]

if (!run) {
  console.error(`run_id not found: ${runId}`)
  process.exit(1)
}

if (run.status !== 'completed' || !run.report_data) {
  console.error(`run is not completed or has no report_data: ${runId} (${run.status})`)
  process.exit(1)
}

const html = generateReportHtml(run.report_data, { editable: true })
const outDir = join(root, 'public/reports')
mkdirSync(outDir, { recursive: true })
const outPath = join(outDir, `duiba_manual_question_bank_${runId}_editable.html`)
writeFileSync(outPath, html, 'utf8')

console.log(JSON.stringify({
  run_id: runId,
  report_id: run.report_data.meta?.report_id,
  output: outPath,
  total_queries: run.report_data.meta?.total_queries,
  completed_samples: run.report_data.audit?.completed_samples,
  expected_samples: run.report_data.audit?.expected_samples,
}, null, 2))
