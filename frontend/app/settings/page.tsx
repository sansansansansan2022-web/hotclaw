"use client";

import Link from "next/link";
import { PageHeader, SectionCard } from "@/components/console-ui";

const ITEMS = [
  { href: "/settings/llm-providers", title: "LLM Provider", desc: "模型供应商与 API Key" },
  { href: "/settings/agents", title: "智能体配置", desc: "Prompt、模型参数、重试策略" },
  { href: "/settings/skills", title: "Skill 配置", desc: "技能插件配置" },
  { href: "/accounts", title: "微信配置", desc: "先进入账号详情，再配置公众号" },
  { href: "/history", title: "系统运行", desc: "任务历史与运行回看" },
];

export default function SettingsPage() {
  return (
    <div className="min-h-screen bg-[#F5F7FA] p-6">
      <div className="mx-auto max-w-6xl space-y-4">
        <div><Link href="/" className="text-sm text-emerald-600">← 返回运营总览</Link></div>
        <PageHeader title="设置中心" subtitle="统一入口，不在单页堆叠表单" />
        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {ITEMS.map((item) => (
            <SectionCard key={item.href}>
              <Link href={item.href} className="block">
                <p className="text-base font-semibold text-slate-800">{item.title}</p>
                <p className="mt-1 text-sm text-slate-500">{item.desc}</p>
                <p className="mt-3 text-xs text-emerald-600">进入配置 →</p>
              </Link>
            </SectionCard>
          ))}
        </section>
      </div>
    </div>
  );
}
