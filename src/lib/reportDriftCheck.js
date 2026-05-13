import { REPORT_COLORS, REPORT_SECTION_TITLES } from './reportDataAdapter.js'

const FORBIDDEN_MOCK_NAMES = ['有赞', '微盟', '兑吧']
const REQUIRED_CSS_TOKENS = [
  REPORT_COLORS.primary,
  REPORT_COLORS.positive,
  REPORT_COLORS.negative,
  REPORT_COLORS.neutral,
  REPORT_COLORS.gooseYellow,
]

function htmlTitleNeedle(title) {
  return title.replace(/^\d+\s/, '').replace(/&/g, '&amp;')
}

export function checkReportDrift({ displayData, html = '', inputText = '' }) {
  const issues = []
  const sectionTitles = Object.values(REPORT_SECTION_TITLES)

  sectionTitles.forEach(title => {
    if (title.startsWith('00')) return
    if (html && !html.includes(htmlTitleNeedle(title))) {
      issues.push(`missing section title: ${title}`)
    }
  })

  REQUIRED_CSS_TOKENS.forEach(token => {
    if (html && !html.includes(token)) issues.push(`missing css token: ${token}`)
  })

  if (displayData?.audit?.validation_errors?.length) {
    issues.push(...displayData.audit.validation_errors.map(error => `validation: ${error}`))
  }

  if (html) {
    FORBIDDEN_MOCK_NAMES.forEach(name => {
      if (html.includes(name) && !inputText.includes(name)) {
        issues.push(`hardcoded mock brand name detected: ${name}`)
      }
    })
  }

  return {
    ok: issues.length === 0,
    issues,
  }
}
