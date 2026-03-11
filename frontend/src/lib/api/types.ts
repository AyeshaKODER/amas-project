// ---------------------------------------------------------------------------
// Domain models
// ---------------------------------------------------------------------------

export interface Agent {
  id: string;
  name: string;
  type: string;
  status: 'idle' | 'running' | 'error' | 'stopped';
  description: string;
  capabilities: string[];
  created_at: string;
  last_active?: string;
  config?: Record<string, any>;
}

export interface Task {
  id: string;
  agent_id: string;
  agent_name: string;
  title: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  priority: 'low' | 'medium' | 'high';
  created_at: string;
  completed_at?: string;
  progress?: number;
  result?: string;
  error?: string;
}

export interface TaskLog {
  id: string;
  task_id: string;
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'debug';
  message: string;
  metadata?: Record<string, any>;
}

export interface MemoryEntry {
  id: string;
  content: string;
  metadata: Record<string, any>;
  score?: number;
  timestamp: string;
  agent_id?: string;
  tags?: string[];
}

export interface SystemMetrics {
  active_agents: number;
  total_tasks: number;
  pending_tasks: number;
  completed_tasks: number;
  memory_entries: number;
  avg_task_time?: string;
}

// ---------------------------------------------------------------------------
// Auth types
// ---------------------------------------------------------------------------

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
}

export interface UserProfile {
  id: string;
  email: string;
  name: string;
  role: string;
}

// ---------------------------------------------------------------------------
// Chat types
// ---------------------------------------------------------------------------

export interface ChatRequest {
  message: string;
  session_id?: string;
}

export interface ChatResponse {
  reply: string;
  session_id: string;
}

// ---------------------------------------------------------------------------
// CRUD request types
// ---------------------------------------------------------------------------

export interface CreateAgentRequest {
  name: string;
  type: string;
  description: string;
  capabilities?: string[];
  config?: Record<string, any>;
}

export interface UpdateAgentRequest {
  name?: string;
  description?: string;
  capabilities?: string[];
  config?: Record<string, any>;
}

// ---------------------------------------------------------------------------
// Error
// ---------------------------------------------------------------------------

export interface ApiErrorResponse {
  detail: string;
}
