import { useEffect, useState } from 'react'
import { Outlet, NavLink } from 'react-router-dom'
import {
  FIXED_DIAGNOSTIC_REPORT_URL,
  LATEST_DIAGNOSTIC_REPORT_KEY,
} from '../config/reportFrontend.js'
import './Layout.css'

function getLatestDiagnosticReportUrl() {
  if (typeof window === 'undefined') return FIXED_DIAGNOSTIC_REPORT_URL
  if (window.localStorage.getItem(LATEST_DIAGNOSTIC_REPORT_KEY) !== FIXED_DIAGNOSTIC_REPORT_URL) {
    window.localStorage.setItem(LATEST_DIAGNOSTIC_REPORT_KEY, FIXED_DIAGNOSTIC_REPORT_URL)
  }
  return FIXED_DIAGNOSTIC_REPORT_URL
}

export default function Layout() {
  const [diagnosticReportUrl, setDiagnosticReportUrl] = useState(getLatestDiagnosticReportUrl)

  useEffect(() => {
    const updateDiagnosticReportUrl = () => setDiagnosticReportUrl(getLatestDiagnosticReportUrl())
    window.addEventListener('storage', updateDiagnosticReportUrl)
    window.addEventListener('geo:diagnostic-report-updated', updateDiagnosticReportUrl)
    return () => {
      window.removeEventListener('storage', updateDiagnosticReportUrl)
      window.removeEventListener('geo:diagnostic-report-updated', updateDiagnosticReportUrl)
    }
  }, [])

  const hasDiagnosticReport = diagnosticReportUrl === FIXED_DIAGNOSTIC_REPORT_URL

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="sidebar-logo">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L2 7l10 5 10-5-10-5z" fill="currentColor" opacity="0.95"/>
              <path d="M2 17l10 5 10-5" stroke="currentColor" strokeWidth="2" fill="none" opacity="0.45"/>
              <path d="M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2" fill="none" opacity="0.68"/>
            </svg>
            <span>GEO Platform</span>
          </div>
          <div className="sidebar-version">v0.1 · Demo</div>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-section-label">工作台</div>
          <NavLink to="/brand/config" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/>
            </svg>
            <span>品牌配置页</span>
          </NavLink>
          <NavLink to="/brand/dashboard" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
            </svg>
            <span>Dashboard</span>
          </NavLink>
          <NavLink to="/content/generate" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <path d="M8 13h8"/><path d="M8 17h5"/>
            </svg>
            <span>内容生成</span>
          </NavLink>
          <NavLink to="/prompt/lab" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 5h16"/>
              <path d="M4 12h16"/>
              <path d="M4 19h10"/>
              <path d="m17 16 3 3"/>
              <path d="m20 16-3 3"/>
            </svg>
            <span>Prompt Lab</span>
          </NavLink>
          <NavLink to="/monitor/visibility" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
              <circle cx="12" cy="12" r="3"/>
            </svg>
            <span>AI 可见度</span>
          </NavLink>

          <div className="nav-section-label" style={{marginTop: 24}}>迭代</div>
          <NavLink to="/iteration/priority" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 5h16"/>
              <path d="M4 12h10"/>
              <path d="M4 19h7"/>
              <path d="m16 16 2 2 4-5"/>
            </svg>
            <span>迭代优先级</span>
          </NavLink>

          <div className="nav-section-label" style={{marginTop: 24}}>报告</div>
          <a href={diagnosticReportUrl} className="nav-item">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
            <span>诊断报告</span>
            <span className={`nav-badge ${hasDiagnosticReport ? 'ready' : ''}`}>{hasDiagnosticReport ? 'READY' : 'HTML'}</span>
          </a>
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-client">
            <div className="client-avatar">兑</div>
            <div>
              <div className="client-name">杭州兑吧</div>
              <div className="client-meta">Demo 客户</div>
            </div>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <Outlet />
      </main>
    </div>
  )
}
