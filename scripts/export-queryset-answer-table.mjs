import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = join(__dirname, '..')
const runId = process.argv[2]

if (!runId) {
  console.error('Usage: node scripts/export-queryset-answer-table.mjs <run_id>')
  process.exit(1)
}

const runs = JSON.parse(readFileSync(join(root, 'backend/storage/diagnostic_runs.json'), 'utf8'))
const inspectionResults = JSON.parse(readFileSync(join(root, 'backend/storage/inspection_results.json'), 'utf8'))
const run = runs[runId]
const inspection = inspectionResults[runId]

if (!run || !inspection) {
  console.error(`run or inspection results not found: ${runId}`)
  process.exit(1)
}

const outDir = join(root, 'public/reports')
mkdirSync(outDir, { recursive: true })

const queries = [...(run.queryset?.queries || [])].sort((a, b) => {
  const an = Number(String(a.query_id || '').match(/(\d+)$/)?.[1] || 0)
  const bn = Number(String(b.query_id || '').match(/(\d+)$/)?.[1] || 0)
  return an - bn
})

const resultsByKey = new Map()
for (const row of inspection.results || []) {
  resultsByKey.set(`${row.query_id}::${row.platform}`, row)
}

const platforms = ['GPT', '豆包']

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function csvCell(value) {
  return `"${String(value ?? '').replace(/"/g, '""')}"`
}

function answerOf(result) {
  if (!result) return ''
  if (result.status !== 'completed') return `巡检失败：${result.error_type || 'unknown'} ${result.error || ''}`.trim()
  return result.parsed?.answer || result.raw_answer || ''
}

function citationsOf(result) {
  if (!result || result.status !== 'completed') return []
  return Array.isArray(result.parsed?.citations) ? result.parsed.citations : []
}

function citationLines(citations) {
  return citations
    .filter(citation => citation?.url || citation?.domain)
    .map(citation => {
      const title = citation.title ? `${citation.title} - ` : ''
      return `${title}${citation.url || citation.domain}`
    })
}

function platformCell(result) {
  if (!result) {
    return '<td class="platform-cell missing"><span class="status failed">未采集</span></td>'
  }
  const answer = answerOf(result)
  const citations = citationsOf(result)
  const statusClass = result.status === 'completed' ? 'ok' : 'failed'
  const citationHtml = citations.length
    ? `<ol class="refs">${citations.map(citation => {
        const url = citation.url || ''
        const domain = citation.domain || ''
        const title = citation.title || url || domain || '未命名来源'
        const quote = citation.quoted_text || citation.answer_excerpt || ''
        return `<li><a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${escapeHtml(title)}</a>${domain ? `<small>${escapeHtml(domain)}</small>` : ''}${quote ? `<p>${escapeHtml(quote)}</p>` : ''}</li>`
      }).join('')}</ol>`
    : '<div class="no-ref">未抽取到 URL 引用</div>'

  return `<td class="platform-cell ${statusClass}">
    <div class="cell-head"><span class="status ${statusClass}">${escapeHtml(result.status)}</span><span>${escapeHtml(result.model || '')}</span><span>${citations.length} refs</span></div>
    <details open>
      <summary>回答</summary>
      <div class="answer">${escapeHtml(answer)}</div>
    </details>
    <details>
      <summary>引用网址</summary>
      ${citationHtml}
    </details>
  </td>`
}

const rows = queries.map((query, index) => {
  const gpt = resultsByKey.get(`${query.query_id}::GPT`)
  const doubao = resultsByKey.get(`${query.query_id}::豆包`)
  return `<tr>
    <td class="idx">${index + 1}</td>
    <td class="query">
      <div class="qid">${escapeHtml(query.query_id)}</div>
      <div class="topic">${escapeHtml(query.topic || '')}</div>
      <div class="pattern">${escapeHtml(query.query_pattern || query.intent_type || '')}</div>
      <div class="question">${escapeHtml(query.query_text || '')}</div>
    </td>
    ${platformCell(gpt)}
    ${platformCell(doubao)}
  </tr>`
}).join('\n')

const completedSummary = Object.fromEntries(platforms.map(platform => {
  const rowsForPlatform = (inspection.results || []).filter(row => row.platform === platform)
  return [platform, {
    completed: rowsForPlatform.filter(row => row.status === 'completed').length,
    failed: rowsForPlatform.filter(row => row.status === 'failed').length,
    total: rowsForPlatform.length,
  }]
}))

const html = `<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>兑吧 QuerySet 双平台巡检回答表</title>
<style>
  :root{--bg:#f6f7f9;--card:#fff;--line:#dfe5ec;--text:#172033;--muted:#687386;--blue:#1f5f99;--green:#18794e;--red:#b42318}
  *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue","PingFang SC","Noto Sans SC",sans-serif;font-size:14px;line-height:1.55}
  header{position:sticky;top:0;z-index:10;background:rgba(255,255,255,.96);border-bottom:1px solid var(--line);padding:16px 22px}
  h1{margin:0 0 8px;font-size:20px;line-height:1.25}.meta{display:flex;flex-wrap:wrap;gap:10px 18px;color:var(--muted);font-size:12px}.meta b{color:var(--text)}
  main{padding:18px 22px 48px}.table-wrap{overflow:auto;border:1px solid var(--line);background:var(--card);border-radius:8px}
  table{border-collapse:collapse;min-width:1480px;width:100%} th{position:sticky;top:73px;background:#eef3f8;z-index:5;text-align:left;color:#334155;font-size:12px;padding:10px;border-bottom:1px solid var(--line)}
  td{vertical-align:top;border-bottom:1px solid var(--line);border-right:1px solid var(--line);padding:12px} tr:last-child td{border-bottom:0}
  .idx{width:48px;text-align:center;color:var(--muted);font-weight:700}.query{width:300px}.qid{font:700 12px/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--blue);margin-bottom:7px}
  .topic,.pattern{display:inline-block;margin:0 6px 8px 0;padding:2px 7px;border-radius:4px;background:#eef3f8;color:#475569;font-size:12px}.question{font-size:15px;font-weight:700;line-height:1.45}
  .platform-cell{width:560px}.platform-cell.ok{background:#fbfffd}.platform-cell.failed,.platform-cell.missing{background:#fff8f7}
  .cell-head{display:flex;gap:8px;align-items:center;color:var(--muted);font-size:12px;margin-bottom:8px}.status{display:inline-block;padding:2px 7px;border-radius:4px;font-weight:800;font-size:11px}.status.ok{background:#e7f7ef;color:var(--green)}.status.failed{background:#fde7e4;color:var(--red)}
  details{border-top:1px solid #edf1f5;padding-top:8px;margin-top:8px} summary{cursor:pointer;font-weight:800;color:#334155;margin-bottom:6px}.answer{white-space:pre-wrap;color:#1f2937}.refs{margin:0;padding-left:22px}.refs li{margin:0 0 10px}.refs a{color:var(--blue);font-weight:700;text-decoration:none;overflow-wrap:anywhere}.refs small{display:block;color:var(--muted);font-size:12px;margin-top:2px}.refs p{margin:4px 0 0;color:#475569;font-size:13px;white-space:pre-wrap}.no-ref{color:var(--muted);font-size:13px}
</style>
</head>
<body>
<header>
  <h1>兑吧 QuerySet 双平台巡检回答表</h1>
  <div class="meta">
    <span>Run: <b>${escapeHtml(runId)}</b></span>
    <span>QuerySet: <b>${escapeHtml(run.queryset?.queryset_id || '')}</b></span>
    <span>问题数: <b>${queries.length}</b></span>
    <span>GPT: <b>${completedSummary.GPT.completed}/${completedSummary.GPT.total}</b></span>
    <span>豆包: <b>${completedSummary['豆包'].completed}/${completedSummary['豆包'].total}</b></span>
  </div>
</header>
<main>
  <div class="table-wrap">
    <table>
      <thead><tr><th>#</th><th>Query</th><th>GPT 回答 / 引用</th><th>豆包 回答 / 引用</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  </div>
</main>
</body>
</html>`

const csvRows = [
  ['index', 'query_id', 'topic', 'query_pattern', 'question', 'gpt_status', 'gpt_answer', 'gpt_urls', 'doubao_status', 'doubao_answer', 'doubao_urls'],
  ...queries.map((query, index) => {
    const gpt = resultsByKey.get(`${query.query_id}::GPT`)
    const doubao = resultsByKey.get(`${query.query_id}::豆包`)
    return [
      index + 1,
      query.query_id,
      query.topic,
      query.query_pattern,
      query.query_text,
      gpt?.status || 'missing',
      answerOf(gpt),
      citationLines(citationsOf(gpt)).join('\n'),
      doubao?.status || 'missing',
      answerOf(doubao),
      citationLines(citationsOf(doubao)).join('\n'),
    ]
  }),
]

const htmlPath = join(outDir, `duiba_queryset_answer_matrix_${runId}.html`)
const csvPath = join(outDir, `duiba_queryset_answer_matrix_${runId}.csv`)
writeFileSync(htmlPath, html, 'utf8')
writeFileSync(csvPath, csvRows.map(row => row.map(csvCell).join(',')).join('\n'), 'utf8')

console.log(JSON.stringify({
  run_id: runId,
  html: htmlPath,
  csv: csvPath,
  queries: queries.length,
  summary: completedSummary,
}, null, 2))
