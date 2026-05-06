"use client";

import type { AccountCreateRequest } from "@/types";
import { SectionCard } from "./index";

export function AccountForm({
  form,
  onChange,
  submitLabel,
  submitting,
  error,
}: {
  form: AccountCreateRequest;
  onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => void;
  submitLabel: string;
  submitting: boolean;
  error?: string | null;
}) {
  return (
    <div className="space-y-4">
      {error ? <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div> : null}

      <SectionCard title="Step 1 · 公众号接入状态">
        <p className="text-sm text-slate-500">如需真实发布，请在账号创建后前往微信配置绑定 AppID / AppSecret。</p>
      </SectionCard>

      <SectionCard title="Step 2 · 基本信息">
        <div className="grid gap-3 md:grid-cols-2">
          <Input label="账号名称*" name="name" value={form.name ?? ""} onChange={onChange} />
          <Input label="账号类别" name="category" value={form.category ?? ""} onChange={onChange} />
          <TextArea className="md:col-span-2" label="账号定位*" name="positioning" value={form.positioning ?? ""} onChange={onChange} rows={4} />
        </div>
      </SectionCard>

      <SectionCard title="受众与风格">
        <div className="grid gap-3 md:grid-cols-2">
          <Input label="目标读者" name="audience" value={form.audience ?? ""} onChange={onChange} />
          <Input label="风格调性" name="tone_style" value={form.tone_style ?? ""} onChange={onChange} />
        </div>
      </SectionCard>

      <SectionCard title="发布策略">
        <div className="grid gap-3 md:grid-cols-2">
          <Select
            label="发布频率"
            name="posting_frequency"
            value={form.posting_frequency ?? ""}
            onChange={onChange}
            options={[
              ["", "不设置"],
              ["daily", "每日"],
              ["weekly", "每周"],
              ["biweekly", "每两周"],
              ["monthly", "每月"],
            ]}
          />
          <Input label="发布时间" name="posting_time" value={form.posting_time ?? ""} onChange={onChange} type="time" />
          <TextArea className="md:col-span-2" label="内容策略" name="content_strategy" value={form.content_strategy ?? ""} onChange={onChange} rows={3} />
          <Input className="md:col-span-2" label="参考公众号" name="reference_accounts" value={form.reference_accounts ?? ""} onChange={onChange} />
        </div>
      </SectionCard>

      <SectionCard title="运行模式">
        <div className="grid gap-3 md:grid-cols-2">
          <Select
            label="运行模式"
            name="operation_mode"
            value={form.operation_mode ?? "manual"}
            onChange={onChange}
            options={[["manual", "manual"], ["semi_auto", "semi_auto"], ["full_auto", "full_auto"]]}
          />
          <div className="space-y-2 rounded-lg border border-slate-200 p-3 text-sm">
            <label className="flex items-center gap-2"><input name="auto_run_enabled" checked={!!form.auto_run_enabled} onChange={onChange} type="checkbox" />自动运行</label>
            <label className="flex items-center gap-2"><input name="auto_publish_enabled" checked={!!form.auto_publish_enabled} onChange={onChange} type="checkbox" />自动发布</label>
            <label className="flex items-center gap-2"><input name="is_active" checked={!!form.is_active} onChange={onChange} type="checkbox" />创建后启用</label>
          </div>
        </div>
      </SectionCard>

      <button type="submit" disabled={submitting} className="rounded-lg bg-emerald-500 px-4 py-2 text-sm text-white disabled:opacity-60">
        {submitting ? "提交中..." : submitLabel}
      </button>
    </div>
  );
}

function Input({ label, className = "", ...props }: any) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-1 block text-xs text-slate-500">{label}</span>
      <input {...props} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-emerald-400" />
    </label>
  );
}

function TextArea({ label, className = "", ...props }: any) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-1 block text-xs text-slate-500">{label}</span>
      <textarea {...props} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-emerald-400" />
    </label>
  );
}

function Select({ label, options, className = "", ...props }: any) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-1 block text-xs text-slate-500">{label}</span>
      <select {...props} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-emerald-400">
        {options.map(([v, l]: [string, string]) => <option value={v} key={v}>{l}</option>)}
      </select>
    </label>
  );
}
