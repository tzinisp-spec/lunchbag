import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ToastProvider } from './lib/toast'
import { AuthProvider, useAuth } from './lib/auth'
import ToastContainer from './components/ToastContainer'
import Shell from './components/Shell'
import LoginPage from './pages/LoginPage'
import Dashboard from './pages/Dashboard'
import Photoshoots from './pages/Photoshoots'
import ShootDetail from './pages/ShootDetail'
import ContentPlanning from './pages/ContentPlanning'
import PostScheduling from './pages/PostScheduling'
import AgentDetail from './pages/AgentDetail'
import Org from './pages/Org'
import Logs from './pages/Logs'
import PhotoshootReport from './pages/PhotoshootReport'
import ContentPlanReport from './pages/ContentPlanReport'
import NewRun from './pages/NewRun'
import ContentPipeline from './pages/ContentPipeline'

// Routes only admin can access
const ADMIN_ROUTES = ['/', '/run', '/content-pipeline', '/logs', '/org', '/photoshoot-report', '/content-plan-report']

function ProtectedRoute({ element, adminOnly = false }) {
  const { auth } = useAuth()
  if (!auth) return null  // still loading
  if (!auth.user) return <Navigate to="/login" replace />
  if (adminOnly && auth.role !== 'admin') return <Navigate to="/photoshoots" replace />
  return element
}

function AppRoutes() {
  const { auth } = useAuth()

  // While session is loading, render nothing
  if (!auth) return null

  // Not logged in — show login page for all routes
  if (!auth.user) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*"      element={<Navigate to="/login" replace />} />
      </Routes>
    )
  }

  const isAdmin = auth.role === 'admin'

  return (
    <Shell>
      <Routes>
        {/* Admin only */}
        <Route path="/"                     element={<ProtectedRoute element={<Dashboard />}         adminOnly />} />
        <Route path="/run"                  element={<ProtectedRoute element={<NewRun />}             adminOnly />} />
        <Route path="/content-pipeline"     element={<ProtectedRoute element={<ContentPipeline />}   adminOnly />} />
        <Route path="/agents/:agentId"      element={<ProtectedRoute element={<AgentDetail />}       adminOnly />} />
        <Route path="/org"                  element={<ProtectedRoute element={<Org />}               adminOnly />} />
        <Route path="/logs"                 element={<ProtectedRoute element={<Logs />}              adminOnly />} />
        <Route path="/photoshoot-report"    element={<ProtectedRoute element={<PhotoshootReport />}  adminOnly />} />
        <Route path="/content-plan-report"  element={<ProtectedRoute element={<ContentPlanReport />} adminOnly />} />

        {/* All authenticated users */}
        <Route path="/photoshoots"          element={<Photoshoots />} />
        <Route path="/photoshoots/:shootId" element={<ShootDetail />} />
        <Route path="/content-planning"     element={<ContentPlanning />} />
        <Route path="/post-scheduling"      element={<PostScheduling />} />

        {/* Default redirect based on role */}
        <Route path="*" element={<Navigate to={isAdmin ? '/' : '/photoshoots'} replace />} />
      </Routes>
    </Shell>
  )
}

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </BrowserRouter>
      <ToastContainer />
    </ToastProvider>
  )
}
