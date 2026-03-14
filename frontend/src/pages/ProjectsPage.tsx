import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from "@/contexts/auth-context"
import { projectsApi } from "@/api/projects"
import { PageHeader } from "@/components/page-header"
import { EmptyState } from "@/components/empty-state"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RiAddLine, RiFolder3Line, RiGitRepositoryLine } from "@remixicon/react"
import type { ProjectCreate, ProjectResponse } from "@/api/types"

export default function ProjectsPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [projects, setProjects] = useState<ProjectResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState<ProjectCreate>({ name: "", slug: "", github_repo_url: "" })

  const load = () => {
    if (!user?.org_id) return
    projectsApi.list(user.org_id).then(setProjects).catch(() => {}).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [user?.org_id])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!user?.org_id) return
    setCreating(true)
    try {
      await projectsApi.create(user.org_id, form)
      setDialogOpen(false)
      setForm({ name: "", slug: "", github_repo_url: "" })
      load()
    } catch {
      // TODO: toast error
    } finally {
      setCreating(false)
    }
  }

  const updateForm = (field: string, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }))
    if (field === "name" && !form.slug) {
      setForm((prev) => ({ ...prev, slug: value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") }))
    }
  }

  if (loading) {
    return <div className="space-y-4">{[1, 2, 3].map((i) => <div key={i} className="h-24 animate-pulse rounded-lg bg-muted" />)}</div>
  }

  return (
    <div className="animate-in fade-in duration-300">
      <PageHeader
        title="Projects"
        description="Manage your project repositories and Jira connections"
        actions={
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger render={<Button size="sm" />}>
              <RiAddLine className="mr-1 h-4 w-4" />
              New project
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create project</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleCreate} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="name">Name</Label>
                  <Input id="name" value={form.name} onChange={(e) => updateForm("name", e.target.value)} required />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="slug">Slug</Label>
                  <Input id="slug" value={form.slug} onChange={(e) => setForm((prev) => ({ ...prev, slug: e.target.value }))} required pattern="[a-z0-9-]+" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="github_repo_url">GitHub repository URL</Label>
                  <Input id="github_repo_url" value={form.github_repo_url} onChange={(e) => updateForm("github_repo_url", e.target.value)} placeholder="https://github.com/org/repo" required />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="collection_group">Collection group (optional)</Label>
                  <Input id="collection_group" value={form.collection_group || ""} onChange={(e) => setForm((prev) => ({ ...prev, collection_group: e.target.value || undefined }))} placeholder="shared-group-slug" />
                  <p className="text-xs text-muted-foreground">Projects in the same group share a Qdrant collection</p>
                </div>
                <Button type="submit" className="w-full" disabled={creating}>
                  {creating ? "Creating..." : "Create project"}
                </Button>
              </form>
            </DialogContent>
          </Dialog>
        }
      />

      {projects.length === 0 ? (
        <EmptyState
          icon={<RiFolder3Line className="h-10 w-10" />}
          title="No projects yet"
          description="Create your first project to start generating prompts from tickets."
          action={
            <Button size="sm" onClick={() => setDialogOpen(true)}>
              <RiAddLine className="mr-1 h-4 w-4" />
              New project
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => (
            <Card
              key={project.project_id}
              className="cursor-pointer transition-colors hover:border-foreground/20"
              onClick={() => navigate(`/projects/${project.project_id}`)}
            >
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-base">
                  <RiFolder3Line className="h-4 w-4 text-muted-foreground" />
                  {project.name}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <RiGitRepositoryLine className="h-3 w-3" />
                  <span className="truncate">{project.github_repo_url}</span>
                </div>
                {project.collection_group && (
                  <Badge variant="secondary" className="mt-2 text-xs">{project.collection_group}</Badge>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
