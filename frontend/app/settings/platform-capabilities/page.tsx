"use client";

import { useEffect, useMemo, useState } from "react";
import { Icon } from "@/components/console/icons";
import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Input,
  PageHeader,
  Select,
  SkeletonRows,
  StatCard,
  Tabs,
  Textarea,
} from "@/components/console/ui";
import {
  createPlatformCapability,
  deletePlatformCapability,
  listPlatformCapabilities,
  restorePlatformCapability,
  updatePlatformCapability,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ContentPlatform, PlatformCapability } from "@/types";

type PlatformFilter = "all" | ContentPlatform;
type CapabilityMode = "view" | "edit" | "create";
type NoticeTone = "success" | "danger" | "info";

interface NoticeState {
  tone: NoticeTone;
  message: string;
}

interface CapabilityFormState {
  capability_id: string;
  content_platform: ContentPlatform;
  capability_type: string;
  name: string;
  description: string;
  is_enabled: boolean;
  status: string;
  config_json: string;
  prompt_overrides_json: string;
}

type FieldErrors = Partial<Record<keyof CapabilityFormState, string>>;

const emptyForm: CapabilityFormState = {
  capability_id: "",
  content_platform: "wechat",
  capability_type: "",
  name: "",
  description: "",
  is_enabled: true,
  status: "active",
  config_json: "{}",
  prompt_overrides_json: "{}",
};

const platformTabs: Array<{ value: PlatformFilter; label: string }> = [
  { value: "all", label: "全部" },
  { value: "wechat", label: "微信" },
  { value: "xiaohongshu", label: "小红书" },
];

const platformLabels: Record<string, string> = {
  wechat: "微信",
  xiaohongshu: "小红书",
};

function formatJson(value: Record<string, unknown> | null | undefined) {
  return JSON.stringify(value && typeof value === "object" ? value : {}, null, 2);
}

function parseJsonObject(value: string, label: string): Record<string, unknown> {
  const text = value.trim();
  if (!text) return {};
  let parsed: unknown;
  try {
    parsed = JSON.parse(text) as unknown;
  } catch {
    throw new Error(`${label}不是有效 JSON。`);
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(`${label}必须是 JSON 对象。`);
  }
  return parsed as Record<string, unknown>;
}

function capabilityToForm(capability: PlatformCapability): CapabilityFormState {
  return {
    capability_id: capability.capability_id,
    content_platform: capability.content_platform === "xiaohongshu" ? "xiaohongshu" : "wechat",
    capability_type: capability.capability_type,
    name: capability.name,
    description: capability.description || "",
    is_enabled: capability.is_enabled,
    status: capability.status || "active",
    config_json: formatJson(capability.config_json),
    prompt_overrides_json: formatJson(capability.prompt_overrides_json),
  };
}

function sourceLabel(capability: PlatformCapability) {
  if (capability.source === "overridden") return "覆盖";
  if (capability.is_builtin) return "内置";
  return "自定义";
}

function sourceTone(capability: PlatformCapability) {
  if (capability.source === "overridden") return "warning" as const;
  if (capability.is_builtin) return "info" as const;
  return "success" as const;
}

function platformCapabilityErrorDescription(error: string) {
  if (error.includes("/api/v1/health") || error.includes("无法连接后端服务")) {
    return `${error} 恢复后请点击重试刷新。`;
  }
  return `${error} 如这是后端服务连接问题，请先启动后端服务，确认 /api/v1/health 可访问后再重试。`;
}

function NoticeBanner({ notice }: { notice: NoticeState | null }) {
  if (!notice) return null;

  const className =
    notice.tone === "success"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : notice.tone === "danger"
        ? "border-rose-200 bg-rose-50 text-rose-700"
        : "border-sky-200 bg-sky-50 text-sky-700";

  return <div className={cn("rounded-2xl border px-4 py-3 text-sm", className)}>{notice.message}</div>;
}

export default function PlatformCapabilitiesPage() {
  const [capabilities, setCapabilities] = useState<PlatformCapability[]>([]);
  const [selected, setSelected] = useState<PlatformCapability | null>(null);
  const [form, setForm] = useState<CapabilityFormState>(emptyForm);
  const [initialForm, setInitialForm] = useState<CapabilityFormState>(emptyForm);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [platformFilter, setPlatformFilter] = useState<PlatformFilter>("all");
  const [includeDeleted, setIncludeDeleted] = useState(false);
  const [mode, setMode] = useState<CapabilityMode>("view");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [restoreOpen, setRestoreOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<NoticeState | null>(null);

  const isEditing = mode === "edit" || mode === "create";
  const isDirty = useMemo(() => isEditing && JSON.stringify(form) !== JSON.stringify(initialForm), [form, initialForm, isEditing]);
  const actionBusy = saving || deleting || restoring;
  const activeEnabledCount = capabilities.filter((item) => item.status === "active" && item.is_enabled).length;
  const deletedCount = capabilities.filter((item) => item.status === "deleted").length;
  const builtinCount = capabilities.filter((item) => item.is_builtin).length;
  const customCount = capabilities.filter((item) => !item.is_builtin).length;
  const overrideCount = capabilities.filter((item) => item.source === "overridden").length;
  const createDisabled = actionBusy || loading || Boolean(error);

  function setField<K extends keyof CapabilityFormState>(key: K, value: CapabilityFormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
    setFieldErrors((current) => ({ ...current, [key]: undefined }));
  }

  function confirmDiscardChanges() {
    if (!isDirty) return true;
    return window.confirm("当前有未保存的修改，继续操作会丢弃这些内容。确定继续吗？");
  }

  async function loadCapabilities(preferredCapabilityId?: string) {
    setLoading(true);
    try {
      const response = await listPlatformCapabilities({
        contentPlatform: platformFilter === "all" ? undefined : platformFilter,
        includeDeleted,
      });
      const nextCapabilities = Array.isArray(response.capabilities) ? response.capabilities : [];
      setCapabilities(nextCapabilities);

      const nextSelected =
        nextCapabilities.find((item) => item.capability_id === preferredCapabilityId) ||
        nextCapabilities.find((item) => item.capability_id === selected?.capability_id) ||
        nextCapabilities[0] ||
        null;

      if (nextSelected) {
        const nextForm = capabilityToForm(nextSelected);
        setSelected(nextSelected);
        setForm(nextForm);
        setInitialForm(nextForm);
        setMode("view");
      } else {
        const nextForm = { ...emptyForm, content_platform: platformFilter === "all" ? "wechat" : platformFilter };
        setSelected(null);
        setForm(nextForm);
        setInitialForm(nextForm);
        setMode("view");
      }

      setError(null);
      setFieldErrors({});
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "无法加载平台内容能力。");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadCapabilities();
  }, [platformFilter, includeDeleted]);

  useEffect(() => {
    if (!isDirty) return;
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [isDirty]);

  function handleSelect(capability: PlatformCapability) {
    if (!confirmDiscardChanges()) return;
    const nextForm = capabilityToForm(capability);
    setSelected(capability);
    setForm(nextForm);
    setInitialForm(nextForm);
    setMode("view");
    setNotice(null);
    setFieldErrors({});
  }

  function handleCreate() {
    if (error) {
      setNotice({ tone: "danger", message: "平台能力尚未加载成功。请先恢复后端连接并刷新，再新增能力。" });
      return;
    }
    if (!confirmDiscardChanges()) return;
    const nextForm = {
      ...emptyForm,
      content_platform: platformFilter === "all" ? "wechat" : platformFilter,
    };
    setSelected(null);
    setForm(nextForm);
    setInitialForm(nextForm);
    setMode("create");
    setNotice(null);
    setFieldErrors({});
  }

  function handleCancel() {
    if (selected) {
      const nextForm = capabilityToForm(selected);
      setForm(nextForm);
      setInitialForm(nextForm);
      setMode("view");
      setFieldErrors({});
      return;
    }

    const firstCapability = capabilities[0];
    if (firstCapability) {
      handleSelect(firstCapability);
    } else {
      const nextForm = { ...emptyForm, content_platform: platformFilter === "all" ? "wechat" : platformFilter };
      setForm(nextForm);
      setInitialForm(nextForm);
      setMode("view");
      setFieldErrors({});
    }
  }

  async function handleSave() {
    const nextErrors: FieldErrors = {};
    const capabilityId = form.capability_id.trim();
    if (capabilityId && !/^[a-z0-9_.-]+$/.test(capabilityId)) {
      nextErrors.capability_id = "只能使用小写字母、数字、下划线、点和短横线；留空则自动生成。";
    }
    if (!form.capability_type.trim()) nextErrors.capability_type = "请填写能力类型。";
    if (!form.name.trim()) nextErrors.name = "请填写展示名称。";

    let configJson: Record<string, unknown> | null = null;
    let promptOverridesJson: Record<string, unknown> | null = null;
    try {
      configJson = parseJsonObject(form.config_json, "规则配置");
    } catch (jsonError) {
      nextErrors.config_json = jsonError instanceof Error ? jsonError.message : "规则配置不是有效 JSON。";
    }
    try {
      promptOverridesJson = parseJsonObject(form.prompt_overrides_json, "提示词调整");
    } catch (jsonError) {
      nextErrors.prompt_overrides_json = jsonError instanceof Error ? jsonError.message : "提示词调整不是有效 JSON。";
    }

    setFieldErrors(nextErrors);
    if (Object.keys(nextErrors).length || !configJson || !promptOverridesJson) {
      setNotice({ tone: "danger", message: "请先修正表单里的错误，再保存。" });
      return;
    }

    setSaving(true);
    try {
      if (mode === "create") {
        const created = await createPlatformCapability({
          capability_id: capabilityId || undefined,
          content_platform: form.content_platform,
          capability_type: form.capability_type.trim(),
          name: form.name.trim(),
          description: form.description.trim() || null,
          is_enabled: form.is_enabled,
          config_json: configJson,
          prompt_overrides_json: promptOverridesJson,
        });
        await loadCapabilities(created.capability_id);
        setNotice({ tone: "success", message: `已创建「${created.name}」。` });
      } else if (selected) {
        const updated = await updatePlatformCapability(selected.capability_id, {
          name: form.name.trim(),
          description: form.description.trim() || null,
          is_enabled: form.is_enabled,
          status: form.status,
          config_json: configJson,
          prompt_overrides_json: promptOverridesJson,
        });
        await loadCapabilities(updated.capability_id);
        setNotice({ tone: "success", message: `已保存「${updated.name}」。` });
      }
    } catch (saveError) {
      setNotice({
        tone: "danger",
        message: saveError instanceof Error ? saveError.message : "无法保存这个能力。",
      });
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!selected) return;

    setDeleting(true);
    try {
      const deleted = await deletePlatformCapability(selected.capability_id);
      setDeleteOpen(false);
      await loadCapabilities(includeDeleted ? deleted.capability_id : undefined);
      setNotice({ tone: "success", message: `已停用「${deleted.name}」。` });
    } catch (deleteError) {
      setNotice({
        tone: "danger",
        message: deleteError instanceof Error ? deleteError.message : "无法停用这个能力。",
      });
    } finally {
      setDeleting(false);
    }
  }

  async function handleRestore() {
    if (!selected) return;

    setRestoring(true);
    try {
      const restored = await restorePlatformCapability(selected.capability_id);
      setRestoreOpen(false);
      await loadCapabilities(restored.capability_id);
      setNotice({ tone: "success", message: `已恢复「${restored.name}」。` });
    } catch (restoreError) {
      setNotice({
        tone: "danger",
        message: restoreError instanceof Error ? restoreError.message : "无法恢复这个能力。",
      });
    } finally {
      setRestoring(false);
    }
  }

  function handleFormatJson(field: "config_json" | "prompt_overrides_json", label: string) {
    try {
      const formatted = formatJson(parseJsonObject(form[field], label));
      setField(field, formatted);
      setFieldErrors((current) => ({ ...current, [field]: undefined }));
    } catch (formatError) {
      setFieldErrors((current) => ({
        ...current,
        [field]: formatError instanceof Error ? formatError.message : `${label}不是有效 JSON。`,
      }));
    }
  }

  return (
    <>
      <div className="space-y-8">
        <PageHeader
          eyebrow="运营规则"
          title="平台内容能力"
          description="控制不同平台的选题、账号分析、排版和发布准备规则"
          actions={
            <>
              <Button
                variant="secondary"
                onClick={() => {
                  if (confirmDiscardChanges()) void loadCapabilities(selected?.capability_id);
                }}
                disabled={actionBusy}
              >
                <Icon name="refresh" className="h-4 w-4" />
                刷新
              </Button>
              <div className="flex flex-col items-start gap-1 sm:items-end">
                <Button
                  onClick={handleCreate}
                  disabled={createDisabled}
                  title={error ? "请先恢复后端连接并刷新成功后再新增能力。" : undefined}
                >
                  <Icon name="plus" className="h-4 w-4" />
                  新增能力
                </Button>
                {error ? <p className="max-w-60 text-xs leading-5 text-slate-500">加载失败时暂不能新增，请先刷新确认后端可用。</p> : null}
              </div>
            </>
          }
        />

        {loading ? (
          <SkeletonRows rows={5} />
        ) : error ? (
          <ErrorState
            title="平台内容能力加载失败"
            description={platformCapabilityErrorDescription(error)}
            retry={() => {
              if (confirmDiscardChanges()) void loadCapabilities(selected?.capability_id);
            }}
          />
        ) : (
          <>
            <div className="grid gap-5 md:grid-cols-4">
              <StatCard
                label="当前能力"
                value={String(capabilities.length)}
                hint="当前筛选下可查看的能力数量。"
                tone="info"
                icon={<Icon name="settings" className="h-6 w-6" />}
              />
              <StatCard
                label="已启用"
                value={String(activeEnabledCount)}
                hint="可参与运营规则匹配。"
                tone="success"
                icon={<Icon name="check" className="h-6 w-6" />}
              />
              <StatCard
                label="系统预设"
                value={String(builtinCount)}
                hint={`${overrideCount} 个已有运营调整。`}
                tone="warning"
                icon={<Icon name="workspace" className="h-6 w-6" />}
              />
              <StatCard
                label="自定义 / 已停用"
                value={`${customCount} / ${deletedCount}`}
                hint="人工新增和可恢复的停用记录。"
                tone={deletedCount ? "danger" : "brand"}
                icon={<Icon name="drafts" className="h-6 w-6" />}
              />
            </div>

            <Card title="筛选" description="按平台查看能力，也可以临时查看已停用的能力。">
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <Tabs
                  value={platformFilter}
                  onChange={(value) => {
                    if (value === platformFilter) return;
                    if (confirmDiscardChanges()) setPlatformFilter(value);
                  }}
                  items={platformTabs}
                />
                <label className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3 text-sm text-slate-600">
                  <input
                    type="checkbox"
                    checked={includeDeleted}
                    onChange={(event) => {
                      if (confirmDiscardChanges()) {
                        setIncludeDeleted(event.target.checked);
                      }
                    }}
                    className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-200"
                  />
                  <span className="font-medium text-slate-900">查看已停用能力</span>
                </label>
              </div>
            </Card>

            <div className="grid gap-6 xl:grid-cols-[0.95fr_1.25fr]">
              <Card title="能力列表" description="选择一个平台能力，查看或调整它的运营规则。">
                {capabilities.length ? (
                  <div className="space-y-3">
                    {capabilities.map((capability) => {
                      const active = selected?.capability_id === capability.capability_id && mode !== "create";
                      const deleted = capability.status === "deleted";
                      return (
                        <button
                          key={capability.capability_id}
                          type="button"
                          onClick={() => handleSelect(capability)}
                          className={cn(
                            "w-full rounded-2xl border p-4 text-left transition",
                            active
                              ? "border-brand-200 bg-brand-50"
                              : "border-slate-200 bg-white hover:border-brand-200 hover:bg-brand-50/50",
                            deleted ? "opacity-75" : "",
                          )}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="truncate text-sm font-semibold text-slate-900">{capability.name}</p>
                              <p className="mt-1 truncate text-xs text-slate-500">{capability.capability_id}</p>
                            </div>
                            <div className="flex flex-wrap justify-end gap-2">
                              <Badge tone="muted">{platformLabels[capability.content_platform] || capability.content_platform}</Badge>
                              <Badge tone="neutral">{capability.capability_type}</Badge>
                            </div>
                          </div>
                          <p className="mt-3 line-clamp-2 text-sm leading-6 text-slate-500">
                            {capability.description || "暂未填写说明。"}
                          </p>
                          <div className="mt-4 flex flex-wrap gap-2">
                            <Badge tone={capability.is_enabled && !deleted ? "success" : "muted"}>
                              {capability.is_enabled && !deleted ? "已启用" : "未启用"}
                            </Badge>
                            <Badge tone={sourceTone(capability)}>{sourceLabel(capability)}</Badge>
                            <Badge tone={deleted ? "danger" : "success"}>{deleted ? "已停用" : "正常"}</Badge>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <EmptyState
                    title="没有找到能力"
                    description="当前筛选条件下没有匹配的平台能力。"
                    action={
                      <Button onClick={handleCreate}>
                        <Icon name="plus" className="h-4 w-4" />
                        新增能力
                      </Button>
                    }
                  />
                )}
              </Card>

              <div className="space-y-6">
                <NoticeBanner notice={notice} />

                {selected || mode === "create" ? (
                  <>
                    <Card
                      title={mode === "create" ? "新增平台能力" : "能力配置"}
                      description="调整这个能力在平台内容生产中的名称、说明、状态和规则。"
                      action={
                        <div className="flex flex-wrap gap-2">
                          {isEditing ? (
                            <>
                              <Button variant="secondary" onClick={handleCancel} disabled={actionBusy}>
                                取消
                              </Button>
                              <Button onClick={() => void handleSave()} disabled={actionBusy}>
                                {saving ? "保存中..." : mode === "create" ? "创建能力" : "保存修改"}
                              </Button>
                            </>
                          ) : (
                            <>
                              {selected?.status === "deleted" ? (
                                <Button variant="secondary" onClick={() => setRestoreOpen(true)} disabled={actionBusy}>
                                  恢复
                                </Button>
                              ) : null}
                              {selected ? (
                                <Button variant="secondary" onClick={() => setMode("edit")} disabled={actionBusy}>
                                  <Icon name="edit" className="h-4 w-4" />
                                  编辑
                                </Button>
                              ) : null}
                            </>
                          )}
                        </div>
                      }
                    >
                      <div className="grid gap-5">
                        <div className="grid gap-5 md:grid-cols-2">
                          <div>
                            <label className="mb-2 block text-sm font-medium text-slate-700">能力 ID</label>
                            <Input
                              value={form.capability_id}
                              onChange={(event) => setField("capability_id", event.target.value)}
                              disabled={mode !== "create"}
                              placeholder="wechat.custom.my_capability"
                              aria-invalid={Boolean(fieldErrors.capability_id)}
                            />
                            <p className="mt-2 text-xs leading-5 text-slate-500">
                              可留空自动生成；手填仅支持小写字母、数字、下划线、点和短横线。
                            </p>
                            {fieldErrors.capability_id ? (
                              <p className="mt-2 text-sm text-rose-600">{fieldErrors.capability_id}</p>
                            ) : null}
                          </div>
                          <div>
                            <label className="mb-2 block text-sm font-medium text-slate-700">平台</label>
                            <Select
                              value={form.content_platform}
                              onChange={(event) => setField("content_platform", event.target.value as ContentPlatform)}
                              disabled={mode !== "create"}
                            >
                              <option value="wechat">微信</option>
                              <option value="xiaohongshu">小红书</option>
                            </Select>
                          </div>
                        </div>

                        <div className="grid gap-5 md:grid-cols-2">
                          <div>
                            <label className="mb-2 block text-sm font-medium text-slate-700">能力类型</label>
                            <Input
                              value={form.capability_type}
                              onChange={(event) => setField("capability_type", event.target.value)}
                              disabled={mode !== "create"}
                              placeholder="recommendation"
                              aria-invalid={Boolean(fieldErrors.capability_type)}
                            />
                            {fieldErrors.capability_type ? (
                              <p className="mt-2 text-sm text-rose-600">{fieldErrors.capability_type}</p>
                            ) : null}
                          </div>
                          <div>
                            <label className="mb-2 block text-sm font-medium text-slate-700">展示名称</label>
                            <Input
                              value={form.name}
                              onChange={(event) => setField("name", event.target.value)}
                              disabled={!isEditing}
                              placeholder="例如：小红书选题规则"
                              aria-invalid={Boolean(fieldErrors.name)}
                            />
                            {fieldErrors.name ? <p className="mt-2 text-sm text-rose-600">{fieldErrors.name}</p> : null}
                          </div>
                        </div>

                        <div>
                          <label className="mb-2 block text-sm font-medium text-slate-700">说明</label>
                          <Textarea
                            value={form.description}
                            onChange={(event) => setField("description", event.target.value)}
                            disabled={!isEditing}
                            className="min-h-24"
                            placeholder="说明这项能力适用的运营场景。"
                          />
                        </div>

                        <div className="grid gap-4 md:grid-cols-2">
                          <label className="flex items-center justify-between rounded-2xl border border-slate-200 p-4">
                            <span>
                              <span className="block text-sm font-medium text-slate-900">启用能力</span>
                              <span className="text-sm text-slate-500">启用后会参与内容生产规则匹配。</span>
                            </span>
                            <input
                              type="checkbox"
                              checked={form.is_enabled}
                              onChange={(event) => setField("is_enabled", event.target.checked)}
                              disabled={!isEditing}
                              className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-200"
                            />
                          </label>
                          <div>
                            <label className="mb-2 block text-sm font-medium text-slate-700">状态</label>
                            <Select
                              value={form.status}
                              onChange={(event) => setField("status", event.target.value)}
                              disabled={!isEditing || mode === "create"}
                            >
                              <option value="active">正常</option>
                              <option value="deleted">已停用</option>
                            </Select>
                          </div>
                        </div>

                        <details
                          {...(fieldErrors.config_json || fieldErrors.prompt_overrides_json ? { open: true } : {})}
                          className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4"
                        >
                          <summary className="cursor-pointer text-sm font-semibold text-slate-900">高级设置</summary>
                          <div className="mt-5 grid gap-5">
                            <div>
                              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                                <label className="block text-sm font-medium text-slate-700">规则配置 JSON</label>
                                <Button
                                  variant="secondary"
                                  size="sm"
                                  onClick={() => handleFormatJson("config_json", "规则配置")}
                                  disabled={!isEditing}
                                >
                                  格式化 JSON
                                </Button>
                              </div>
                              <Textarea
                                value={form.config_json}
                                onChange={(event) => setField("config_json", event.target.value)}
                                disabled={!isEditing}
                                className="min-h-[220px] font-mono"
                                spellCheck={false}
                                aria-invalid={Boolean(fieldErrors.config_json)}
                              />
                              {fieldErrors.config_json ? (
                                <p className="mt-2 text-sm text-rose-600">{fieldErrors.config_json}</p>
                              ) : null}
                            </div>

                            <div>
                              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                                <label className="block text-sm font-medium text-slate-700">提示词调整 JSON</label>
                                <Button
                                  variant="secondary"
                                  size="sm"
                                  onClick={() => handleFormatJson("prompt_overrides_json", "提示词调整")}
                                  disabled={!isEditing}
                                >
                                  格式化 JSON
                                </Button>
                              </div>
                              <Textarea
                                value={form.prompt_overrides_json}
                                onChange={(event) => setField("prompt_overrides_json", event.target.value)}
                                disabled={!isEditing}
                                className="min-h-[220px] font-mono"
                                spellCheck={false}
                                aria-invalid={Boolean(fieldErrors.prompt_overrides_json)}
                              />
                              {fieldErrors.prompt_overrides_json ? (
                                <p className="mt-2 text-sm text-rose-600">{fieldErrors.prompt_overrides_json}</p>
                              ) : null}
                            </div>
                          </div>
                        </details>
                      </div>
                    </Card>

                    {selected ? (
                      <div className="grid gap-6 md:grid-cols-2">
                        <Card title="当前状态" description="这个能力当前保存的来源、平台和状态信息。">
                          <div className="grid gap-4 text-sm text-slate-600">
                            <div className="flex items-center justify-between gap-4">
                              <span className="text-slate-500">平台</span>
                              <Badge tone="muted">
                                {platformLabels[selected.content_platform] || selected.content_platform}
                              </Badge>
                            </div>
                            <div className="flex items-center justify-between gap-4">
                              <span className="text-slate-500">类型</span>
                              <span className="font-medium text-slate-900">{selected.capability_type}</span>
                            </div>
                            <div className="flex items-center justify-between gap-4">
                              <span className="text-slate-500">来源</span>
                              <Badge tone={sourceTone(selected)}>{sourceLabel(selected)}</Badge>
                            </div>
                            <div className="flex items-center justify-between gap-4">
                              <span className="text-slate-500">状态</span>
                              <Badge tone={selected.status === "deleted" ? "danger" : "success"}>
                                {selected.status === "deleted" ? "已停用" : "正常"}
                              </Badge>
                            </div>
                          </div>
                        </Card>

                        <Card
                          title="能力管理"
                          description="停用后不会参与内容生产，但仍可在这里恢复。"
                          action={
                            selected.status === "deleted" ? (
                              <Button variant="secondary" onClick={() => setRestoreOpen(true)} disabled={actionBusy}>
                                恢复
                              </Button>
                            ) : (
                              <Button variant="destructive" onClick={() => setDeleteOpen(true)} disabled={actionBusy}>
                                停用
                              </Button>
                            )
                          }
                        >
                          <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 text-sm text-slate-600">
                            <p className="font-medium text-slate-900">{selected.capability_id}</p>
                            <p className="mt-2">创建时间：{selected.created_at || "N/A"}</p>
                            <p className="mt-1">更新时间：{selected.updated_at || "N/A"}</p>
                          </div>
                        </Card>
                      </div>
                    ) : null}
                  </>
                ) : (
                  <Card title="能力配置" description="请选择一个能力，或新增一条平台能力。">
                    <EmptyState
                      title="请选择能力"
                      description="从左侧列表选择一项，或新增自定义能力。"
                    />
                  </Card>
                )}
              </div>
            </div>
          </>
        )}
      </div>

      <ConfirmDialog
        open={deleteOpen}
        title="停用平台能力"
        description={`确定要停用「${selected?.name ?? "当前能力"}」吗？停用后它不会参与内容生产，但可以恢复。`}
        confirmLabel="停用"
        cancelLabel="取消"
        tone="danger"
        confirmDisabled={deleting}
        confirmLoading={deleting}
        onConfirm={() => void handleDelete()}
        onCancel={() => {
          if (!deleting) setDeleteOpen(false);
        }}
      />

      <ConfirmDialog
        open={restoreOpen}
        title="恢复平台能力"
        description={`确定要恢复「${selected?.name ?? "当前能力"}」吗？恢复后它会重新进入平台内容能力列表。`}
        confirmLabel="恢复"
        cancelLabel="取消"
        confirmDisabled={restoring}
        confirmLoading={restoring}
        onConfirm={() => void handleRestore()}
        onCancel={() => {
          if (!restoring) setRestoreOpen(false);
        }}
      />
    </>
  );
}
