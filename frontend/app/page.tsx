/** Main page: the pixel-art editorial office.
 *
 * Powered by PixelOffice Canvas engine.
 * Agent characters render in real-time, driven by SSE task events.
 */

"use client";

import { useState, useCallback } from "react";
// import PixelOffice from "@/components/office/PixelOffice";
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
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <h1 className="text-3xl font-bold mb-8 text-center">HotClaw 主页</h1>
      <div className="max-w-4xl mx-auto">
        <div className="bg-gray-800 rounded-lg p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">欢迎使用 HotClaw</h2>
          <p className="text-gray-300 mb-4">
            这是一个基于 Next.js 构建的现代化应用平台。
          </p>
          <div className="flex space-x-4">
            <a 
              href="/newsroom" 
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
            >
              访问新闻编辑部
            </a>
            <button 
              onClick={() => handleCreateTask('test-positioning')}
              disabled={loading}
              className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg transition-colors disabled:opacity-50"
            >
              {loading ? '创建中...' : '创建测试任务'}
            </button>
          </div>
        </div>
        
        {taskId && (
          <div className="bg-gray-800 rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-2">当前任务</h3>
            <p className="text-gray-300">任务ID: {taskId}</p>
            {resultData && (
              <div className="mt-4 p-4 bg-gray-700 rounded">
                <h4 className="font-medium mb-2">结果数据:</h4>
                <pre className="text-sm text-gray-300 whitespace-pre-wrap">
                  {JSON.stringify(resultData, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
