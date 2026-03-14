import { api } from "./client"
import type { JiraSyncResponse, JiraSyncStatusResponse } from "./types"

export const jiraSyncApi = {
  sync: (projectId: string) => api.post<JiraSyncResponse>(`/api/projects/${projectId}/jira/sync`).then(r => r.data),
  getStatus: (projectId: string, jobId: string) => api.get<JiraSyncStatusResponse>(`/api/projects/${projectId}/jira/sync/${jobId}`).then(r => r.data),
}
