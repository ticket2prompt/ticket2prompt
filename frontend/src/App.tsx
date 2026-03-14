import { createBrowserRouter, RouterProvider } from "react-router-dom"
import Layout from "@/components/Layout"
import { ProtectedRoute } from "@/components/protected-route"
import LoginPage from "@/pages/LoginPage"
import RegisterPage from "@/pages/RegisterPage"
import DashboardPage from "@/pages/DashboardPage"
import ProjectsPage from "@/pages/ProjectsPage"
import ProjectDetailPage from "@/pages/ProjectDetailPage"
import TicketFormPage from "@/pages/TicketFormPage"
import PromptResultPage from "@/pages/PromptResultPage"
import PromptLookupPage from "@/pages/PromptLookupPage"
import TeamsPage from "@/pages/TeamsPage"
import SettingsPage from "@/pages/SettingsPage"

const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/register", element: <RegisterPage /> },
  {
    element: (
      <ProtectedRoute>
        <Layout />
      </ProtectedRoute>
    ),
    children: [
      { path: "/", element: <DashboardPage /> },
      { path: "/projects", element: <ProjectsPage /> },
      { path: "/projects/:projectId", element: <ProjectDetailPage /> },
      { path: "/projects/:projectId/ticket", element: <TicketFormPage /> },
      { path: "/projects/:projectId/prompt/:ticketId", element: <PromptResultPage /> },
      { path: "/projects/:projectId/lookup", element: <PromptLookupPage /> },
      { path: "/teams", element: <TeamsPage /> },
      { path: "/settings", element: <SettingsPage /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
