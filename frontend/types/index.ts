/** Shared type definitions for HotClaw frontend. */

// --- Agent / Task status ---

export type TaskStatus = "pending" | "running" | "completed" | "failed";
export type NodeStatus = "pending" | "running" | "completed" | "failed" | "skipped";

// --- API response ---

export interface ApiResponse<T = unknown> {
  code: number;
  message: string;
  data: T;
  details?: Record<string, unknown> | null;
}

// --- Task ---

export interface TaskCreateRequest {
  positioning: string;
  workflow_id?: string;
}

export interface TaskCreateData {
  task_id: string;
  status: TaskStatus;
  created_at: string;
  workflow_id: string;
}

export interface TaskDetail {
  task_id: string;
  status: TaskStatus;
  input_data: { positioning: string } | null;
  workflow_id: string;
  result_data: Record<string, unknown> | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  elapsed_seconds: number | null;
  total_tokens: number | null;
}

export interface NodeRun {
  node_id: string;
  agent_id: string;
  status: NodeStatus;
  input_data: Record<string, unknown> | null;
  output_data: Record<string, unknown> | null;
  started_at: string | null;
  completed_at: string | null;
  elapsed_seconds: number | null;
  degraded: boolean;
  error_message: string | null;
}

export interface TaskSummary {
  task_id: string;
  positioning_summary: string;
  status: TaskStatus;
  created_at: string;
  elapsed_seconds: number | null;
}

// --- SSE events ---

export interface SSENodeStart {
  node_id: string;
  agent_id: string;
  name: string;
  index: number;
  total: number;
  started_at: string;
}

export interface SSENodeComplete {
  node_id: string;
  agent_id: string;
  name: string;
  elapsed_seconds: number;
  degraded: boolean;
  output_summary: string;
}

export interface SSENodeError {
  node_id: string;
  error: string;
}

export interface SSETaskComplete {
  task_id: string;
  elapsed_seconds: number;
}

// --- Agent characters ---

export interface AgentCharacter {
  agent_id: string;
  name: string;
  role: string;
  color: string;       // Primary pixel color
  accent: string;      // Secondary pixel color
  deskX: number;       // Position in office grid
  deskY: number;
  idleFrames: number;
}

// --- Dashboard ---

export interface DashboardStats {
  account_name: string;
  followers: number;
  total_reads: number;
  avg_reads: number;
  articles_count: number;
  weekly_growth: number;
}
