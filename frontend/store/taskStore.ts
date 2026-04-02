"use client";

/**
 * ============================================================
 * taskStore.ts - 任务状态管理
 * ============================================================
 *
 * 【状态管理方案】
 * 使用 Zustand + persist 中间件实现全局状态管理
 * - Zustand：轻量级 React 状态管理库，比 Redux 更简洁
 * - persist：Zustand 的持久化中间件，将状态保存到 localStorage
 *
 * 【设计目的】
 * 在页面刷新后仍能恢复用户的"当前任务"上下文
 * - 用户发起任务后刷新页面，仍能看到任务状态
 * - 任务定位信息（positioning）也一并保存
 *
 * 【与 SSE 的区别】
 * - SSE (useTaskSSE)：实时同步后端任务状态，页面级（组件卸载即丢失）
 * - taskStore：持久化任务上下文，浏览器会话间共享
 *
 * 面试点：
 * - Zustand 的 create + hooks 用法
 * - persist 中间件的 localStorage 持久化
 * - TypeScript 泛型约束状态结构
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";

// ============================================================
// 状态类型定义
// ============================================================

/**
 * 任务状态接口
 * 定义了任务模块的完整状态结构和操作方法
 */
interface TaskState {
  // ========== 状态字段 ==========

  /** 当前活跃任务的唯一标识符 */
  // null 表示没有活跃任务
  activeTaskId: string | null;

  /** 任务创建时的定位描述文本 */
  // 用于恢复用户的输入内容，避免重复输入
  activePositioning: string | null;

  // ========== 操作方法 ==========

  /**
   * 设置活跃任务
   * @param taskId - 任务ID
   * @param positioning - 可选的任务描述
   */
  setActiveTask: (taskId: string, positioning?: string) => void;

  /**
   * 清除活跃任务
   * 用于任务完成后或用户主动取消时调用
   */
  clearActiveTask: () => void;
}

// ============================================================
// 状态创建
// ============================================================

/**
 * 任务状态存储
 *
 * 使用流程：
 * 1. create<TaskState>() - 创建带类型的 store
 * 2. persist() - 包装持久化中间件
 * 3. set() - 更新状态（自动合并）
 *
 * persist 配置：
 * - name: localStorage 的键名
 * - 状态会自动序列化/反序列化
 */
export const useTaskStore = create<TaskState>()(
  // persist 中间件：第二个参数是配置对象
  persist(
    // set 函数：更新状态的唯一方式
    (set) => ({
      // ---------- 初始状态 ----------
      activeTaskId: null,
      activePositioning: null,

      // ---------- setActiveTask ----------
      // 更新当前活跃任务
      // 使用函数式更新，Zustand 会自动合并状态
      setActiveTask: (taskId: string, positioning?: string) =>
        set({
          activeTaskId: taskId,
          // 如果没有传 positioning，保持现有的
          // 如果传了，用新值；如果传了 undefined，转为 null
          activePositioning: positioning || null,
        }),

      // ---------- clearActiveTask ----------
      // 重置任务状态到初始值
      clearActiveTask: () =>
        set({
          activeTaskId: null,
          activePositioning: null,
        }),
    }),
    // ---------- persist 配置 ----------
    {
      // localStorage 中存储的键名
      name: "hotclaw-task-store",
    }
  )
);

// ============================================================
// 使用示例
// ============================================================

/**
 * 在组件中使用：
 *
 * ```tsx
 * import { useTaskStore } from "@/store/taskStore";
 *
 * function MyComponent() {
 *   // 读取状态
 *   const taskId = useTaskStore((state) => state.activeTaskId);
 *
 *   // 写入状态
 *   const setActiveTask = useTaskStore((state) => state.setActiveTask);
 *
 *   // 调用
 *   setActiveTask("task-123", "我的公众号定位");
 * }
 * ```
 *
 * 【性能优化提示】
 * - 避免订阅整个状态对象
 * - 使用选择器只订阅需要的字段：
 *   ✓ const taskId = useTaskStore(s => s.activeTaskId)
 *   ✗ const store = useTaskStore()
 *
 * 【持久化说明】
 * - 页面刷新后状态从 localStorage 恢复
 * - 清除浏览器缓存会丢失状态
 * - 可在浏览器 DevTools → Application → Local Storage 查看
 */
