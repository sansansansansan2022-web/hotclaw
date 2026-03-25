/** Speech bubble that appears above a working character. */

"use client";

import type { NodeStatus } from "@/types";

interface Props {
  text: string;
  status: NodeStatus;
}

export default function SpeechBubble({ text, status }: Props) {
  const borderColor =
    status === "running"
      ? "border-blue-400"
      : status === "completed"
        ? "border-green-400"
        : status === "failed"
          ? "border-red-400"
          : "border-gray-400";

  const textColor =
    status === "running"
      ? "text-blue-300"
      : status === "completed"
        ? "text-green-300"
        : status === "failed"
          ? "text-red-300"
          : "text-gray-300";

  return (
    <div className="animate-[float-bubble_2s_ease-in-out_infinite] mb-1">
      <div
        className={`relative bg-gray-900/90 ${borderColor} border px-2 py-0.5 rounded-sm`}
      >
        <span className={`text-[8px] font-mono ${textColor} whitespace-nowrap`}>
          {text}
        </span>
        {/* Triangle pointer */}
        <div
          className={`absolute left-1/2 -translate-x-1/2 -bottom-[5px] w-0 h-0
            border-l-[4px] border-l-transparent
            border-r-[4px] border-r-transparent
            border-t-[5px] ${borderColor.replace("border-", "border-t-")}`}
        />
      </div>
    </div>
  );
}
