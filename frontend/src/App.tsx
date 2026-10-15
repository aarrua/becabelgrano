import { BrowserRouter, Routes, Route, Navigate } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './context/AuthContext'
import { ProtectedRoute } from './components/ProtectedRoute'
import { Navbar } from './components/Navbar'
import { LoginView } from './views/LoginView'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginView />} />

            <Route
              path="/monitor"
              element={
                <ProtectedRoute>
                  <div className="app-layout">
                    <Navbar />
                    <main className="main-content">
                      <h2>Panel de Monitoreo</h2>
                    </main>
                  </div>
                </ProtectedRoute>
              }
            />

            <Route
              path="/audit"
              element={
                <ProtectedRoute requiredRole="DOCENTE">
                  <div className="app-layout">
                    <Navbar />
                    <main className="main-content">
                      <h2>Auditoría de Comandos</h2>
                    </main>
                  </div>
                </ProtectedRoute>
              }
            />

            <Route path="*" element={<Navigate to="/monitor" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}
