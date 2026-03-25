/** Workstation: a desk with a monitor and a pixel character sitting at it. */

"use client";

import PixelCharacter from "./PixelCharacter";
import SpeechBubble from "./SpeechBubble";
import type { NodeStatus } from "@/types";

interface Props {
  agentId: string;
  name: string;
  status: NodeStatus;
  elapsed: number | null;
  outputSummary: string;
  error: string | null;
  onClick?: () => void;
  onContextMenu?: (e: React.MouseEvent) => void;
}

export default function Workstation({
  agentId,
  name,
  status,
  elapsed,
  outputSummary,
  error,
  onClick,
  onContextMenu,
}: Props) {
  const deskColor = "#8b6914";
  const monitorBg = status === "running" ? "#0f3460" : status === "completed" ? "#0a2e14" : "#1a1a2e";
  const monitorGlow =
    status === "running"
      ? "shadow-[0_0_8px_rgba(59,130,246,0.5)]"
      : status === "completed"
        ? "shadow-[0_0_8px_rgba(74,222,128,0.5)]"
        : "";

  let bubbleText = "";
  if (status === "running") bubbleText = "处理中...";
  else if (status === "completed" && outputSummary) bubbleText = outputSummary.slice(0, 20);
  else if (status === "failed" && error) bubbleText = "出错了!";

  return (
    <div
      className="flex flex-col items-center cursor-pointer group relative"
      onClick={onClick}
      onContextMenu={onContextMenu}
      title={`${name} (${agentId})`}
    >
      {/* Speech bubble */}
      {bubbleText && <SpeechBubble text={bubbleText} status={status} />}

      {/* Character */}
      <div className="relative z-10 mb-[-4px]">
        <PixelCharacter agentId={agentId} status={status} name={name} size={64} />
      </div>

      {/* Desk with monitor */}
      <div className="relative">
        {/* Monitor */}
        <div
          className={`w-[40px] h-[28px] border-2 border-gray-500 rounded-sm relative overflow-hidden ${monitorGlow}`}
          style={{ backgroundColor: monitorBg }}
        >
          {status === "running" && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-[4px] h-[4px] bg-blue-400 animate-ping rounded-full" />
            </div>
          )}
          {status === "completed" && (
            <div className="absolute inset-0 flex items-center justify-center text-green-400 text-[10px]">
              ✓
            </div>
          )}
          {status === "failed" && (
            <div className="absolute inset-0 flex items-center justify-center text-red-400 text-[10px]">
              ✗
            </div>
          )}
          {status === "running" && (
            <div
              className="absolute inset-0 opacity-10 pointer-events-none"
              style={{
                background:
                  "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255,255,255,0.03) 2px, rgba(255,255,255,0.03) 4px)",
              }}
            />
          )}
        </div>
        {/* Monitor stand */}
        <div className="w-[8px] h-[6px] bg-gray-500 mx-auto" />

        {/* Desk surface */}
        <div
          className="w-[56px] h-[8px] rounded-sm"
          style={{ backgroundColor: deskColor }}
        />
        {/* Desk legs */}
        <div className="flex justify-between px-[4px]">
          <div className="w-[4px] h-[12px]" style={{ backgroundColor: "#6b4f10" }} />
          <div className="w-[4px] h-[12px]" style={{ backgroundColor: "#6b4f10" }} />
        </div>
      </div>

      {/* Name label */}
      <div className="mt-1 text-[9px] font-mono text-gray-300 text-center leading-tight max-w-[64px] group-hover:text-white transition-colors">
        {name}
      </div>

      {/* Elapsed time */}
      {elapsed !== null && (
        <div className="text-[8px] font-mono text-gray-500">
          {elapsed.toFixed(1)}s
        </div>
      )}
    </div>
  );
}
