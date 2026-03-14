import { useState } from "react"
import { useParams } from "react-router-dom"
import { promptsApi } from "@/api/prompts"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { RiSearchLine, RiAlertLine, RiFileCopyLine, RiCheckLine } from "@remixicon/react"

export default function PromptLookupPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const [ticketId, setTicketId] = useState("")
  const [loading, setLoading] = useState(false)
  const [promptText, setPromptText] = useState("")
  const [error, setError] = useState("")
  const [copied, setCopied] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!projectId || !ticketId.trim()) return
    setLoading(true)
    setError("")
    setPromptText("")
    try {
      const res = await promptsApi.get(projectId, ticketId.trim())
      setPromptText(res.prompt_text)
    } catch {
      setError("No prompt found for this ticket ID")
    } finally {
      setLoading(false)
    }
  }

  const handleCopy = async () => {
    await navigator.clipboard.writeText(promptText)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="animate-in fade-in duration-300">
      <PageHeader title="Lookup prompt" description="Retrieve a previously generated prompt by ticket ID" />

      <Card className="max-w-2xl mb-6">
        <CardContent className="pt-6">
          <form onSubmit={handleSubmit} className="flex gap-3 items-end">
            <div className="flex-1 space-y-2">
              <Label htmlFor="ticket-id">Ticket ID</Label>
              <Input
                id="ticket-id"
                value={ticketId}
                onChange={(e) => setTicketId(e.target.value)}
                placeholder="Enter ticket ID"
                disabled={loading}
              />
            </div>
            <Button type="submit" disabled={loading || !ticketId.trim()}>
              <RiSearchLine className="mr-1 h-4 w-4" />
              {loading ? "Searching..." : "Lookup"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {error && (
        <Alert variant="destructive" className="max-w-2xl mb-6">
          <RiAlertLine className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {promptText && (
        <Card className="max-w-4xl dark:border-primary/10">
          <div className="flex items-center justify-between border-b px-6 py-3">
            <span className="text-sm font-medium">Result</span>
            <Button variant="ghost" size="sm" onClick={handleCopy}>
              {copied ? <RiCheckLine className="mr-1 h-3 w-3" /> : <RiFileCopyLine className="mr-1 h-3 w-3" />}
              {copied ? "Copied" : "Copy"}
            </Button>
          </div>
          <CardContent className="p-0">
            <ScrollArea className="h-[400px]">
              <pre className="whitespace-pre-wrap p-6 text-sm font-mono leading-relaxed">{promptText}</pre>
            </ScrollArea>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
