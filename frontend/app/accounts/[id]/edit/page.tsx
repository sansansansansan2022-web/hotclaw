"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { getAccount, updateAccount } from "@/lib/api";
import type { AccountCreateRequest } from "@/types";
import { AccountForm } from "@/components/console-ui/AccountForm";
import { PageHeader } from "@/components/console-ui";

export default function EditAccountPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const accountId = params?.id;
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<AccountCreateRequest>({ name: "", positioning: "", operation_mode: "manual", auto_run_enabled: false, auto_publish_enabled: false, is_active: true });

  useEffect(() => {
    if (!accountId) return;
    getAccount(accountId)
      .then((a) =>
        setForm({
          name: a.name,
          category: a.category ?? undefined,
          positioning: a.positioning,
          audience: a.audience ?? undefined,
          tone_style: a.tone_style ?? undefined,
          posting_frequency: a.posting_frequency ?? undefined,
          posting_time: a.posting_time ?? undefined,
          content_strategy: a.content_strategy ?? undefined,
          reference_accounts: a.reference_accounts ?? undefined,
          operation_mode: a.operation_mode,
          auto_run_enabled: a.auto_run_enabled,
          auto_publish_enabled: a.auto_publish_enabled,
          is_active: a.is_active,
          publish_paused: a.publish_paused,
          max_posts_per_day: a.max_posts_per_day ?? undefined,
          min_interval_minutes: a.min_interval_minutes ?? undefined,
        })
      )
      .catch((e) => setError(e instanceof Error ? e.message : "加载失败"))
      .finally(() => setLoading(false));
  }, [accountId]);

  function handleChange(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) {
    const { name, value, type } = e.target;
    setForm((prev) => ({ ...prev, [name]: type === "checkbox" ? (e.target as HTMLInputElement).checked : value || undefined }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!accountId) return;
    setSubmitting(true);
    setError(null);
    try {
      await updateAccount(accountId, form);
      router.push(`/accounts/${accountId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
      setSubmitting(false);
    }
  }

  if (loading) return <div className="min-h-screen bg-[#F5F7FA] p-6">加载中...</div>;

  return (
    <div className="min-h-screen bg-[#F5F7FA] p-6">
      <div className="mx-auto max-w-4xl">
        <div className="mb-4"><Link href={`/accounts/${accountId}`} className="text-sm text-emerald-600">← 返回账号详情</Link></div>
        <PageHeader title="编辑运营账号" subtitle="沿用创建页结构，支持分区编辑" />
        <form onSubmit={onSubmit}>
          <AccountForm form={form} onChange={handleChange} submitLabel="保存修改" submitting={submitting} error={error} />
        </form>
      </div>
    </div>
  );
}
