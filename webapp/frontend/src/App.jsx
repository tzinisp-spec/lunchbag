import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ToastProvider } from './lib/toast'
import ToastContainer from './components/ToastContainer'
import Shell from './components/Shell'
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

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Shell>
          <Routes>
            <Route path="/"                        element={<Dashboard />} />
            <Route path="/photoshoots"             element={<Photoshoots />} />
            <Route path="/photoshoots/:shootId"    element={<ShootDetail />} />
            <Route path="/content-planning"        element={<ContentPlanning />} />
            <Route path="/post-scheduling"         element={<PostScheduling />} />
            <Route path="/agents/:agentId"         element={<AgentDetail />} />
            <Route path="/run"                      element={<NewRun />} />
            <Route path="/content-pipeline"        element={<ContentPipeline />} />
            <Route path="/org"                     element={<Org />} />
            <Route path="/logs"                    element={<Logs />} />
            <Route path="/photoshoot-report"        element={<PhotoshootReport />} />
            <Route path="/content-plan-report"      element={<ContentPlanReport />} />
            <Route path="*"                        element={<Navigate to="/" replace />} />
          </Routes>
        </Shell>
      </BrowserRouter>
      <ToastContainer />
    </ToastProvider>
  )
}
