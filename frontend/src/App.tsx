import { BrowserRouter, Routes, Route } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const queryClient = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<div style={{ padding: '2rem' }}>Inicializando Frontend Tanques...</div>} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
