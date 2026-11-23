import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { ApiError } from './api/client'
import { AuthProvider } from './context/AuthContext'
import { SyncProvider } from './context/SyncContext'
import AppRoutes from './routes/AppRoutes'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      // Don't retry permission/validation errors; do retry network glitches.
      retry: (count, err) => !(err instanceof ApiError && err.status >= 400 && err.status < 500) && count < 2,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <SyncProvider>
            <AppRoutes />
          </SyncProvider>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
