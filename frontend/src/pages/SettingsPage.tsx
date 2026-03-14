import { useState } from "react"
import { useAuth } from "@/contexts/auth-context"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { RiSettings3Line, RiKeyLine } from "@remixicon/react"
import { authApi } from "@/api/auth"

export default function SettingsPage() {
  const { user, logout } = useAuth()
  const [apiKeyName, setApiKeyName] = useState("")
  const [createdKey, setCreatedKey] = useState("")
  const [creatingKey, setCreatingKey] = useState(false)

  const handleCreateKey = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreatingKey(true)
    try {
      const res = await authApi.createApiKey({ name: apiKeyName })
      setCreatedKey(res.prefix)
      setApiKeyName("")
    } catch {
      // TODO: toast error
    } finally {
      setCreatingKey(false)
    }
  }

  return (
    <div className="animate-in fade-in duration-300">
      <PageHeader title="Settings" description="Manage your account and organization" />

      <div className="max-w-2xl space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <RiSettings3Line className="h-4 w-4" />
              Profile
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Email</Label>
              <Input value={user?.email || ""} disabled />
            </div>
            <div className="space-y-2">
              <Label>Display name</Label>
              <Input value={user?.display_name || ""} disabled />
            </div>
            <div className="space-y-2">
              <Label>Role</Label>
              <Input value={user?.role || ""} disabled />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <RiKeyLine className="h-4 w-4" />
              API Keys
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <form onSubmit={handleCreateKey} className="flex gap-2">
              <Input
                value={apiKeyName}
                onChange={(e) => setApiKeyName(e.target.value)}
                placeholder="Key name (e.g. CI/CD)"
                required
                className="flex-1"
              />
              <Button type="submit" disabled={creatingKey} size="sm">
                {creatingKey ? "Creating..." : "Generate"}
              </Button>
            </form>
            {createdKey && (
              <div className="rounded-md bg-primary/5 dark:bg-primary/10 border border-primary/10 p-3">
                <p className="text-xs text-muted-foreground mb-1">Your new API key (shown once):</p>
                <code className="text-sm font-mono">{createdKey}</code>
              </div>
            )}
          </CardContent>
        </Card>

        <Separator />

        <Button variant="outline" onClick={logout} className="text-destructive hover:text-destructive">
          Log out
        </Button>
      </div>
    </div>
  )
}
