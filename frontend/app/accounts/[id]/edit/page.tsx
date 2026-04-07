"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { getAccount, updateAccount } from "@/lib/api";
import type { AccountCreateRequest } from "@/types";
import { AccountForm } from "@/components/console-ui/AccountForm";
import { PageHeader } from "@/components/console-ui";

export default function EditAccountPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const accountId = params?.id;

  // 状态管理
  // account: 原始账号数据（用于显示）
  // loading: 加载状态
  // submitting: 提交中状态
  // error: 错误信息
  // form: 表单数据
  const [account, setAccount] = useState<AccountDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<AccountCreateRequest>({ name: "", positioning: "", operation_mode: "manual", auto_run_enabled: false, auto_publish_enabled: false, is_active: true });

  useEffect(() => {
    if (!accountId) return;
    loadAccount();
  }, [accountId]);

  /**
   * loadAccount - 加载账号详情并填充表单
   *
   * 调用 API: getAccount(accountId)
   * 更新状态: account, form
   */
  async function loadAccount() {
    setLoading(true);
    try {
      if (!accountId) return;
      const data = await getAccount(accountId);
      setAccount(data);
      // 填充表单数据（将 null 转为 undefined）
      setForm({
        name: data.name,
        category: data.category ?? undefined,
        positioning: data.positioning,
        audience: data.audience ?? undefined,
        tone_style: data.tone_style ?? undefined,
        posting_frequency: data.posting_frequency ?? undefined,
        posting_time: data.posting_time ?? undefined,
        content_strategy: data.content_strategy ?? undefined,
        reference_accounts: data.reference_accounts ?? undefined,
        operation_mode: data.operation_mode,
        auto_run_enabled: data.auto_run_enabled,
        auto_publish_enabled: data.auto_publish_enabled,
        is_active: data.is_active,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  function handleChange(
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) {
    const { name, value, type } = e.target;
    setForm((prev) => ({ ...prev, [name]: type === "checkbox" ? (e.target as HTMLInputElement).checked : value || undefined }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!accountId) return;
    setSubmitting(true);
    setError(null);
    try {
      if (!accountId) return;
      await updateAccount(accountId, form);
      router.push(`/accounts/${params.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "更新失败");
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
