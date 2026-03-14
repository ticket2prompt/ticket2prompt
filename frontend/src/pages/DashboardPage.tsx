import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from "@/contexts/auth-context"
import { projectsApi } from "@/api/projects"
import { PageHeader } from "@/components/page-header"
import { StatCard } from "@/components/stat-card"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { RiFolder3Line, RiTeamLine, RiFileTextLine, RiAddLine } from "@remixicon/react"
import type { ProjectResponse } from "@/api/types"

export default function DashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [projects, setProjects] = useState<ProjectResponse[]>([])

  useEffect(() => {
    if (user?.org_id) {
      projectsApi.list(user.org_id).then(setProjects).catch(() => {})
    }
  }, [user?.org_id])

  return (
    <div className="animate-in fade-in duration-300">
      <PageHeader
        title={`Welcome back${user?.display_name ? `, ${user.display_name}` : ""}`}
        description="Here's an overview of your workspace"
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard icon={<RiFolder3Line className="h-5 w-5" />} label="Projects" value={projects.length} />
        <StatCard icon={<RiTeamLine className="h-5 w-5" />} label="Teams" value="—" />
        <StatCard icon={<RiFileTextLine className="h-5 w-5" />} label="Prompts generated" value="—" />
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-medium">Recent projects</CardTitle>
          </CardHeader>
          <CardContent>
            {projects.length === 0 ? (
              <p className="text-sm text-muted-foreground">No projects yet. Create your first project to get started.</p>
            ) : (
              <div className="space-y-2">
                {projects.slice(0, 5).map((p) => (
                  <button
                    key={p.project_id}
                    onClick={() => navigate(`/projects/${p.project_id}`)}
                    className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition-colors hover:bg-muted"
                  >
                    <RiFolder3Line className="h-4 w-4 text-muted-foreground" />
                    <span className="font-medium">{p.name}</span>
                    <span className="ml-auto text-xs text-muted-foreground">{p.slug}</span>
                  </button>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-medium">Quick actions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <Button variant="outline" className="w-full justify-start" onClick={() => navigate("/projects")}>
              <RiAddLine className="mr-2 h-4 w-4" />
              Create a project
            </Button>
            <Button variant="outline" className="w-full justify-start" onClick={() => navigate("/teams")}>
              <RiTeamLine className="mr-2 h-4 w-4" />
              Manage teams
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
