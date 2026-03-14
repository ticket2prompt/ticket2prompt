import { useEffect, useState } from "react"
import { useParams, Link } from "react-router-dom"
import { promptsApi } from "@/api/prompts"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import { RiFileCopyLine, RiCheckLine, RiArrowLeftLine } from "@remixicon/react"

export default function PromptResultPage() {
  const { projectId, ticketId } = useParams<{ projectId: string; ticketId: string }>()
  const [promptText, setPromptText] = useState("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!projectId || !ticketId) return
    promptsApi.get(projectId, ticketId)
      .then((res) => setPromptText(res.prompt_text))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load prompt"))
      .finally(() => setLoading(false))
  }, [projectId, ticketId])

  const handleCopy = async () => {
    await navigator.clipboard.writeText(promptText)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-sm text-destructive">{error}</div>
    )
  }

  return (
    <div className="animate-in fade-in duration-300">
      <div className="mb-4">
        <Link
          to={`/projects/${projectId}`}
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-primary transition-colors"
        >
          <RiArrowLeftLine className="h-4 w-4" />
          Back to project
        </Link>
      </div>

      <PageHeader
        title="Generated prompt"
        description={ticketId}
        actions={
          <Button variant="outline" size="sm" onClick={handleCopy}>
            {copied ? <RiCheckLine className="mr-1 h-4 w-4" /> : <RiFileCopyLine className="mr-1 h-4 w-4" />}
            {copied ? "Copied" : "Copy"}
          </Button>
        }
      />

      <Card className="dark:border-primary/10">
        <CardContent className="p-0">
          <ScrollArea className="h-[500px]">
            <pre className="whitespace-pre-wrap p-6 text-sm font-mono leading-relaxed">{promptText}</pre>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  )
}
