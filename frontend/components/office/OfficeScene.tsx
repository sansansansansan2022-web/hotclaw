/** OfficeScene: main pixel-art editorial office room.
 *
 * Layout (based on R2108101 LargePixelOffice.png):
 *   - Upper: large editorial floor scene (LargePixelOffice.png)
 *   - Bottom: 3-panel bar (LOGS | STATUS | VISITORS)
 *
 * 6 backend agents mapped to 4 sprite types:
 *   分析型(蓝紫): profile_agent, hot_topic_agent
 *   策划型(橙):   topic_planner_agent
 *   创作型(绿):   title_generator_agent, content_writer_agent
 *   审核型(紫):   audit_agent
 */

"use client";

import { useState, useRef } from "react";
import Link from "next/link";
import PixelCharacter, { StatusIcon } from "./PixelCharacter";
import SpeechBubble from "./SpeechBubble";
import TaskInput from "./TaskInput";
import ResultPanel from "./ResultPanel";
import AgentContextMenu from "./AgentContextMenu";
import AgentSettingsDrawer from "./AgentSettingsDrawer";
import ExclamationEffect from "./ExclamationEffect";
import { SCENES } from "@/lib/assets";
import type { NodeState } from "@/hooks/useTaskSSE";
import type { NodeStatus } from "@/types";

// 6 agents positioned in LargePixelOffice room (zones: entry → sofa → bookshelf → workstations → server)
const AGENT_CONFIG = [
  { agent_id: "profile_agent",         name: "小档", role: "账号解析",   left: "18%", top: "50%" },
  { agent_id: "hot_topic_agent",       name: "小热", role: "热点分析",   left: "30%", top: "35%" },
  { agent_id: "topic_planner_agent",   name: "小策", role: "选题策划",   left: "42%", top: "55%" },
  { agent_id: "title_generator_agent", name: "小标", role: "标题生成",   left: "58%", top: "38%" },
  { agent_id: "content_writer_agent",  name: "小文", role: "正文生成",   left: "70%", top: "55%" },
  { agent_id: "audit_agent",          name: "小审", role: "审核评估",   left: "82%", top: "42%" },
];

interface Props {
  nodes: NodeState[];
  taskDone: boolean;
  taskError: string | null;
  taskId: string | null;
  onCreateTask: (positioning: string) => void;
  loading: boolean;
  resultData: Record<string, unknown> | null;
}

interface ContextMenuState {
  agentId: string;
  agentName: string;
  x: number;
  y: number;
}

interface ExclamationItem {
  id: number;
  x: number;
  y: number;
}

export default function OfficeScene({
  nodes,
  taskDone,
  taskError,
  taskId,
  onCreateTask,
  loading,
  resultData,
}: Props) {
  const isRunning = nodes.some((n) => n.status === "running");
  const showResult = taskDone && resultData;

  // Interaction state
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);
  const [settingsAgent, setSettingsAgent] = useState<string | null>(null);
  const [exclamations, setExclamations] = useState<ExclamationItem[]>([]);
  const nextExclId = useRef(0);

  function handleAgentContextMenu(
    e: React.MouseEvent,
    agentId: string,
    agentName: string,
  ) {
    e.preventDefault();
    const id = nextExclId.current++;
    setExclamations((prev) => [...prev, { id, x: e.clientX, y: e.clientY }]);
    setContextMenu({ agentId, agentName, x: e.clientX, y: e.clientY });
  }

  function handleExclamationDone(id: number) {
    setExclamations((prev) => prev.filter((item) => item.id !== id));
  }

  function getBubbleText(
    status: NodeStatus,
    outputSummary: string,
    error: string | null,
  ): string {
    if (status === "running") return "处理中...";
    if (status === "completed" && outputSummary) {
      return outputSummary.length > 16
        ? outputSummary.slice(0, 16) + "..."
        : outputSummary;
    }
    if (status === "failed" && error) return "出错了!";
    return "";
  }

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden bg-[#1a1a2e]">
      {/* ============ Room section ============ */}
      <div
        className="relative flex-1 min-h-0 pixel-border-pink mx-2 mt-2 overflow-hidden"
        style={{
          backgroundImage: `url(${SCENES.large})`,
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        {/* Title + Navigation */}
        <div className="absolute top-2 left-0 right-0 z-20 flex items-center justify-center">
          <div className="bg-black/50 backdrop-blur-sm px-4 py-1 rounded-sm flex items-center gap-4">
            <span className="text-[13px] font-mono text-gray-200 tracking-[0.3em]">
              HOTCLAW 编辑部
            </span>
            <nav className="flex gap-2 text-[9px]">
              <Link
                href="/history"
                className="text-gray-400 hover:text-cyan-400 transition-colors border border-gray-600/50 px-2 py-0.5 rounded-sm"
              >
                历史任务
              </Link>
              <Link
                href="/settings/agents"
                className="text-gray-400 hover:text-cyan-400 transition-colors border border-gray-600/50 px-2 py-0.5 rounded-sm"
              >
                Agent
              </Link>
            </nav>
          </div>
        </div>

        {/* Agent sprite overlays */}
        {AGENT_CONFIG.map((agent) => {
          const node = nodes.find((n) => n.agent_id === agent.agent_id);
          const status = node?.status || "pending";
          const bubbleText = getBubbleText(
            status,
            node?.output_summary || "",
            node?.error ?? null,
          );

          return (
            <div
              key={agent.agent_id}
              className="absolute flex flex-col items-center cursor-pointer group"
              style={{
                left: agent.left,
                top: agent.top,
                transform: "translate(-50%, -50%)",
              }}
              onContextMenu={(e) =>
                handleAgentContextMenu(e, agent.agent_id, agent.name)
              }
              title={`${agent.name} - ${agent.role}\n右键打开设置`}
            >
              {bubbleText && (
                <SpeechBubble text={bubbleText} status={status} />
              )}
              <PixelCharacter
                agentId={agent.agent_id}
                status={status}
                name={agent.name}
                size={48}
              />
              <div className="text-[8px] font-mono text-white bg-black/50 px-1 rounded-sm mt-0.5 group-hover:text-cyan-300 transition-colors">
                {agent.name}
              </div>
            </div>
          );
        })}

        {/* Room bottom bar */}
        <div className="absolute bottom-0 left-0 right-0 bg-[#5a3a20]/80 py-1">
          <div className="text-center text-[10px] font-mono text-[#d4a86a] tracking-widest">
            ─── HOTCLAW ROOM ───
          </div>
        </div>

        {/* Task status floating badge */}
        {taskId && (
          <div className="absolute bottom-8 left-1/2 -translate-x-1/2 z-20">
            <div className="bg-black/60 border border-gray-600/50 rounded-sm px-3 py-1 flex items-center gap-2">
              {isRunning && (
                <>
                  <span className="w-[6px] h-[6px] rounded-full bg-yellow-400 animate-pulse" />
                  <span className="text-[9px] font-mono text-yellow-300">
                    编辑部工作中...
                  </span>
                </>
              )}
              {taskDone && !taskError && (
                <>
                  <span className="w-[6px] h-[6px] rounded-full bg-green-400" />
                  <span className="text-[9px] font-mono text-green-300">
                    全部完成!
                  </span>
                </>
              )}
              {taskError && (
                <>
                  <span className="w-[6px] h-[6px] rounded-full bg-red-400" />
                  <span className="text-[9px] font-mono text-red-300">
                    出错: {taskError}
                  </span>
                </>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ============ Bottom 3-panel section ============ */}
      <div className="h-[220px] shrink-0 flex gap-2 px-2 pb-2 pt-1">
        {/* --- LOGS panel --- */}
        <div className="flex-1 pixel-border-pink bg-[#1a1a3e] flex flex-col overflow-hidden">
          <div className="bg-[#2a2a5a] px-3 py-1 border-b border-[#6b4f10]">
            <span className="text-[10px] font-mono text-yellow-400 tracking-wider">
              LOGS
            </span>
          </div>
          {/* Compact task input */}
          <div className="px-2 pt-1.5 shrink-0">
            <TaskInput
              onSubmit={onCreateTask}
              loading={loading}
              disabled={isRunning}
            />
          </div>
          {/* Log entries */}
          <div className="flex-1 overflow-y-auto px-2 pb-1 mt-1">
            <div className="space-y-0.5">
              {nodes.map((node) => {
                if (node.status === "pending") return null;
                return (
                  <div
                    key={node.node_id}
                    className="flex items-start gap-1.5 text-[9px] font-mono"
                  >
                    <span
                      className={`mt-0.5 w-[5px] h-[5px] rounded-full shrink-0 ${
                        node.status === "running"
                          ? "bg-yellow-400 animate-pulse"
                          : node.status === "completed"
                            ? "bg-green-400"
                            : node.status === "failed"
                              ? "bg-red-400"
                              : "bg-gray-500"
                      }`}
                    />
                    <span className="text-gray-400">{node.name}</span>
                    <span
                      className={
                        node.status === "running"
                          ? "text-yellow-300"
                          : node.status === "completed"
                            ? "text-green-300"
                            : node.status === "failed"
                              ? "text-red-300"
                              : "text-gray-500"
                      }
                    >
                      {node.status === "running"
                        ? "执行中..."
                        : node.status === "completed"
                          ? `完成 ${node.elapsed_seconds?.toFixed(1)}s`
                          : node.status === "failed"
                            ? "失败"
                            : ""}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* --- STATUS panel --- */}
        <div className="flex-1 pixel-border-pink bg-[#1a1a3e] flex flex-col overflow-hidden">
          <div className="bg-[#2a2a5a] px-3 py-1 border-b border-[#6b4f10]">
            <span className="text-[10px] font-mono text-yellow-400 tracking-wider">
              STATUS
            </span>
          </div>
          <div className="flex-1 p-2 grid grid-cols-3 grid-rows-2 gap-1">
            {AGENT_CONFIG.map((agent) => {
              const node = nodes.find((n) => n.agent_id === agent.agent_id);
              const status = node?.status || "pending";
              return (
                <div
                  key={agent.agent_id}
                  className="flex flex-col items-center justify-center bg-[#0a0a1e] rounded-sm
                             border border-gray-700/30 p-1 cursor-pointer
                             hover:border-cyan-500/50 transition-colors"
                  onContextMenu={(e) =>
                    handleAgentContextMenu(e, agent.agent_id, agent.name)
                  }
                  title={`${agent.name} - ${agent.role}`}
                >
                  <StatusIcon agentId={agent.agent_id} status={status} name={agent.name} size={24} />
                  <div className="text-[8px] font-mono text-gray-300 mt-0.5">
                    {agent.name}
                  </div>
                  <div
                    className={`text-[7px] font-mono ${
                      status === "running"
                        ? "text-yellow-400"
                        : status === "completed"
                          ? "text-green-400"
                          : status === "failed"
                            ? "text-red-400"
                            : "text-gray-500"
                    }`}
                  >
                    {status === "pending"
                      ? "IDLE"
                      : status === "running"
                        ? "WORK"
                        : status === "completed"
                          ? "DONE"
                          : "ALRT"}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* --- VISITORS panel --- */}
        <div className="flex-1 pixel-border-pink bg-[#1a1a3e] flex flex-col overflow-hidden">
          <div className="bg-[#2a2a5a] px-3 py-1 border-b border-[#6b4f10]">
            <span className="text-[10px] font-mono text-yellow-400 tracking-wider">
              VISITORS
            </span>
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {taskId ? (
              <>
                <div className="text-[9px] font-mono text-gray-400 mb-1">
                  任务:{" "}
                  <span className="text-cyan-400">
                    {taskId.slice(0, 8)}...
                  </span>
                </div>
                {nodes
                  .filter((n) => n.status !== "pending")
                  .map((node) => (
                    <div
                      key={node.node_id}
                      className="flex items-center gap-1.5 bg-[#0a0a1e] rounded-sm p-1.5 border border-gray-700/20"
                    >
                      <StatusIcon
                        agentId={node.agent_id}
                        status={node.status}
                        name={node.name}
                        size={18}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="text-[8px] font-mono text-gray-300 truncate">
                          {node.agent_id}
                        </div>
                        {node.output_summary && (
                          <div className="text-[7px] font-mono text-gray-500 truncate">
                            {node.output_summary}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
              </>
            ) : (
              <div className="text-[9px] font-mono text-gray-500 text-center mt-4">
                等待任务...
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ============ Overlays ============ */}

      {/* Exclamation effects */}
      {exclamations.map((exc) => (
        <ExclamationEffect
          key={exc.id}
          x={exc.x}
          y={exc.y}
          onDone={() => handleExclamationDone(exc.id)}
        />
      ))}

      {/* Right-click context menu */}
      {contextMenu && (
        <AgentContextMenu
          agentId={contextMenu.agentId}
          agentName={contextMenu.agentName}
          x={contextMenu.x}
          y={contextMenu.y}
          onClose={() => setContextMenu(null)}
          onSettings={() => setSettingsAgent(contextMenu.agentId)}
          onViewPrompt={() => setSettingsAgent(contextMenu.agentId)}
        />
      )}

      {/* Settings drawer */}
      <AgentSettingsDrawer
        agentId={settingsAgent || ""}
        open={!!settingsAgent}
        onClose={() => setSettingsAgent(null)}
      />

      {/* Result slide-out panel */}
      {showResult && <ResultPanel data={resultData} />}
    </div>
  );
}
