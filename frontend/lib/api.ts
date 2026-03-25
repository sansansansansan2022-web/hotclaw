/** API client for HotClaw backend. */

import type {
  ApiResponse,
  TaskCreateRequest,
  TaskCreateData,
  TaskDetail,
  NodeRun,
  TaskSummary,
} from "@/types";

const BASE = "/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body: ApiResponse<T> = await res.json();
  if (body.code !== 0) {
    throw new Error(body.message || "request failed");
  }
  return body.data;
}

export async function createTask(positioning: string): Promise<TaskCreateData> {
  return request<TaskCreateData>("/tasks", {
    method: "POST",
    body: JSON.stringify({ positioning } satisfies TaskCreateRequest),
  });
}

export async function getTaskDetail(taskId: string): Promise<TaskDetail> {
  return request<TaskDetail>(`/tasks/${taskId}`);
}

export async function getTaskNodes(taskId: string): Promise<{ nodes: NodeRun[] }> {
  return request<{ nodes: NodeRun[] }>(`/tasks/${taskId}/nodes`);
}

export async function listTasks(
  page = 1,
  pageSize = 20
): Promise<{ tasks: TaskSummary[]; pagination: { page: number; page_size: number; total: number } }> {
  return request(`/tasks?page=${page}&page_size=${pageSize}`);
}

export function getTaskStreamUrl(taskId: string): string {
  return `${BASE}/tasks/${taskId}/stream`;
}

// --- Agents ---

export interface AgentInfo {
  agent_id: string;
  name: string;
  description: string;
  version: string;
  status: string;
  model_config_data?: Record<string, unknown> | null;
  prompt_template?: string | null;
  prompt_source?: string | null;
  default_system_prompt?: string | null;
  has_custom_prompt?: boolean;
  retry_config?: Record<string, unknown> | null;
}

export async function listAgents(): Promise<{ agents: AgentInfo[] }> {
  return request<{ agents: AgentInfo[] }>("/agents");
}

export async function getAgent(agentId: string): Promise<AgentInfo> {
  return request<AgentInfo>(`/agents/${agentId}`);
}

export async function updateAgentConfig(
  agentId: string,
  config: { model_config_data?: Record<string, unknown>; prompt_template?: string; retry_config?: Record<string, unknown> }
): Promise<{ agent_id: string; updated_fields: string[] }> {
  return request(`/agents/${agentId}/config`, {
    method: "PUT",
    body: JSON.stringify(config),
  });
}

// --- Skills ---

export interface SkillInfo {
  skill_id: string;
  name: string;
  description: string;
  version: string;
  config_data: Record<string, unknown> | null;
  status: string;
}

export async function listSkills(): Promise<{ skills: SkillInfo[] }> {
  return request<{ skills: SkillInfo[] }>("/skills");
}

export async function updateSkillConfig(
  skillId: string,
  config: { config_data: Record<string, unknown> }
): Promise<{ skill_id: string; updated: boolean }> {
  return request(`/skills/${skillId}/config`, {
    method: "PUT",
    body: JSON.stringify(config),
  });
}
