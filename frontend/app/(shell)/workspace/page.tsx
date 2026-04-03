/**
 * Workspace — 创作工作台视图
 *
 * 【Shell 内视图】
 * 包含 CommandCenter（任务创建 + 6智能体环形展示）。
 */

"use client";

import CommandCenter from "@/components/command-center/CommandCenter";

export default function WorkspaceView() {
  return (
    <div className="h-full">
      <CommandCenter />
    </div>
  );
}
