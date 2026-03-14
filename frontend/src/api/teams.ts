import { api } from "./client"
import type { TeamCreate, TeamResponse, TeamMemberAdd } from "./types"

export const teamsApi = {
  create: (orgId: string, data: TeamCreate) => api.post<TeamResponse>(`/api/orgs/${orgId}/teams`, data).then(r => r.data),
  list: (orgId: string) => api.get<TeamResponse[]>(`/api/orgs/${orgId}/teams`).then(r => r.data),
  addMember: (orgId: string, teamId: string, data: TeamMemberAdd) => api.post(`/api/orgs/${orgId}/teams/${teamId}/members`, data).then(r => r.data),
}
