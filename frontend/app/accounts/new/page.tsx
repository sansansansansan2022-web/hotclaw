"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createAccount } from "@/lib/api";
import type { AccountCreateRequest } from "@/types";
import { AccountForm } from "@/components/console-ui/AccountForm";
import { PageHeader } from "@/components/console-ui";

export default function NewAccountPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<AccountCreateRequest>({ name: "", positioning: "", operation_mode: "manual", auto_run_enabled: false, auto_publish_enabled: false, is_active: true });

  function handleChange(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) {
    const { name, value, type } = e.target;
    setForm((prev) => ({ ...prev, [name]: type === "checkbox" ? (e.target as HTMLInputElement).checked : value || undefined }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!form.name?.trim() || !form.positioning?.trim()) {
      setError("请填写账号名称和定位");
      return;
    }
    setSubmitting(true);
    try {
      const res = await createAccount(form);
      router.push(`/accounts/${res.account_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建失败");
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#F5F7FA] p-6">
      <div className="mx-auto max-w-4xl">
        <div className="mb-4"><Link href="/accounts" className="text-sm text-emerald-600">← 返回账号管理</Link></div>
        <PageHeader title="新建运营账号" subtitle="两步式创建：接入说明 + 运营配置" />
        <form onSubmit={onSubmit}>
          <AccountForm form={form} onChange={handleChange} submitLabel="创建账号" submitting={submitting} error={error} />
        </form>
      </div>
    </div>
  );
}
