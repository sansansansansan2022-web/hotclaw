"use client";

import Link from "next/link";

const SETTINGS_ITEMS = [
  {
    href: "/settings/llm-providers",
    icon: "&#9881;",
    title: "LLM Provider 配置",
    description: "管理 LLM API 密钥、Base URL、默认模型和连通性测试",
    tags: ["API Key", "模型配置", "连通性测试"],
    color: "cyan",
  },
  {
    href: "/settings/agents",
    icon: "&#129302;",
    title: "智能体配置",
    description: "管理各智能体的 Prompt 模板、模型参数和重试策略",
    tags: ["Prompt", "模型参数", "重试"],
    color: "purple",
  },
  {
    href: "/settings/skills",
    icon: "&#128161;",
    title: "技能配置",
    description: "管理可复用的技能模块，包括热点抓取和内容后处理",
    tags: ["热点抓取", "内容后处理", "可复用"],
    color: "yellow",
  },
];

const COLOR_MAP: Record<string, { border: string; iconBg: string; iconText: string; tagBg: string }> = {
  cyan: {
    border: "hover:border-cyan-500/50",
    iconBg: "bg-cyan-500/10",
    iconText: "text-cyan-400",
    tagBg: "bg-cyan-900/30 text-cyan-300",
  },
  purple: {
    border: "hover:border-purple-500/50",
    iconBg: "bg-purple-500/10",
    iconText: "text-purple-400",
    tagBg: "bg-purple-900/30 text-purple-300",
  },
  yellow: {
    border: "hover:border-yellow-500/50",
    iconBg: "bg-yellow-500/10",
    iconText: "text-yellow-400",
    tagBg: "bg-yellow-900/30 text-yellow-300",
  },
};

export default function SettingsPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
      {/* Header */}
      <header className="bg-slate-800/80 backdrop-blur-sm border-b border-slate-700 px-6 py-4 sticky top-0 z-20">
        <div className="max-w-4xl mx-auto flex items-center gap-4">
          <Link
            href="/"
            className="text-cyan-400 hover:text-cyan-300 transition-colors flex items-center gap-2"
          >
            <span>&larr;</span>
            <span>首页</span>
          </Link>
          <span className="text-slate-500">/</span>
          <span className="text-white font-medium">系统设置</span>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-4xl mx-auto p-6">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white mb-2">系统设置</h1>
          <p className="text-slate-400 text-sm">
            管理 LLM Provider、智能体配置和技能模块
          </p>
        </div>

        <div className="space-y-4">
          {SETTINGS_ITEMS.map((item) => {
            const colors = COLOR_MAP[item.color];
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`block bg-slate-800/60 border border-slate-700 rounded-xl p-6
                           ${colors.border} hover:bg-slate-800/80 transition-all group`}
              >
                <div className="flex items-start gap-5">
                  <div
                    className={`w-12 h-12 rounded-xl flex items-center justify-center text-2xl
                               ${colors.iconBg} ${colors.iconText} flex-shrink-0`}
                    dangerouslySetInnerHTML={{ __html: item.icon }}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <h2 className="text-white font-medium text-lg">{item.title}</h2>
                      <span className="text-slate-600 group-hover:text-slate-400 transition-colors text-lg">
                        &rarr;
                      </span>
                    </div>
                    <p className="text-slate-400 text-sm mb-3">{item.description}</p>
                    <div className="flex flex-wrap gap-2">
                      {item.tags.map((tag) => (
                        <span
                          key={tag}
                          className={`px-2 py-0.5 text-xs rounded-full ${colors.tagBg}`}
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      </main>
    </div>
  );
}
