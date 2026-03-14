import { api } from "./client"
import type { IndexRequest, IndexStatusResponse } from "./types"

export const reposApi = {
  index: (projectId: string, data?: IndexRequest) => api.post<{ job_id: string }>(`/api/projects/${projectId}/index`, data ?? {}).then(r => r.data),
  getStatus: (projectId: string, jobId: string) => api.get<IndexStatusResponse>(`/api/projects/${projectId}/index/${jobId}`).then(r => r.data),
}
