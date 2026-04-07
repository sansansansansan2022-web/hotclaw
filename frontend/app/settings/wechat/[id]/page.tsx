"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { getWeChatConfig, createWeChatConfig, updateWeChatConfig, testWeChatConnection } from "@/lib/api";

export default function WeChatSettingsPage() {
  const params = useParams<{ id: string }>();
  const accountId = params?.id ?? "";
  const [config, setConfig] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [appId, setAppId] = useState("");
  const [appSecret, setAppSecret] = useState("");
  const [defaultAuthor, setDefaultAuthor] = useState("");
  const [isEnabled, setIsEnabled] = useState(true);

  useEffect(() => {
    if (!accountId) return;
    loadConfig(accountId);
  }, [accountId]);

  async function loadConfig(id: string) {
    try {
      const data = await getWeChatConfig(id);
      setConfig(data as any);
      if (data) {
        setDefaultAuthor((data as any).default_author || "");
        setIsEnabled((data as any).is_enabled ?? true);
      }
    } catch (e) {
      // No config exists yet
      setConfig(null);
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      if (config) {
        await updateWeChatConfig(accountId, {
          app_id: appId || undefined,
          app_secret: appSecret || undefined,
          default_author: defaultAuthor || undefined,
          is_enabled: isEnabled,
        });
      } else {
        await createWeChatConfig({ account_id: accountId, app_id: appId, app_secret: appSecret, default_author: defaultAuthor || undefined, is_enabled: isEnabled });
      }
      setMessage("保存成功");
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败");
    }
  }

  async function test() {
    setError(null);
    setMessage(null);
    try {
      const res = await testWeChatConnection({ app_id: appId, app_secret: appSecret });
      setMessage(res.success ? "测试成功" : `测试失败：${res.message}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "测试失败");
    }
  }

  if (loading) return <div className="min-h-screen bg-[#F5F7FA] p-6">加载中...</div>;

  return (
    <div className="min-h-screen bg-[#F5F7FA] p-6">
      <div className="mx-auto max-w-3xl space-y-4">
        <div><Link href={`/accounts/${accountId}`} className="text-sm text-emerald-600">← 返回账号详情</Link></div>
        <PageHeader title="微信配置" subtitle="公众号接入与发布开关" />

        <SectionCard title="连接状态">
          {config ? (
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-500">AppID</p>
                <p className="font-mono text-slate-700">{config.app_id_masked}</p>
              </div>
              <StatusBadge status={config.is_enabled ? "success" : "discarded"} />
            </div>
          ) : (
            <p className="text-sm text-slate-500">尚未配置公众号凭据。</p>
          )}
        </SectionCard>

        <SectionCard title="配置表单">
          <div className="space-y-3">
            <label className="block text-sm"><span className="mb-1 block text-xs text-slate-500">AppID</span><input value={appId} onChange={(e) => setAppId(e.target.value)} className="w-full rounded-lg border border-slate-200 px-3 py-2" /></label>
            <label className="block text-sm"><span className="mb-1 block text-xs text-slate-500">AppSecret（不会明文回显）</span><input type="password" value={appSecret} onChange={(e) => setAppSecret(e.target.value)} className="w-full rounded-lg border border-slate-200 px-3 py-2" /></label>
            <label className="block text-sm"><span className="mb-1 block text-xs text-slate-500">默认作者</span><input value={defaultAuthor} onChange={(e) => setDefaultAuthor(e.target.value)} className="w-full rounded-lg border border-slate-200 px-3 py-2" /></label>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={isEnabled} onChange={(e) => setIsEnabled(e.target.checked)} />启用真实发布</label>

            {message ? <p className="text-sm text-emerald-600">{message}</p> : null}
            {error ? <p className="text-sm text-rose-600">{error}</p> : null}
            <div className="flex gap-2">
              <button onClick={save} className="rounded-lg bg-emerald-500 px-3 py-2 text-sm text-white">保存</button>
              <button onClick={test} className="rounded-lg border border-slate-200 px-3 py-2 text-sm">测试连接</button>
            </div>
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
