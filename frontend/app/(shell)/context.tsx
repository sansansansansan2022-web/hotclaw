/**
 * Shell Context — 壳层上下文
 *
 * 提供 Shell Layout 的共享状态给子视图使用。
 */

import { createContext, useContext } from "react";

// =============================================================================
// 类型定义
// =============================================================================

export interface DashboardStats {
  todayTasks: number;
  pendingDrafts: number;
  publishedToday: number;
  publishFailed: number;
}

export interface RecentEvent {
  id: string;
  type: "task" | "draft" | "publish";
  action: string;
  title: string;
  accountName?: string;
  time: string;
  timestamp: number;
  status: "success" | "failed" | "pending" | "info";
}

export interface ShellContextValue {
  stats: DashboardStats;
  accounts: import("@/types").AccountSummary[];
  drafts: import("@/types").DraftSummary[];
  tasks: import("@/types").TaskSummary[];
  events: RecentEvent[];
  refreshData: () => void;
}

// =============================================================================
// Context
// =============================================================================

export const ShellContext = createContext<ShellContextValue | null>(null);

export function useShellContext(): ShellContextValue {
  const ctx = useContext(ShellContext);
  if (!ctx) {
    throw new Error("useShellContext must be used within ShellLayout");
  }
  return ctx;
}
