// Auth
export interface LoginRequest { email: string; password: string }
export interface RegisterRequest { email: string; password: string; display_name: string; org_name: string; org_slug: string }
export interface TokenResponse { access_token: string; token_type: string; expires_in: number }
export interface CurrentUser { user_id: string; email: string; display_name: string; org_id: string; role: string }
export interface ApiKeyCreate { name: string }
export interface ApiKeyResponse { key_id: string; name: string; prefix: string; created_at: string }

// Orgs
export interface OrgCreate { name: string; slug: string }
export interface OrgResponse { org_id: string; name: string; slug: string; created_at: string }
export interface OrgMemberAdd { user_id: string; role: string }

// Teams
export interface TeamCreate { name: string }
export interface TeamResponse { team_id: string; org_id: string; name: string; created_at: string }
export interface TeamMemberAdd { user_id: string }

// Projects
export interface ProjectCreate { name: string; slug: string; github_repo_url: string; team_id?: string; jira_base_url?: string; jira_email?: string; jira_api_token?: string; github_token?: string; collection_group?: string }
export interface ProjectResponse { project_id: string; org_id: string; name: string; slug: string; github_repo_url: string; team_id?: string; jira_base_url?: string; collection_group?: string; created_at: string; updated_at: string }
export interface ProjectUpdate { name?: string; github_repo_url?: string; jira_base_url?: string; jira_email?: string; jira_api_token?: string; github_token?: string; collection_group?: string }

// Tickets
export interface TicketSubmission { ticket_id: string; title: string; description: string; acceptance_criteria?: string }
export interface TicketResponse { ticket_id: string; status: string; message: string }

// Prompts
export interface PromptResult { ticket_id: string; prompt_text: string; metadata?: Record<string, unknown> }

// Repos
export interface IndexRequest { branch?: string }
export interface IndexStatusResponse {
  status: "cloning" | "parsing" | "embedding" | "building_graph" | "completed" | "failed" | "retrying" | "in_progress" | "unknown"
  job_id?: string
  repo_url?: string
  project_id?: string
  files_total?: number
  files_parsed?: number
  files_indexed?: number
  symbols_indexed?: number
  modules_detected?: number
  cross_module_edges?: number
  message?: string
  retry_count?: number
  max_retries?: number
}

// Jira Sync
export interface JiraSyncResponse { job_id: string; status: string }
export interface JiraSyncStatusResponse { job_id: string; status: string; tickets_synced?: number; message?: string }

// Health (preserved for health.ts)
export interface HealthResponse { status: string; version: string }
