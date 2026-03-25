/** Main page: the pixel-art editorial office.
 *
 * Powered by PixelOffice Canvas engine.
 * Agent characters render in real-time, driven by SSE task events.
 */

"use client";

import { useState, useCallback } from "react";
import PixelOffice from "@/components/office/PixelOffice";
import { useTaskSSE } from "@/hooks/useTaskSSE";
import { createTask, getTaskDetail } from "@/lib/api";

export default function HomePage() {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [resultData, setResultData] = useState<Record<string, unknown> | null>(null);

  const { nodes, taskDone, taskError } = useTaskSSE(taskId);

  // When task completes, fetch full result
  const fetchResult = useCallback(async (tid: string) => {
    try {
      const detail = await getTaskDetail(tid);
      if (detail.result_data) {
        setResultData(detail.result_data);
      }
    } catch {
      // Result fetch failure is non-critical
    }
  }, []);

  // Watch for task completion
  if (taskDone && taskId && !resultData) {
    fetchResult(taskId);
  }

  async function handleCreateTask(positioning: string) {
    setLoading(true);
    setResultData(null);
    try {
      const data = await createTask(positioning);
      setTaskId(data.task_id);
    } catch (err) {
      alert(err instanceof Error ? err.message : "创建任务失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <PixelOffice
      nodes={nodes}
      taskDone={taskDone}
      taskError={taskError}
      taskId={taskId}
      onCreateTask={handleCreateTask}
      loading={loading}
      resultData={resultData}
    />
  );
}
