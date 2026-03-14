import { api } from "./client"
import type { TicketSubmission, TicketResponse } from "./types"

export const ticketsApi = {
  submit: (projectId: string, data: TicketSubmission) => api.post<TicketResponse>(`/api/projects/${projectId}/ticket`, data).then(r => r.data),
}
