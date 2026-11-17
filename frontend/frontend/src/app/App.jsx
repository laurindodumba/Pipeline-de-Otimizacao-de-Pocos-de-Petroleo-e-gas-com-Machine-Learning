import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import AppShell from '../components/layout/AppShell.jsx'
import AboutPage from '../pages/AboutPage.jsx'
import DashboardPage from '../pages/DashboardPage.jsx'
import NotFoundPage from '../pages/NotFoundPage.jsx'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<DashboardPage />} />
          <Route path="about" element={<AboutPage />} />
          <Route path="not-found" element={<NotFoundPage />} />
          <Route path="*" element={<Navigate to="/not-found" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
