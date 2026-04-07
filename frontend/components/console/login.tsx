"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button, Input } from "@/components/console/ui";
import { Icon } from "@/components/console/icons";
import { useI18n } from "@/lib/i18n";
import { useAppStore } from "@/store/appStore";

export function LoginPage() {
  const { locale, t } = useI18n();
  const router = useRouter();
  const signIn = useAppStore((state) => state.signIn);
  const [mode, setMode] = useState<"email" | "wechat">("email");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const submit = () => {
    const resolvedEmail = email.trim() || "operator@hotclaw.dev";
    signIn(resolvedEmail);
    router.push("/dashboard");
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(34,197,94,0.18),_transparent_28%),_#f5f7f2] px-4 py-8 lg:px-8">
      <div className="mx-auto grid min-h-[720px] w-full max-w-7xl overflow-hidden rounded-[32px] border border-white/70 bg-white shadow-[0_40px_120px_-48px_rgba(15,23,42,0.3)] lg:grid-cols-2">
        <div className="relative overflow-hidden bg-[linear-gradient(135deg,_#16a34a,_#15803d)] p-10 text-white lg:p-16">
          <div className="absolute inset-0 opacity-30">
            <div className="absolute left-16 top-16 h-56 w-56 rounded-full bg-white/25 blur-3xl" />
            <div className="absolute bottom-12 right-8 h-72 w-72 rounded-full bg-white/20 blur-3xl" />
          </div>
          <div className="relative z-10 flex h-full flex-col justify-between">
            <div>
              <div className="mb-12 flex items-center gap-4">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white text-brand-600 shadow-lg">
                  <Icon name="paw" className="h-7 w-7" />
                </div>
                <div>
                  <p className="text-3xl font-semibold tracking-tight">HotClaw</p>
                  <p className="text-sm text-brand-100">{locale === "zh-CN" ? "微信公众号内容运营" : "WeChat Content Operations"}</p>
                </div>
              </div>
              <h1 className="max-w-lg text-4xl font-semibold leading-tight lg:text-5xl">{locale === "zh-CN" ? "用后端联动工作流管理 AI 驱动的公众号运营。" : "AI-powered WeChat management with backend-connected workflows."}</h1>
              <p className="mt-6 max-w-xl text-lg leading-8 text-brand-50">
                {locale === "zh-CN"
                  ? "在一个生产控制台里协同账号、草稿、发布审核和六 Agent 任务编排。"
                  : "Coordinate accounts, drafts, publish reviews and six-agent task orchestration from one production console."}
              </p>
            </div>

            <div className="space-y-5">
              {[
                locale === "zh-CN" ? "多账号调度与账号详情工作流" : "Multi-account scheduling and account detail workflows",
                locale === "zh-CN" ? "带状态约束的草稿收件箱与审核控制" : "Draft inbox with status-accurate review controls",
                locale === "zh-CN" ? "任务历史、发布日志和微信配置统一入口" : "Task history, publish logs and WeChat config in one surface",
              ].map((item) => (
                <div key={item} className="flex items-start gap-3">
                  <div className="mt-1 flex h-6 w-6 items-center justify-center rounded-lg bg-white/20">
                    <Icon name="check" className="h-4 w-4" />
                  </div>
                  <p className="text-sm text-brand-50">{item}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="flex items-center p-8 lg:p-16">
          <div className="mx-auto w-full max-w-md">
            <div className="mb-8">
              <h2 className="text-3xl font-semibold tracking-tight text-slate-950">{locale === "zh-CN" ? "欢迎回来" : "Welcome back"}</h2>
              <p className="mt-2 text-sm text-slate-500">{locale === "zh-CN" ? "在接入正式认证 API 前，这个版本先使用本地会话适配层。" : "This build uses a local session adapter until a dedicated auth API is connected."}</p>
            </div>

            <div className="mb-8 grid grid-cols-2 gap-2 rounded-2xl bg-slate-100 p-1.5">
              <button type="button" onClick={() => setMode("email")} className={`rounded-xl px-4 py-3 text-sm font-medium transition ${mode === "email" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500"}`}>
                {locale === "zh-CN" ? "邮箱登录" : "Email Login"}
              </button>
              <button type="button" onClick={() => setMode("wechat")} className={`rounded-xl px-4 py-3 text-sm font-medium transition ${mode === "wechat" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500"}`}>
                {locale === "zh-CN" ? "微信扫码" : "WeChat Scan"}
              </button>
            </div>

            {mode === "email" ? (
              <div className="space-y-5">
                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-700">{locale === "zh-CN" ? "邮箱地址" : "Email address"}</label>
                  <Input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" />
                </div>
                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-700">{locale === "zh-CN" ? "密码" : "Password"}</label>
                  <Input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder={locale === "zh-CN" ? "本地适配模式下可输入任意密码" : "Enter any password for local adapter mode"} />
                </div>
                <Button className="w-full" onClick={submit}>
                  {locale === "zh-CN" ? "登录" : "Sign In"}
                </Button>
              </div>
            ) : (
              <div className="space-y-5">
                <div className="flex flex-col items-center rounded-[28px] border border-dashed border-slate-300 bg-slate-50 px-6 py-10 text-center">
                  <div className="flex h-48 w-48 items-center justify-center rounded-[28px] border border-slate-200 bg-white shadow-sm">
                    <div>
                      <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-50 text-brand-600">
                        <Icon name="paw" className="h-8 w-8" />
                      </div>
                      <p className="mt-4 text-sm font-medium text-slate-900">{locale === "zh-CN" ? "二维码占位" : "QR placeholder"}</p>
                      <p className="mt-1 text-xs text-slate-500">{locale === "zh-CN" ? "微信登录还没有接入后端。" : "WeChat login is not wired to the backend yet."}</p>
                    </div>
                  </div>
                  <p className="mt-5 text-sm text-slate-500">{locale === "zh-CN" ? "现在可以先使用邮箱模式进入本地会话。" : "Use email mode to continue with the local session adapter."}</p>
                </div>
                <Button variant="secondary" className="w-full" onClick={() => setMode("email")}>
                  {locale === "zh-CN" ? "改用邮箱登录" : "Use Email Instead"}
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
