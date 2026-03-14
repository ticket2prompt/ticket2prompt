import { api } from "./client"
import type { PromptResult } from "./types"

export const promptsApi = {
  get: (projectId: string, ticketId: string) => api.get<PromptResult>(`/api/projects/${projectId}/prompt/${ticketId}`).then(r => r.data),
}
