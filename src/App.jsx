import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import VisibilityPage from './pages/VisibilityPage.jsx'
import BrandConfigPage from './pages/BrandConfigPage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import ContentGenerationPage from './pages/ContentGenerationPage.jsx'
import DiagnosticReportPage from './pages/DiagnosticReportPage.jsx'

export default function App() {
  return (
    <Routes>
      <Route path="/report/diagnostic" element={<DiagnosticReportPage />} />
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/brand/config" replace />} />
        <Route path="brand/config" element={<BrandConfigPage />} />
        <Route path="dashboard" element={<Navigate to="/brand/dashboard" replace />} />
        <Route path="brand/dashboard" element={<DashboardPage />} />
        <Route path="content/generate" element={<ContentGenerationPage />} />
        <Route path="monitor/visibility" element={<VisibilityPage />} />
      </Route>
    </Routes>
  )
}
