"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { createWeChatConfig, getWeChatConfig, listAccounts, testWeChatConnection, updateWeChatConfig } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { AccountSummary, WeChatConfigCreate, WeChatConfigDetail, WeChatConfigUpdate } from "@/types";
import { Badge, Button, Card, EmptyState, ErrorState, Input, PageHeader, Select, SkeletonRows } from "@/components/console/ui";
import { useAppStore } from "@/store/appStore";

interface ConfigFormState {
  app_id: string;
  app_secret: string;
  default_author: string;
  default_thumb_media_id: string;
  need_open_comment: boolean;
  only_fans_can_comment: boolean;
  is_enabled: boolean;
}

const emptyForm: ConfigFormState = {
  app_id: "",
  app_secret: "",
  default_author: "",
  default_thumb_media_id: "",
  need_open_comment: true,
  only_fans_can_comment: false,
  is_enabled: true,
};

export function WeChatConfigPage({ accountId }: { accountId?: string }) {
  const { locale, t, token } = useI18n();
  const router = useRouter();
  const pushToast = useAppStore((state) => state.pushToast);
  const [accounts, setAccounts] = useState<AccountSummary[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(accountId ?? null);
  const [existing, setExisting] = useState<WeChatConfigDetail | null>(null);
  const [form, setForm] = useState<ConfigFormState>(emptyForm);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadedAccountId, setLoadedAccountId] = useState<string | null>(null);
  const loadRequestRef = useRef(0);

  const load = async (targetAccountId?: string | null) => {
    const requestId = loadRequestRef.current + 1;
    loadRequestRef.current = requestId;
    try {
      setLoading(true);
      setError(null);
      setExisting(null);
      setForm(emptyForm);
      setLoadedAccountId(null);
      const accountsRes = await listAccounts(1, 100).catch(() => ({ accounts: [], pagination: { page: 1, page_size: 100, total: 0 } }));
      if (loadRequestRef.current !== requestId) return;
      setAccounts(accountsRes.accounts);

      const resolvedAccountId = targetAccountId ?? accountId ?? accountsRes.accounts[0]?.account_id ?? null;
      setSelectedAccountId(resolvedAccountId);

      if (!resolvedAccountId) {
        setExisting(null);
        setForm(emptyForm);
        setLoadedAccountId(null);
        return;
      }

      try {
        const config = await getWeChatConfig(resolvedAccountId);
        if (loadRequestRef.current !== requestId) return;
        setExisting(config);
        setForm({
          app_id: "",
          app_secret: "",
          default_author: config.default_author ?? "",
          default_thumb_media_id: config.default_thumb_media_id ?? "",
          need_open_comment: config.need_open_comment,
          only_fans_can_comment: config.only_fans_can_comment,
          is_enabled: config.is_enabled,
        });
        setLoadedAccountId(resolvedAccountId);
      } catch {
        if (loadRequestRef.current !== requestId) return;
        setExisting(null);
        setForm(emptyForm);
        setLoadedAccountId(resolvedAccountId);
      }
    } catch (loadError) {
      if (loadRequestRef.current !== requestId) return;
      setError(loadError instanceof Error ? loadError.message : t("wechat.loadError"));
    } finally {
      if (loadRequestRef.current === requestId) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    void load(accountId ?? null);
  }, [accountId]);

  const selectedAccount = useMemo(() => accounts.find((account) => account.account_id === selectedAccountId) ?? null, [accounts, selectedAccountId]);
  const formReady = Boolean(selectedAccountId && selectedAccountId === loadedAccountId && !loading);

  const setField = <K extends keyof ConfigFormState>(key: K, value: ConfigFormState[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const submit = async () => {
    if (!selectedAccountId) return;
    if (!formReady) {
      pushToast({
        tone: "warning",
        title: locale === "zh-CN" ? "配置仍在加载" : "Configuration still loading",
        message: locale === "zh-CN" ? "请等待当前账号配置加载完成后再保存。" : "Wait for the selected account configuration to finish loading before saving.",
      });
      return;
    }
    try {
      setSaving(true);
      setError(null);
      if (existing) {
        const payload: WeChatConfigUpdate = {
          app_id: form.app_id || undefined,
          app_secret: form.app_secret || undefined,
          default_author: form.default_author || undefined,
          default_thumb_media_id: form.default_thumb_media_id || undefined,
          need_open_comment: form.need_open_comment,
          only_fans_can_comment: form.only_fans_can_comment,
          is_enabled: form.is_enabled,
        };
        await updateWeChatConfig(selectedAccountId, payload);
        pushToast({ tone: "success", title: locale === "zh-CN" ? "微信配置已更新" : "WeChat config updated", message: locale === "zh-CN" ? "账号配置已成功保存。" : "The account configuration was saved." });
      } else {
        if (!form.app_id || !form.app_secret) {
          pushToast({ tone: "warning", title: locale === "zh-CN" ? "需要凭证" : "Credentials required", message: locale === "zh-CN" ? "创建新配置时必须填写 App ID 和 App Secret。" : "App ID and App Secret are required when creating a new config." });
          return;
        }
        const payload: WeChatConfigCreate = {
          account_id: selectedAccountId,
          app_id: form.app_id,
          app_secret: form.app_secret,
          default_author: form.default_author || undefined,
          default_thumb_media_id: form.default_thumb_media_id || undefined,
          need_open_comment: form.need_open_comment,
          only_fans_can_comment: form.only_fans_can_comment,
          is_enabled: form.is_enabled,
        };
        await createWeChatConfig(payload);
        pushToast({ tone: "success", title: locale === "zh-CN" ? "微信配置已创建" : "WeChat config created", message: locale === "zh-CN" ? "该账号现在已经绑定微信配置。" : "The account is now bound to a WeChat config." });
      }
      await load(selectedAccountId);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : (locale === "zh-CN" ? "无法保存微信配置" : "Unable to save WeChat config"));
    } finally {
      setSaving(false);
    }
  };

  const runConnectionTest = async () => {
    if (!form.app_id || !form.app_secret) {
      pushToast({ tone: "warning", title: locale === "zh-CN" ? "需要凭证" : "Credentials required", message: locale === "zh-CN" ? "测试连接前请先填写 App ID 和 App Secret。" : "Enter App ID and App Secret to test the connection." });
      return;
    }
    try {
      const result = await testWeChatConnection({ app_id: form.app_id, app_secret: form.app_secret });
      pushToast({
        tone: result.success ? "success" : "danger",
        title: result.success ? (locale === "zh-CN" ? "连接成功" : "Connection successful") : (locale === "zh-CN" ? "连接失败" : "Connection failed"),
        message: result.message,
      });
    } catch (testError) {
      pushToast({
        tone: "danger",
        title: locale === "zh-CN" ? "连接测试失败" : "Connection test failed",
        message: testError instanceof Error ? testError.message : (locale === "zh-CN" ? "发生了意外错误" : "Unexpected error"),
      });
    }
  };

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={locale === "zh-CN" ? "微信投递" : "WeChat Delivery"}
        title={locale === "zh-CN" ? "微信配置" : "WeChat Config"}
        description={locale === "zh-CN" ? "绑定或更新微信公众号凭证、默认发布设置和连通性检查。" : "Bind or update WeChat official account credentials, default publish settings and connectivity checks."}
      />

      {loading ? (
        <SkeletonRows rows={5} />
      ) : error ? (
        <ErrorState title={locale === "zh-CN" ? "微信配置加载失败" : "WeChat config failed to load"} description={error} retry={() => void load(selectedAccountId)} />
      ) : accounts.length ? (
        <>
          <Card title={locale === "zh-CN" ? "目标账号" : "Target Account"} description={locale === "zh-CN" ? "选择要绑定或编辑微信配置的账号。" : "Select which account should receive or edit a WeChat configuration binding."}>
            <div className="grid gap-4 md:grid-cols-[1fr_auto]">
              <Select
                value={selectedAccountId ?? ""}
                onChange={(event) => {
                  const nextId = event.target.value;
                  setSelectedAccountId(nextId);
                  setExisting(null);
                  setForm(emptyForm);
                  setLoadedAccountId(null);
                  setLoading(true);
                  void load(nextId);
                  router.push(`/settings/wechat/${nextId}`);
                }}
              >
                {accounts.map((account) => (
                  <option key={account.account_id} value={account.account_id}>
                    {account.name}
                  </option>
                ))}
              </Select>
              <Button variant="secondary" onClick={() => void load(selectedAccountId)}>
                {locale === "zh-CN" ? "刷新" : "Refresh"}
              </Button>
            </div>
          </Card>

          <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
            <Card title={locale === "zh-CN" ? "配置表单" : "Configuration Form"} description={existing ? (locale === "zh-CN" ? "凭证字段留空即可保留当前的 App ID 和 Secret。" : "Leave credential fields blank to keep the current secret and App ID.") : (locale === "zh-CN" ? "新建配置时需要提供 App ID 和 App Secret。" : "A new config requires App ID and App Secret.")}>
              <div className="grid gap-5">
                <div className="grid gap-5 md:grid-cols-2">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">App ID</label>
                    <Input value={form.app_id} onChange={(event) => setField("app_id", event.target.value)} placeholder={existing?.app_id_masked || "wx1234567890"} />
                  </div>
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">App Secret</label>
                    <Input type="password" value={form.app_secret} onChange={(event) => setField("app_secret", event.target.value)} placeholder={existing?.has_app_secret ? "Stored in backend" : "Enter App Secret"} />
                  </div>
                </div>

                <div className="grid gap-5 md:grid-cols-2">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">{locale === "zh-CN" ? "默认作者" : "Default author"}</label>
                    <Input value={form.default_author} onChange={(event) => setField("default_author", event.target.value)} placeholder={selectedAccount?.name || (locale === "zh-CN" ? "默认作者" : "Default author")} />
                  </div>
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">{locale === "zh-CN" ? "默认封面 media_id" : "Default thumb media ID"}</label>
                    <Input value={form.default_thumb_media_id} onChange={(event) => setField("default_thumb_media_id", event.target.value)} placeholder={locale === "zh-CN" ? "可选 media_id" : "Optional media_id"} />
                  </div>
                </div>

                <label className="flex items-center justify-between rounded-2xl border border-slate-200 p-4">
                  <span>
                    <span className="block text-sm font-medium text-slate-900">{locale === "zh-CN" ? "开启评论" : "Enable comments"}</span>
                    <span className="text-sm text-slate-500">{locale === "zh-CN" ? "映射到微信的 need_open_comment 标志。" : "Maps to the WeChat `need_open_comment` flag."}</span>
                  </span>
                  <input type="checkbox" checked={form.need_open_comment} onChange={(event) => setField("need_open_comment", event.target.checked)} />
                </label>

                <label className="flex items-center justify-between rounded-2xl border border-slate-200 p-4">
                  <span>
                    <span className="block text-sm font-medium text-slate-900">{locale === "zh-CN" ? "仅粉丝可评论" : "Only fans can comment"}</span>
                    <span className="text-sm text-slate-500">{locale === "zh-CN" ? "映射到 only_fans_can_comment。" : "Maps to `only_fans_can_comment`."}</span>
                  </span>
                  <input type="checkbox" checked={form.only_fans_can_comment} onChange={(event) => setField("only_fans_can_comment", event.target.checked)} />
                </label>

                <label className="flex items-center justify-between rounded-2xl border border-slate-200 p-4">
                  <span>
                    <span className="block text-sm font-medium text-slate-900">{locale === "zh-CN" ? "启用微信发布" : "Enable WeChat publishing"}</span>
                    <span className="text-sm text-slate-500">{locale === "zh-CN" ? "后端发起发布时会检查这个开关。" : "Backend publish attempts respect this flag."}</span>
                  </span>
                  <input type="checkbox" checked={form.is_enabled} onChange={(event) => setField("is_enabled", event.target.checked)} />
                </label>
              </div>
            </Card>

            <div className="space-y-6">
              <Card title={locale === "zh-CN" ? "当前绑定" : "Current Binding"} description={locale === "zh-CN" ? "后端为当前账号返回的现有配置摘要。" : "Existing summary returned by the backend for the selected account."}>
                {existing ? (
                  <div className="grid gap-4 text-sm text-slate-600">
                    <div className="flex items-center justify-between gap-4">
                      <span className="text-slate-500">{locale === "zh-CN" ? "账号" : "Account"}</span>
                      <span className="font-medium text-slate-900">{selectedAccount?.name || selectedAccountId}</span>
                    </div>
                    <div className="flex items-center justify-between gap-4">
                      <span className="text-slate-500">{locale === "zh-CN" ? "脱敏 App ID" : "Masked App ID"}</span>
                      <span className="font-medium text-slate-900">{existing.app_id_masked}</span>
                    </div>
                    <div className="flex items-center justify-between gap-4">
                      <span className="text-slate-500">App Secret</span>
                      <Badge tone={existing.has_app_secret ? "success" : "muted"}>{existing.has_app_secret ? token("stored") : token("missing")}</Badge>
                    </div>
                    <div className="flex items-center justify-between gap-4">
                      <span className="text-slate-500">{locale === "zh-CN" ? "已启用" : "Enabled"}</span>
                      <Badge tone={existing.is_enabled ? "success" : "muted"}>{existing.is_enabled ? token("yes") : token("no")}</Badge>
                    </div>
                    <div className="flex items-center justify-between gap-4">
                      <span className="text-slate-500">{locale === "zh-CN" ? "测试状态" : "Test Status"}</span>
                      <Badge tone={existing.test_status === "success" ? "success" : existing.test_status === "failed" ? "danger" : "muted"}>{existing.test_status ? token(existing.test_status) : (locale === "zh-CN" ? "未知" : "Unknown")}</Badge>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                      <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "最近测试信息" : "Last test message"}</p>
                      <p className="mt-2 text-sm text-slate-600">{existing.test_message || (locale === "zh-CN" ? "还没有测试信息。" : "No test message recorded.")}</p>
                    </div>
                  </div>
                ) : (
                  <EmptyState title={locale === "zh-CN" ? "还没有微信配置" : "No WeChat config yet"} description={locale === "zh-CN" ? "先为这个账号创建第一条绑定，才能解锁发布和状态刷新。" : "Create the first binding for this account to unlock publish attempts and status refresh."} />
                )}
              </Card>

              <Card title={locale === "zh-CN" ? "操作" : "Actions"} description={locale === "zh-CN" ? "先做连通性校验，再保存到后端。" : "Run validation before saving or persist the config to the backend."}>
                <div className="flex flex-wrap gap-3">
                  <Button variant="secondary" disabled={!formReady} onClick={() => void runConnectionTest()}>
                    {locale === "zh-CN" ? "测试连接" : "Test Connection"}
                  </Button>
                  <Button disabled={saving || !selectedAccountId || !formReady} onClick={() => void submit()}>
                    {saving ? (locale === "zh-CN" ? "保存中..." : "Saving...") : existing ? (locale === "zh-CN" ? "保存配置" : "Save Configuration") : (locale === "zh-CN" ? "创建配置" : "Create Configuration")}
                  </Button>
                </div>
              </Card>
            </div>
          </div>
        </>
      ) : (
        <EmptyState title={locale === "zh-CN" ? "暂无可用账号" : "No accounts available"} description={locale === "zh-CN" ? "请先创建账号，再绑定微信凭证。" : "Create an account before attempting to bind WeChat credentials."} />
      )}
    </div>
  );
}
