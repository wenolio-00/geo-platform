import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import VisibilityPage from './pages/VisibilityPage.jsx'
import BrandConfigPage from './pages/BrandConfigPage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import ContentGenerationPage from './pages/ContentGenerationPage.jsx'
import IterationPriorityPage from './pages/IterationPriorityPage.jsx'
import PromptLabPage from './pages/PromptLabPage.jsx'
import { FIXED_DIAGNOSTIC_REPORT_URL } from './config/reportFrontend.js'

function FixedDiagnosticReportRedirect() {
  useEffect(() => {
    window.location.replace(FIXED_DIAGNOSTIC_REPORT_URL)
  }, [])

  return (
    <main style={{ padding: 24, fontFamily: 'system-ui, sans-serif' }}>
      正在打开已确认的中意报告前端...
    </main>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/report/diagnostic" element={<FixedDiagnosticReportRedirect />} />
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/brand/config" replace />} />
        <Route path="brand/config" element={<BrandConfigPage />} />
        <Route path="dashboard" element={<Navigate to="/brand/dashboard" replace />} />
        <Route path="brand/dashboard" element={<DashboardPage />} />
        <Route path="content/generate" element={<ContentGenerationPage />} />
        <Route path="prompt/lab" element={<PromptLabPage />} />
        <Route path="monitor/visibility" element={<VisibilityPage />} />
        <Route path="iteration/priority" element={<IterationPriorityPage />} />
      </Route>
    </Routes>
  )
}
