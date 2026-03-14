-- Database schema for ticket-to-prompt metadata store
-- Multi-tenant schema with organizations, users, projects

-- Enable pgcrypto for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================
-- Multi-tenant identity tables (must precede FK references)
-- ============================================================

CREATE TABLE IF NOT EXISTS organizations (
    org_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS org_memberships (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(user_id),
    org_id UUID NOT NULL REFERENCES organizations(org_id),
    role TEXT NOT NULL DEFAULT 'member',
    joined_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, org_id)
);

-- Rename created_at -> joined_at for existing installs
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'org_memberships' AND column_name = 'created_at'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'org_memberships' AND column_name = 'joined_at'
    ) THEN
        ALTER TABLE org_memberships RENAME COLUMN created_at TO joined_at;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS teams (
    team_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(org_id),
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(org_id, name)
);

CREATE TABLE IF NOT EXISTS team_memberships (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(user_id),
    team_id UUID NOT NULL REFERENCES teams(team_id),
    role TEXT NOT NULL DEFAULT 'member',
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, team_id)
);

CREATE TABLE IF NOT EXISTS projects (
    project_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(org_id),
    team_id UUID REFERENCES teams(team_id),
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    github_repo_url TEXT NOT NULL,
    github_token_encrypted TEXT,
    jira_base_url TEXT,
    jira_email TEXT,
    jira_api_token_encrypted TEXT,
    default_branch TEXT DEFAULT 'main',
    collection_group TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(org_id, slug)
);

CREATE TABLE IF NOT EXISTS api_keys (
    key_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(org_id),
    key_hash TEXT NOT NULL,
    key_prefix TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS jira_tickets (
    id SERIAL PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organizations(org_id),
    project_id UUID NOT NULL REFERENCES projects(project_id),
    ticket_key TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    acceptance_criteria TEXT,
    status TEXT,
    priority TEXT,
    labels TEXT[],
    components TEXT[],
    epic_key TEXT,
    sprint_name TEXT,
    assignee TEXT,
    reporter TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    resolved_at TIMESTAMP,
    last_synced_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(project_id, ticket_key)
);

-- ============================================================
-- Code indexing tables (now scoped to org + project)
-- ============================================================

CREATE TABLE IF NOT EXISTS symbols (
    symbol_id TEXT PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organizations(org_id),
    project_id UUID NOT NULL REFERENCES projects(project_id),
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    repo TEXT NOT NULL,
    start_line INT,
    end_line INT
);

-- module column was added in a later migration; preserve idempotency
ALTER TABLE symbols ADD COLUMN IF NOT EXISTS module TEXT;

CREATE TABLE IF NOT EXISTS files (
    file_id SERIAL PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organizations(org_id),
    project_id UUID NOT NULL REFERENCES projects(project_id),
    file_path TEXT NOT NULL,
    repo TEXT NOT NULL,
    last_modified TIMESTAMP,
    commit_count INT DEFAULT 0,
    UNIQUE(file_path, repo)
);

CREATE TABLE IF NOT EXISTS graph_edges (
    id SERIAL PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organizations(org_id),
    project_id UUID NOT NULL REFERENCES projects(project_id),
    from_symbol TEXT NOT NULL,
    to_symbol TEXT NOT NULL,
    relation_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS git_metadata (
    id SERIAL PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organizations(org_id),
    project_id UUID NOT NULL REFERENCES projects(project_id),
    file_path TEXT NOT NULL,
    repo TEXT NOT NULL,
    last_commit_hash TEXT,
    last_commit_author TEXT,
    commit_frequency INT DEFAULT 0,
    recent_pr TEXT,
    UNIQUE(file_path, repo)
);

-- ============================================================
-- Indexes
-- ============================================================

-- organizations
CREATE INDEX IF NOT EXISTS idx_organizations_slug ON organizations(slug);

-- users
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- org_memberships
CREATE INDEX IF NOT EXISTS idx_org_memberships_org_id ON org_memberships(org_id);
CREATE INDEX IF NOT EXISTS idx_org_memberships_user_id ON org_memberships(user_id);

-- teams
CREATE INDEX IF NOT EXISTS idx_teams_org_id ON teams(org_id);

-- team_memberships
CREATE INDEX IF NOT EXISTS idx_team_memberships_team_id ON team_memberships(team_id);
CREATE INDEX IF NOT EXISTS idx_team_memberships_user_id ON team_memberships(user_id);

-- projects
CREATE INDEX IF NOT EXISTS idx_projects_org_id ON projects(org_id);
CREATE INDEX IF NOT EXISTS idx_projects_team_id ON projects(team_id);
CREATE INDEX IF NOT EXISTS idx_projects_org_slug ON projects(org_id, slug);

-- api_keys
CREATE INDEX IF NOT EXISTS idx_api_keys_org_id ON api_keys(org_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_key_prefix ON api_keys(key_prefix);

-- jira_tickets
CREATE INDEX IF NOT EXISTS idx_jira_tickets_org_id ON jira_tickets(org_id);
CREATE INDEX IF NOT EXISTS idx_jira_tickets_project_id ON jira_tickets(project_id);
CREATE INDEX IF NOT EXISTS idx_jira_tickets_ticket_key ON jira_tickets(ticket_key);
CREATE INDEX IF NOT EXISTS idx_jira_tickets_epic_key ON jira_tickets(epic_key);
CREATE INDEX IF NOT EXISTS idx_jira_tickets_status ON jira_tickets(status);
CREATE INDEX IF NOT EXISTS idx_jira_tickets_assignee ON jira_tickets(assignee);

-- symbols
CREATE INDEX IF NOT EXISTS idx_symbols_org_id ON symbols(org_id);
CREATE INDEX IF NOT EXISTS idx_symbols_project_id ON symbols(project_id);
CREATE INDEX IF NOT EXISTS idx_symbols_repo ON symbols(repo);
CREATE INDEX IF NOT EXISTS idx_symbols_file_path ON symbols(file_path);
CREATE INDEX IF NOT EXISTS idx_symbols_repo_module ON symbols(repo, module);

-- files
CREATE INDEX IF NOT EXISTS idx_files_org_id ON files(org_id);
CREATE INDEX IF NOT EXISTS idx_files_project_id ON files(project_id);
CREATE INDEX IF NOT EXISTS idx_files_repo ON files(repo);

-- graph_edges
CREATE INDEX IF NOT EXISTS idx_graph_org_id ON graph_edges(org_id);
CREATE INDEX IF NOT EXISTS idx_graph_project_id ON graph_edges(project_id);
CREATE INDEX IF NOT EXISTS idx_graph_from ON graph_edges(from_symbol);
CREATE INDEX IF NOT EXISTS idx_graph_to ON graph_edges(to_symbol);
CREATE INDEX IF NOT EXISTS idx_graph_relation ON graph_edges(relation_type);

-- git_metadata
CREATE INDEX IF NOT EXISTS idx_git_metadata_org_id ON git_metadata(org_id);
CREATE INDEX IF NOT EXISTS idx_git_metadata_project_id ON git_metadata(project_id);
CREATE INDEX IF NOT EXISTS idx_git_metadata_repo ON git_metadata(repo);
CREATE INDEX IF NOT EXISTS idx_git_metadata_file_path ON git_metadata(file_path);
