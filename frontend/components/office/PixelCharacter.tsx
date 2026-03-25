/** PixelCharacter: renders individual agent sprite images.
 *
 * Each agent has its own transparent PNG sprite image.
 * Uses CSS to overlay on the background scene.
 */

"use client";

import { AGENT_SPRITE_URL } from "@/lib/assets";

type AgentStatus = "pending" | "running" | "completed" | "failed" | "skipped";

interface CharacterProps {
  agentId: string;
  status: AgentStatus;
  name: string;
  size?: number;
}

interface IconProps {
  agentId?: string;
  status: AgentStatus;
  name: string;
  size?: number;
}

function getAnimClass(status: string) {
  if (status === "running") return "animate-[pixel-work_0.5s_ease-in-out_infinite]";
  if (status === "completed") return "animate-[pixel-done_1.5s_ease-in-out_infinite]";
  if (status === "failed") return "animate-[pixel-idle_2s_ease-in-out_infinite] opacity-60";
  return "animate-[pixel-idle_2s_ease-in-out_infinite]";
}

/** Main character: individual sprite image */
export default function PixelCharacter({ agentId, status, name, size = 64 }: CharacterProps) {
  const spriteUrl = AGENT_SPRITE_URL[agentId] || AGENT_SPRITE_URL["profile_agent"];
  const animClass = getAnimClass(status);

  return (
    <div className="flex flex-col items-center gap-0.5">
      <div className={animClass}>
        <img
          src={spriteUrl}
          alt={name}
          width={size}
          height={size}
          style={{
            imageRendering: "pixelated",
          }}
        />
      </div>
      {status === "running" && (
        <div className="text-[7px] text-yellow-300 font-mono animate-pulse">工作中</div>
      )}
      {status === "completed" && (
        <div className="text-[7px] text-green-400 font-mono">✓</div>
      )}
      {status === "failed" && (
        <div className="text-[7px] text-red-400 font-mono">✗</div>
      )}
    </div>
  );
}

/** StatusIcon: tiny sprite for panels */
export function StatusIcon({ agentId = "", status, name, size = 24 }: IconProps) {
  const spriteUrl = agentId ? (AGENT_SPRITE_URL[agentId] || AGENT_SPRITE_URL["profile_agent"]) : AGENT_SPRITE_URL["profile_agent"];

  return (
    <img
      src={spriteUrl}
      alt={name}
      width={size}
      height={size}
      style={{
        imageRendering: "pixelated",
        flexShrink: 0,
      }}
      title={name}
    />
  );
}
