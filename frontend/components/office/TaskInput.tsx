/** Task input panel at the bottom of the office scene. */

"use client";

import { useState } from "react";

interface Props {
  onSubmit: (positioning: string) => void;
  loading: boolean;
  disabled: boolean;
}

export default function TaskInput({ onSubmit, loading, disabled }: Props) {
  const [text, setText] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = text.trim();
    if (trimmed.length < 5) return;
    onSubmit(trimmed);
  }

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-[600px]">
      <div className="bg-gray-900/80 border border-gray-600 rounded-sm p-3">
        <div className="text-[10px] font-mono text-cyan-400 mb-2">
          ▸ 输入账号定位，编辑部开始工作
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="例：我是一个关注职场成长的公众号，目标读者是25-35岁互联网从业者"
            disabled={disabled || loading}
            className="flex-1 bg-gray-800 border border-gray-600 rounded-sm px-3 py-2
                       text-[12px] font-mono text-gray-200 placeholder:text-gray-600
                       focus:outline-none focus:border-cyan-500 transition-colors
                       disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={disabled || loading || text.trim().length < 5}
            className="bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-700 disabled:text-gray-500
                       text-white text-[11px] font-mono px-4 py-2 rounded-sm transition-colors
                       border border-cyan-500 disabled:border-gray-600"
          >
            {loading ? "派活中..." : "开始"}
          </button>
        </div>
      </div>
    </form>
  );
}
