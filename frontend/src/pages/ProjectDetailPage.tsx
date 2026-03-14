import { useEffect, useState, useRef, useCallback } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { toast } from "sonner"
import { useAuth } from "@/contexts/auth-context"
import { projectsApi } from "@/api/projects"
import { reposApi } from "@/api/repos"
import { jiraSyncApi } from "@/api/jira-sync"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog"
import { Loader2 } from "lucide-react"
import {
  RiGitRepositoryLine,
  RiTicketLine,
  RiPlayLine,
  RiRefreshLine,
  RiFileTextLine,
  RiSettings3Line,
  RiDeleteBinLine,
} from "@remixicon/react"
import type { ProjectResponse, ProjectUpdate, IndexStatusResponse } from "@/api/types"

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [project, setProject] = useState<ProjectResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [indexStatus, setIndexStatus] = useState<IndexStatusResponse | null>(null)
  const [jobId, setJobId] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [editForm, setEditForm] = useState<ProjectUpdate>({})
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = useCallback(() => {
    if (pollingRef.current !== null) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }, [])

  const startPolling = useCallback((jid: string) => {
    stopPolling()
    pollingRef.current = setInterval(async () => {
      try {
        const s = await reposApi.getStatus(projectId!, jid)
        setIndexStatus(s)
        if (s.status === "completed" || s.status === "failed") {
          stopPolling()
          if (s.status === "completed") {
            toast.success("Indexing completed")
          } else {
            toast.error("Indexing failed: " + (s.message || "Unknown error"))
          }
        }
      } catch {
        // ignore polling errors
      }
    }, 2000)
  }, [projectId, stopPolling])

  // Clean up interval on unmount
  useEffect(() => () => stopPolling(), [])

  useEffect(() => {
    if (!user?.org_id || !projectId) return
    projectsApi.get(user.org_id, projectId)
      .then((p) => {
        setProject(p)
        setEditForm({ name: p.name, github_repo_url: p.github_repo_url, collection_group: p.collection_group })
      })
      .catch(() => navigate("/projects"))
      .finally(() => setLoading(false))
  }, [user?.org_id, projectId])

  const handleIndex = async () => {
    if (!projectId) return
    try {
      const res = await reposApi.index(projectId)
      setJobId(res.job_id ?? null)
      setIndexStatus({ status: "cloning" })
      if (res.job_id) {
        startPolling(res.job_id)
      }
    } catch {
      toast.error("Failed to start indexing")
    }
  }

  const handleJiraSync = async () => {
    if (!projectId) return
    setSyncing(true)
    try {
      await jiraSyncApi.sync(projectId)
    } catch {
      // TODO: toast error
    } finally {
      setSyncing(false)
    }
  }

  const handleSave = async () => {
    if (!user?.org_id || !projectId) return
    setSaving(true)
    try {
      const updated = await projectsApi.update(user.org_id, projectId, editForm)
      setProject(updated)
    } catch {
      // TODO: toast error
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!user?.org_id || !projectId) return
    setDeleting(true)
    try {
      await projectsApi.delete(user.org_id, projectId)
      toast.success("Project deleted")
      navigate("/projects")
    } catch {
      toast.error("Failed to delete project")
      setDeleting(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (!project) return null

  return (
    <div className="animate-in fade-in duration-300">
      <PageHeader
        title={project.name}
        description={project.slug}
        actions={
          <Button variant="outline" size="sm" onClick={() => navigate(`/projects/${projectId}/ticket`)}>
            <RiFileTextLine className="mr-1 h-4 w-4" />
            Submit ticket
          </Button>
        }
      />

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="indexing">Indexing</TabsTrigger>
          <TabsTrigger value="jira">Jira Sync</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-6 space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                  <RiGitRepositoryLine className="h-4 w-4" />
                  Repository
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm font-medium">{project.github_repo_url}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                  <RiTicketLine className="h-4 w-4" />
                  Collection
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm font-medium">
                  {project.collection_group ? (
                    <Badge variant="secondary">{project.collection_group}</Badge>
                  ) : (
                    <span className="text-muted-foreground">Standalone</span>
                  )}
                </p>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="indexing" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Repository indexing</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Index the repository to generate code embeddings for semantic search.
              </p>

              {/* Progress display */}
              {indexStatus && indexStatus.status !== "completed" && indexStatus.status !== "failed" && (
                <div className="space-y-3 rounded-lg border p-4">
                  <div className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span className="text-sm font-medium">
                      {indexStatus.status === "cloning" && "Cloning repository..."}
                      {indexStatus.status === "parsing" && `Parsing files (${indexStatus.files_parsed ?? 0}/${indexStatus.files_total ?? "?"})`}
                      {indexStatus.status === "embedding" && "Generating embeddings..."}
                      {indexStatus.status === "building_graph" && "Building code graph..."}
                      {indexStatus.status === "retrying" && `Retrying (attempt ${indexStatus.retry_count ?? "?"} of ${indexStatus.max_retries ?? 3})...`}
                      {indexStatus.status === "in_progress" && "Indexing in progress..."}
                    </span>
                  </div>
                  {indexStatus.status === "parsing" && indexStatus.files_total && indexStatus.files_total > 0 && (
                    <div className="h-2 w-full overflow-hidden rounded-full bg-secondary">
                      <div
                        className="h-full rounded-full bg-primary transition-all duration-300"
                        style={{ width: `${Math.round(((indexStatus.files_parsed ?? 0) / indexStatus.files_total) * 100)}%` }}
                      />
                    </div>
                  )}
                </div>
              )}

              {/* Completed */}
              {indexStatus?.status === "completed" && (
                <div className="rounded-lg border border-green-200 bg-green-50 p-4 dark:border-green-900 dark:bg-green-950">
                  <p className="text-sm font-medium text-green-800 dark:text-green-200">Indexing completed</p>
                  <div className="mt-2 grid grid-cols-3 gap-4 text-sm text-green-700 dark:text-green-300">
                    <div>
                      <span className="font-medium">{indexStatus.files_indexed ?? 0}</span> files
                    </div>
                    <div>
                      <span className="font-medium">{indexStatus.symbols_indexed ?? 0}</span> symbols
                    </div>
                    <div>
                      <span className="font-medium">{indexStatus.modules_detected ?? 0}</span> modules
                    </div>
                  </div>
                </div>
              )}

              {/* Failed */}
              {indexStatus?.status === "failed" && (
                <div className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-950">
                  <p className="text-sm font-medium text-red-800 dark:text-red-200">Indexing failed</p>
                  {indexStatus.message && (
                    <p className="mt-1 text-xs text-red-600 dark:text-red-400">{indexStatus.message}</p>
                  )}
                </div>
              )}

              {/* Action buttons */}
              <div className="flex gap-2">
                <Button onClick={handleIndex} disabled={!!jobId && indexStatus?.status !== "completed" && indexStatus?.status !== "failed"}>
                  <RiPlayLine className="mr-2 h-4 w-4" />
                  {indexStatus?.status === "failed" ? "Retry indexing" : jobId ? "Re-index" : "Start indexing"}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="jira" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Jira ticket sync</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Sync Jira tickets to build historical context for better prompt generation.
              </p>
              <Button onClick={handleJiraSync} disabled={syncing || !project.jira_base_url}>
                <RiRefreshLine className="mr-2 h-4 w-4" />
                {syncing ? "Syncing..." : "Sync tickets"}
              </Button>
              {!project.jira_base_url && (
                <p className="text-xs text-muted-foreground">Configure Jira credentials in Settings first.</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="settings" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <RiSettings3Line className="h-4 w-4" />
                Project settings
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Project name</Label>
                <Input value={editForm.name || ""} onChange={(e) => setEditForm((prev) => ({ ...prev, name: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>GitHub repository URL</Label>
                <Input value={editForm.github_repo_url || ""} onChange={(e) => setEditForm((prev) => ({ ...prev, github_repo_url: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Jira base URL</Label>
                <Input value={editForm.jira_base_url || ""} onChange={(e) => setEditForm((prev) => ({ ...prev, jira_base_url: e.target.value }))} placeholder="https://yourcompany.atlassian.net" />
              </div>
              <div className="space-y-2">
                <Label>Jira email</Label>
                <Input value={editForm.jira_email || ""} onChange={(e) => setEditForm((prev) => ({ ...prev, jira_email: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Jira API token</Label>
                <Input type="password" value={editForm.jira_api_token || ""} onChange={(e) => setEditForm((prev) => ({ ...prev, jira_api_token: e.target.value }))} placeholder="Enter to update" />
              </div>
              <div className="space-y-2">
                <Label>GitHub token</Label>
                <Input type="password" value={editForm.github_token || ""} onChange={(e) => setEditForm((prev) => ({ ...prev, github_token: e.target.value }))} placeholder="Enter to update" />
              </div>
              <div className="space-y-2">
                <Label>Collection group</Label>
                <Input value={editForm.collection_group || ""} onChange={(e) => setEditForm((prev) => ({ ...prev, collection_group: e.target.value || undefined }))} placeholder="shared-group-slug" />
              </div>
              <Button onClick={handleSave} disabled={saving}>
                {saving ? "Saving..." : "Save changes"}
              </Button>

              {/* Danger zone */}
              <div className="mt-8 rounded-lg border border-red-200 p-4 dark:border-red-900">
                <h3 className="text-sm font-medium text-red-800 dark:text-red-200">Danger zone</h3>
                <p className="mt-1 text-xs text-muted-foreground">
                  Permanently delete this project and all indexed data. This action cannot be undone.
                </p>
                <Button
                  variant="destructive"
                  size="sm"
                  className="mt-3"
                  onClick={() => setDeleteDialogOpen(true)}
                >
                  <RiDeleteBinLine className="mr-2 h-4 w-4" />
                  Delete project
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Delete confirmation dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete project</DialogTitle>
            <DialogDescription>
              This will permanently delete "{project.name}" and all indexed data, embeddings, and cached data. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleting}>
              {deleting ? "Deleting..." : "Delete project"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
