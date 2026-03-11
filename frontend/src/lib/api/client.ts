import { Agent, Task, TaskLog, MemoryEntry, SystemMetrics } from './types';
import { mockAgents, mockTasks, mockTaskLogs, mockMemoryEntries, mockMetrics } from './mockData';

// --- Replace existing API_CONFIG block with this ---

// Read config from Vite env (create .env with the keys below)
const DEFAULT_API_HOST = 'http://localhost:8000';
const envApi =
  typeof import.meta !== 'undefined' &&
  import.meta.env &&
  import.meta.env.VITE_API_URL
    ? String(import.meta.env.VITE_API_URL)
    : DEFAULT_API_HOST;

const API_CONFIG = {
  // Toggle mock data using env: VITE_USE_MOCK_DATA (set to "false" to use real backend)
  useMockData:
    typeof import.meta !== 'undefined' &&
    import.meta.env &&
    typeof import.meta.env.VITE_USE_MOCK_DATA !== 'undefined'
      ? String(import.meta.env.VITE_USE_MOCK_DATA).toLowerCase() === 'true'
      : true,

  // Base URL for backend API; default to http://localhost:8000
  baseURL: envApi.endsWith('/') ? envApi.slice(0, -1) : envApi
};

// Storage key for configuration
const CONFIG_KEY = 'amas_api_config';

// Load config from localStorage
export const loadApiConfig = () => {
  const stored = localStorage.getItem(CONFIG_KEY);
  if (stored) {
    const config = JSON.parse(stored);
    API_CONFIG.useMockData = config.useMockData ?? true;
    API_CONFIG.baseURL = config.baseURL || 'http://localhost:8000/api/v1';
  }
  return API_CONFIG;
};

// Save config to localStorage
export const saveApiConfig = (useMock: boolean, baseURL?: string) => {
  API_CONFIG.useMockData = useMock;
  if (baseURL) API_CONFIG.baseURL = baseURL;
  localStorage.setItem(CONFIG_KEY, JSON.stringify(API_CONFIG));
};

// Initialize on load
loadApiConfig();

// Helper to simulate API delay
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

// Real API client
const realApi = {
  get: async (endpoint: string) => {
    const response = await fetch(`${API_CONFIG.baseURL}${endpoint}`, {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('auth_token')}` }
    });
    if (!response.ok) throw new Error(`API Error: ${response.statusText}`);
    return response.json();
  },
  
  post: async (endpoint: string, data: any) => {
    const response = await fetch(`${API_CONFIG.baseURL}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
      },
      body: JSON.stringify(data)
    });
    if (!response.ok) throw new Error(`API Error: ${response.statusText}`);
    return response.json();
  },
  
  put: async (endpoint: string, data: any) => {
    const response = await fetch(`${API_CONFIG.baseURL}${endpoint}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
      },
      body: JSON.stringify(data)
    });
    if (!response.ok) throw new Error(`API Error: ${response.statusText}`);
    return response.json();
  },
  
  delete: async (endpoint: string) => {
    const response = await fetch(`${API_CONFIG.baseURL}${endpoint}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${localStorage.getItem('auth_token')}` }
    });
    if (!response.ok) throw new Error(`API Error: ${response.statusText}`);
    return response.json();
  }
};

// API Client with mock/real toggle
export const apiClient = {
  // System
  getMetrics: async (): Promise<SystemMetrics> => {
    if (API_CONFIG.useMockData) {
      await delay(300);
      return mockMetrics;
    }
    return realApi.get('/metrics');
  },
  
  // Agents
  getAgents: async (): Promise<Agent[]> => {
    if (API_CONFIG.useMockData) {
      await delay(400);
      return mockAgents;
    }
    return realApi.get('/agents');
  },
  
  getAgent: async (id: string): Promise<Agent> => {
    if (API_CONFIG.useMockData) {
      await delay(200);
      const agent = mockAgents.find(a => a.id === id);
      if (!agent) throw new Error('Agent not found');
      return agent;
    }
    return realApi.get(`/agents/${id}`);
  },
  
  startAgent: async (id: string): Promise<void> => {
    if (API_CONFIG.useMockData) {
      await delay(500);
      const agent = mockAgents.find(a => a.id === id);
      if (agent) agent.status = 'running';
      return;
    }
    return realApi.post(`/agents/${id}/start`, {});
  },
  
  stopAgent: async (id: string): Promise<void> => {
    if (API_CONFIG.useMockData) {
      await delay(500);
      const agent = mockAgents.find(a => a.id === id);
      if (agent) agent.status = 'idle';
      return;
    }
    return realApi.post(`/agents/${id}/stop`, {});
  },
  
  // Tasks
  getTasks: async (): Promise<Task[]> => {
    if (API_CONFIG.useMockData) {
      await delay(350);
      return mockTasks;
    }
    return realApi.get('/tasks');
  },
  
  getTask: async (id: string): Promise<Task> => {
    if (API_CONFIG.useMockData) {
      await delay(200);
      const task = mockTasks.find(t => t.id === id);
      if (!task) throw new Error('Task not found');
      return task;
    }
    return realApi.get(`/tasks/${id}`);
  },
  
  createTask: async (data: Partial<Task>): Promise<Task> => {
    if (API_CONFIG.useMockData) {
      await delay(600);
      const newTask: Task = {
        id: `task-${Date.now()}`,
        agent_id: data.agent_id!,
        agent_name: mockAgents.find(a => a.id === data.agent_id)?.name || 'Unknown',
        title: data.title!,
        status: 'pending',
        priority: data.priority || 'medium',
        created_at: new Date().toISOString(),
        progress: 0
      };
      mockTasks.unshift(newTask);
      return newTask;
    }
    return realApi.post('/tasks', data);
  },
  
  getTaskLogs: async (taskId: string): Promise<TaskLog[]> => {
    if (API_CONFIG.useMockData) {
      await delay(300);
      return mockTaskLogs[taskId] || [];
    }
    return realApi.get(`/tasks/${taskId}/logs`);
  },
  
  // Memory
  searchMemory: async (query: string): Promise<MemoryEntry[]> => {
    if (API_CONFIG.useMockData) {
      await delay(500);
      // Simple mock search - in real app, would use vector similarity
      return mockMemoryEntries.filter(entry => 
        entry.content.toLowerCase().includes(query.toLowerCase()) ||
        entry.tags?.some(tag => tag.toLowerCase().includes(query.toLowerCase()))
      );
    }
    return realApi.post('/memory/search', { query });
  },
  
  getMemoryEntries: async (): Promise<MemoryEntry[]> => {
    if (API_CONFIG.useMockData) {
      await delay(400);
      return mockMemoryEntries;
    }
    return realApi.get('/memory');
  }
};

export const getApiConfig = () => API_CONFIG;