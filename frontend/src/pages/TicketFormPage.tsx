import { useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { ticketsApi } from "@/api/tickets"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent } from "@/components/ui/card"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { RiAlertLine } from "@remixicon/react"

export default function TicketFormPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const [form, setForm] = useState({ ticket_id: "", title: "", description: "", acceptance_criteria: "" })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!projectId || !form.title.trim()) return
    setLoading(true)
    setError("")
    try {
      const res = await ticketsApi.submit(projectId, {
        ticket_id: form.ticket_id.trim() || crypto.randomUUID(),
        title: form.title.trim(),
        description: form.description.trim(),
        acceptance_criteria: form.acceptance_criteria.trim() || undefined,
      })
      navigate(`/projects/${projectId}/prompt/${res.ticket_id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit ticket")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="animate-in fade-in duration-300">
      <PageHeader title="Submit ticket" description="Enter Jira ticket details to generate a context-rich prompt" />

      <Card className="max-w-2xl">
        <CardContent className="pt-6">
          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <Alert variant="destructive">
                <RiAlertLine className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <div className="space-y-2">
              <Label htmlFor="ticket_id">Ticket ID (optional)</Label>
              <Input
                id="ticket_id"
                value={form.ticket_id}
                onChange={(e) => setForm((p) => ({ ...p, ticket_id: e.target.value }))}
                placeholder="PROJ-123 (auto-generated if empty)"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="title">Title *</Label>
              <Input
                id="title"
                value={form.title}
                onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))}
                placeholder="Add retry logic to payment service"
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                rows={4}
                value={form.description}
                onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
                placeholder="Describe the ticket in detail..."
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="acceptance_criteria">Acceptance criteria</Label>
              <Textarea
                id="acceptance_criteria"
                rows={3}
                value={form.acceptance_criteria}
                onChange={(e) => setForm((p) => ({ ...p, acceptance_criteria: e.target.value }))}
                placeholder="List the acceptance criteria..."
              />
            </div>

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Generating..." : "Generate prompt"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
