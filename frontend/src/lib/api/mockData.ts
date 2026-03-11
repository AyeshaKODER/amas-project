import { Agent, Task, TaskLog, MemoryEntry, SystemMetrics } from './types';

export const mockAgents: Agent[] = [
  {
    id: 'agent-1',
    name: 'Research Agent',
    type: 'research',
    status: 'running',
    description: 'Autonomous research agent that gathers information from web sources and synthesizes findings',
    capabilities: ['web_search', 'data_extraction', 'summarization', 'citation_tracking'],
    created_at: '2024-01-15T10:00:00Z',
    last_active: '2024-01-20T14:30:00Z',
    config: {
      max_sources: 10,
      search_depth: 3,
      llm_model: 'gpt-4'
    }
  },
  {
    id: 'agent-2',
    name: 'Planner Agent',
    type: 'planner',
    status: 'idle',
    description: 'Strategic planning agent that breaks down complex tasks into actionable steps',
    capabilities: ['task_decomposition', 'dependency_analysis', 'resource_allocation', 'timeline_creation'],
    created_at: '2024-01-15T10:00:00Z',
    last_active: '2024-01-20T12:15:00Z',
    config: {
      planning_depth: 2,
      llm_model: 'gpt-4'
    }
  },
  {
    id: 'agent-3',
    name: 'Executor Agent',
    type: 'executor',
    status: 'running',
    description: 'Execution agent that performs concrete actions and tool invocations',
    capabilities: ['api_calls', 'file_operations', 'code_execution', 'browser_automation'],
    created_at: '2024-01-15T10:00:00Z',
    last_active: '2024-01-20T14:45:00Z',
    config: {
      timeout: 300,
      retry_attempts: 3
    }
  },
  {
    id: 'agent-4',
    name: 'Memory Agent',
    type: 'memory',
    status: 'idle',
    description: 'Memory management agent handling storage, retrieval, and context maintenance',
    capabilities: ['embedding_generation', 'vector_search', 'context_management', 'deduplication'],
    created_at: '2024-01-16T09:00:00Z',
    last_active: '2024-01-20T11:00:00Z',
    config: {
      embedding_model: 'text-embedding-3-small',
      similarity_threshold: 0.7
    }
  }
];

export const mockTasks: Task[] = [
  {
    id: 'task-1',
    agent_id: 'agent-1',
    agent_name: 'Research Agent',
    title: 'Research latest developments in multi-agent systems',
    status: 'running',
    priority: 'high',
    created_at: '2024-01-20T14:00:00Z',
    progress: 65
  },
  {
    id: 'task-2',
    agent_id: 'agent-2',
    agent_name: 'Planner Agent',
    title: 'Create deployment plan for new agent architecture',
    status: 'completed',
    priority: 'high',
    created_at: '2024-01-20T10:00:00Z',
    completed_at: '2024-01-20T12:00:00Z',
    progress: 100,
    result: 'Successfully created 5-phase deployment plan with detailed milestones'
  },
  {
    id: 'task-3',
    agent_id: 'agent-3',
    agent_name: 'Executor Agent',
    title: 'Execute API integration tests',
    status: 'running',
    priority: 'medium',
    created_at: '2024-01-20T13:00:00Z',
    progress: 40
  },
  {
    id: 'task-4',
    agent_id: 'agent-1',
    agent_name: 'Research Agent',
    title: 'Analyze competitor agent frameworks',
    status: 'pending',
    priority: 'medium',
    created_at: '2024-01-20T14:30:00Z',
    progress: 0
  },
  {
    id: 'task-5',
    agent_id: 'agent-3',
    agent_name: 'Executor Agent',
    title: 'Data migration from legacy system',
    status: 'failed',
    priority: 'low',
    created_at: '2024-01-19T16:00:00Z',
    error: 'Connection timeout: Failed to connect to legacy database after 3 retry attempts'
  }
];

export const mockTaskLogs: Record<string, TaskLog[]> = {
  'task-1': [
    {
      id: 'log-1',
      task_id: 'task-1',
      timestamp: '2024-01-20T14:00:15Z',
      level: 'info',
      message: 'Task started: Initializing research parameters'
    },
    {
      id: 'log-2',
      task_id: 'task-1',
      timestamp: '2024-01-20T14:01:30Z',
      level: 'info',
      message: 'Web search initiated with query: "multi-agent systems 2024"'
    },
    {
      id: 'log-3',
      task_id: 'task-1',
      timestamp: '2024-01-20T14:03:45Z',
      level: 'info',
      message: 'Found 127 relevant sources, filtering by relevance score > 0.8'
    },
    {
      id: 'log-4',
      task_id: 'task-1',
      timestamp: '2024-01-20T14:05:20Z',
      level: 'debug',
      message: 'Processing source 15/45: arxiv.org/abs/2401.xxxxx',
      metadata: { source_type: 'academic', relevance: 0.92 }
    },
    {
      id: 'log-5',
      task_id: 'task-1',
      timestamp: '2024-01-20T14:08:10Z',
      level: 'warning',
      message: 'Rate limit approaching for web search API (85% utilized)'
    },
    {
      id: 'log-6',
      task_id: 'task-1',
      timestamp: '2024-01-20T14:10:00Z',
      level: 'info',
      message: 'Synthesis phase: Generating summary from 45 sources'
    }
  ]
};

export const mockMemoryEntries: MemoryEntry[] = [
  {
    id: 'mem-1',
    content: 'LangGraph is a framework for building multi-agent applications with cyclic graph structures',
    metadata: {
      source: 'documentation',
      category: 'framework',
      url: 'https://github.com/langchain-ai/langgraph'
    },
    score: 0.95,
    timestamp: '2024-01-20T10:00:00Z',
    agent_id: 'agent-1',
    tags: ['langgraph', 'framework', 'agents']
  },
  {
    id: 'mem-2',
    content: 'Qdrant vector database provides high-performance similarity search with filtering capabilities',
    metadata: {
      source: 'research',
      category: 'database'
    },
    score: 0.89,
    timestamp: '2024-01-19T15:30:00Z',
    agent_id: 'agent-4',
    tags: ['qdrant', 'vector-db', 'search']
  },
  {
    id: 'mem-3',
    content: 'FastAPI async capabilities enable handling 10,000+ concurrent requests with proper uvicorn configuration',
    metadata: {
      source: 'testing',
      category: 'performance'
    },
    score: 0.87,
    timestamp: '2024-01-19T12:00:00Z',
    agent_id: 'agent-3',
    tags: ['fastapi', 'performance', 'async']
  },
  {
    id: 'mem-4',
    content: 'Agent coordination patterns: hub-and-spoke, chain-of-responsibility, and blackboard architecture',
    metadata: {
      source: 'analysis',
      category: 'architecture'
    },
    score: 0.92,
    timestamp: '2024-01-18T14:20:00Z',
    agent_id: 'agent-2',
    tags: ['patterns', 'architecture', 'coordination']
  }
];

export const mockMetrics: SystemMetrics = {
  active_agents: 2,
  total_tasks: 47,
  pending_tasks: 3,
  completed_tasks: 38,
  memory_entries: 1247,
  avg_task_time: '4m 32s'
};