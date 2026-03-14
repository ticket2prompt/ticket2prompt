import { api } from "./client"
import type { OrgCreate, OrgResponse, OrgMemberAdd } from "./types"

export const orgsApi = {
  create: (data: OrgCreate) => api.post<OrgResponse>("/api/orgs", data).then(r => r.data),
  list: () => api.get<OrgResponse[]>("/api/orgs").then(r => r.data),
  get: (orgId: string) => api.get<OrgResponse>(`/api/orgs/${orgId}`).then(r => r.data),
  addMember: (orgId: string, data: OrgMemberAdd) => api.post(`/api/orgs/${orgId}/members`, data).then(r => r.data),
}
