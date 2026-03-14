import { useEffect, useState } from "react"
import { useAuth } from "@/contexts/auth-context"
import { teamsApi } from "@/api/teams"
import { PageHeader } from "@/components/page-header"
import { EmptyState } from "@/components/empty-state"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RiAddLine, RiTeamLine } from "@remixicon/react"
import type { TeamResponse } from "@/api/types"

export default function TeamsPage() {
  const { user } = useAuth()
  const [teams, setTeams] = useState<TeamResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState("")

  const load = () => {
    if (!user?.org_id) return
    teamsApi.list(user.org_id).then(setTeams).catch(() => {}).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [user?.org_id])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!user?.org_id) return
    setCreating(true)
    try {
      await teamsApi.create(user.org_id, { name })
      setDialogOpen(false)
      setName("")
      load()
    } catch {
      // TODO: toast error
    } finally {
      setCreating(false)
    }
  }

  if (loading) {
    return <div className="space-y-4">{[1, 2].map((i) => <div key={i} className="h-20 animate-pulse rounded-lg bg-muted" />)}</div>
  }

  return (
    <div className="animate-in fade-in duration-300">
      <PageHeader
        title="Teams"
        description="Organize members into teams"
        actions={
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger render={<Button size="sm" />}>
              <RiAddLine className="mr-1 h-4 w-4" />
              New team
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create team</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleCreate} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="team-name">Team name</Label>
                  <Input id="team-name" value={name} onChange={(e) => setName(e.target.value)} required />
                </div>
                <Button type="submit" className="w-full" disabled={creating}>
                  {creating ? "Creating..." : "Create team"}
                </Button>
              </form>
            </DialogContent>
          </Dialog>
        }
      />

      {teams.length === 0 ? (
        <EmptyState
          icon={<RiTeamLine className="h-10 w-10" />}
          title="No teams yet"
          description="Create teams to organize your members and assign projects."
          action={
            <Button size="sm" onClick={() => setDialogOpen(true)}>
              <RiAddLine className="mr-1 h-4 w-4" />
              New team
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {teams.map((team) => (
            <Card key={team.team_id}>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-base">
                  <RiTeamLine className="h-4 w-4 text-muted-foreground" />
                  {team.name}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">
                  Created {new Date(team.created_at).toLocaleDateString()}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
