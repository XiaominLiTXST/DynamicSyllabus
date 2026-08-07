import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import './index.css'
import Instructor from './pages/Instructor'
import Student from './pages/Student'

const router = createBrowserRouter([
  { path: '/', element: <Instructor /> },
  { path: '/:slug', element: <Student /> },
])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
)
