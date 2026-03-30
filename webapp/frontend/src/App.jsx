import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Shell from './components/Shell'
import Dashboard from './pages/Dashboard'
import Photoshoots from './pages/Photoshoots'
import ShootDetail from './pages/ShootDetail'
import ContentPlanning from './pages/ContentPlanning'
import PostScheduling from './pages/PostScheduling'
import AgentDetail from './pages/AgentDetail'

export default function App() {
  return (
    <BrowserRouter>
      <Shell>
        <Routes>
          <Route path="/"                        element={<Dashboard />} />
          <Route path="/photoshoots"             element={<Photoshoots />} />
          <Route path="/photoshoots/:shootId"    element={<ShootDetail />} />
          <Route path="/content-planning"        element={<ContentPlanning />} />
          <Route path="/post-scheduling"         element={<PostScheduling />} />
          <Route path="/agents/:agentId"         element={<AgentDetail />} />
          <Route path="*"                        element={<Navigate to="/" replace />} />
        </Routes>
      </Shell>
    </BrowserRouter>
  )
}
