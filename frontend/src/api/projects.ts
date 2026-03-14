import { api } from "./client"
import type { ProjectCreate, ProjectResponse, ProjectUpdate } from "./types"

export const projectsApi = {
  create: (orgId: string, data: ProjectCreate) => api.post<ProjectResponse>(`/api/orgs/${orgId}/projects`, data).then(r => r.data),
  list: (orgId: string) => api.get<ProjectResponse[]>(`/api/orgs/${orgId}/projects`).then(r => r.data),
  get: (orgId: string, projectId: string) => api.get<ProjectResponse>(`/api/orgs/${orgId}/projects/${projectId}`).then(r => r.data),
  update: (orgId: string, projectId: string, data: ProjectUpdate) => api.put<ProjectResponse>(`/api/orgs/${orgId}/projects/${projectId}`, data).then(r => r.data),
  delete: (orgId: string, projectId: string) => api.delete(`/api/orgs/${orgId}/projects/${projectId}`),
}
