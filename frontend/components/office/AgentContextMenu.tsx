/** AgentContextMenu: pixel-style right-click menu for agents. */

"use client";

import { useEffect, useRef } from "react";
import Image from "next/image";
import { SPRITES } from "@/lib/assets";

interface Props {
  agentId: string;
  agentName: string;
  x: number;
  y: number;
  onClose: () => void;
  onSettings: () => void;
  onViewPrompt: () => void;
}

export default function AgentContextMenu({
  agentId,
  agentName,
  x,
  y,
  onClose,
  onSettings,
  onViewPrompt,
}: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose();
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [onClose]);

  return (
    <div
      ref={ref}
      className="absolute z-50 pixel-border-pink min-w-[140px]"
      style={{ left: x, top: y }}
    >
      {/* Header */}
      <div className="bg-[#1a1a3e] px-3 py-1.5 border-b border-[#6b4f10]">
        <div className="text-[10px] text-yellow-400 font-mono font-bold truncate">
          {agentName}
        </div>
        <div className="text-[8px] text-gray-500 font-mono">{agentId}</div>
      </div>

      {/* Menu items */}
      <div className="bg-[#1a1a3e] py-1">
        <button
          onClick={() => { onSettings(); onClose(); }}
          className="w-full flex items-center gap-2 px-3 py-1.5 text-[10px] font-mono text-gray-200
                     hover:bg-[#2a2a5a] transition-colors text-left"
        >
          <Image
            src={SPRITES.uiGear}
            alt="settings"
            width={12}
            height={12}
            className="pixelated"
            style={{ imageRendering: "pixelated" }}
            unoptimized
          />
          设置
        </button>
        <button
          onClick={() => { onViewPrompt(); onClose(); }}
          className="w-full flex items-center gap-2 px-3 py-1.5 text-[10px] font-mono text-gray-200
                     hover:bg-[#2a2a5a] transition-colors text-left"
        >
          <span className="w-[12px] text-center text-[10px]">📝</span>
          查看 Prompt
        </button>
      </div>
    </div>
  );
}
