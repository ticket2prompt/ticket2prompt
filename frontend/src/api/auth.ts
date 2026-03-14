import { api } from "./client"
import type { LoginRequest, RegisterRequest, TokenResponse, CurrentUser, ApiKeyCreate, ApiKeyResponse } from "./types"

export const authApi = {
  register: (data: RegisterRequest) => api.post<TokenResponse>("/api/auth/register", data).then(r => r.data),
  login: (data: LoginRequest) => api.post<TokenResponse>("/api/auth/login", data).then(r => r.data),
  getMe: () => api.get<CurrentUser>("/api/auth/me").then(r => r.data),
  createApiKey: (data: ApiKeyCreate) => api.post<ApiKeyResponse>("/api/auth/api-keys", data).then(r => r.data),
}
