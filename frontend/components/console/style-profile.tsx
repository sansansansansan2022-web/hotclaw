"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { getAccount, getAccountStyleProfile, rebuildAccountStyleProfile } from "@/lib/api";
import { normalizeStyleProfile } from "@/lib/content-insights";
import { useI18n } from "@/lib/i18n";
import { formatDateTime } from "@/lib/utils";
import type { AccountDetail } from "@/types";
import { StyleProfileSummaryView } from "@/components/console/content-insights";
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader, SkeletonRows } from "@/components/console/ui";
import { useAppStore } from "@/store/appStore";

export function AccountStyleProfilePage({ accountId }: { accountId: string }) {
  const { locale } = useI18n();
  const pushToast = useAppStore((state) => state.pushToast);
  const [account, setAccount] = useState<AccountDetail | null>(null);
  const [profileRaw, setProfileRaw] = useState<Record<string, unknown> | null>(null);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [featureUnavailable, setFeatureUnavailable] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      setFeatureUnavailable(false);

      const accountRes = await getAccount(accountId);
      setAccount(accountRes);

      try {
        const profileRes = await getAccountStyleProfile(accountId);
        setGeneratedAt(profileRes.generated_at ?? null);
        setProfileRaw((profileRes.style_profile?.raw as Record<string, unknown> | null) ?? (profileRes.style_profile as Record<string, unknown> | null));
      } catch (profileError) {
        if (profileError instanceof Error && /404|not found/i.test(profileError.message)) {
          setFeatureUnavailable(true);
          setProfileRaw(null);
          setGeneratedAt(null);
        } else {
          throw profileError;
        }
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : locale === "zh-CN" ? "无法加载风格画像。" : "Unable to load style profile.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [accountId]);

  const profile = useMemo(() => normalizeStyleProfile(profileRaw, null), [profileRaw]);

  const rebuild = async () => {
    try {
      const response = await rebuildAccountStyleProfile(accountId);
      pushToast({
        tone: "success",
        title: locale === "zh-CN" ? "重建已触发" : "Rebuild started",
        message: response.message || (locale === "zh-CN" ? "风格画像重建任务已触发。" : "Style profile rebuild was triggered."),
      });
      await load();
    } catch (actionError) {
      pushToast({
        tone: "danger",
        title: locale === "zh-CN" ? "重建失败" : "Rebuild failed",
        message: actionError instanceof Error ? actionError.message : locale === "zh-CN" ? "发生了意外错误。" : "Unexpected error.",
      });
    }
  };

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={locale === "zh-CN" ? "账号资产" : "Account Asset"}
        title={account?.name ? `${account.name} · ${locale === "zh-CN" ? "风格画像" : "Style Profile"}` : locale === "zh-CN" ? "账号风格画像" : "Account Style Profile"}
        description={
          locale === "zh-CN"
            ? "让账号风格资产可见，便于人工判断 tone、结构、词汇特征和禁用表达。"
            : "Makes the account style asset visible so operators can inspect tone, structure, lexical features and banned patterns."
        }
        actions={
          <>
            <Link href={`/accounts/${accountId}`}>
              <Button variant="secondary">{locale === "zh-CN" ? "返回账号" : "Back to Account"}</Button>
            </Link>
            <Button onClick={() => void rebuild()}>{locale === "zh-CN" ? "重建画像" : "Rebuild Profile"}</Button>
          </>
        }
      />

      {loading ? (
        <SkeletonRows rows={4} />
      ) : error ? (
        <ErrorState title={locale === "zh-CN" ? "风格画像加载失败" : "Style profile failed to load"} description={error} retry={() => void load()} />
      ) : featureUnavailable ? (
        <Card
          title={locale === "zh-CN" ? "功能尚未接通" : "Feature Not Connected Yet"}
          description={locale === "zh-CN" ? "当前后端还没有暴露 style profile 接口。" : "The backend is not exposing a style profile endpoint yet."}
        >
          <EmptyState
            title={locale === "zh-CN" ? "暂无风格画像接口" : "No style profile API available"}
            description={
              locale === "zh-CN"
                ? "页面结构和重建入口已经准备好。后端一旦提供 style profile，这里会直接展示真实内容。"
                : "The page structure and rebuild action are ready. Once the backend returns a style profile, this page will render the live asset."
            }
          />
        </Card>
      ) : !profile ? (
        <Card
          title={locale === "zh-CN" ? "风格画像为空" : "Style Profile Empty"}
          description={locale === "zh-CN" ? "后端接口存在，但当前账号还没有生成 style profile。" : "The backend endpoint exists, but this account has not produced a style profile yet."}
        >
          <EmptyState
            title={locale === "zh-CN" ? "还没有风格画像" : "No style profile yet"}
            description={locale === "zh-CN" ? "你可以手动触发重建，或者等待后端在内容记忆积累后生成画像。" : "Trigger a rebuild manually, or wait for the backend to generate one after more memory is accumulated."}
          />
        </Card>
      ) : (
        <div className="grid gap-6 xl:grid-cols-[1.15fr_0.95fr]">
          <Card
            title={locale === "zh-CN" ? "画像总览" : "Profile Overview"}
            description={locale === "zh-CN" ? "按现有控制台卡片风格展示 tone、结构和词汇特征。" : "Shows tone, structure and lexical features in the existing console card style."}
            action={generatedAt ? <Badge tone="info">{locale === "zh-CN" ? `生成于 ${formatDateTime(generatedAt)}` : `Generated ${formatDateTime(generatedAt)}`}</Badge> : null}
          >
            <StyleProfileSummaryView profile={profile} locale={locale} />
          </Card>

          <div className="space-y-6">
            <Card
              title={locale === "zh-CN" ? "证据与约束" : "Evidence & Constraints"}
              description={locale === "zh-CN" ? "把禁用表达和证据文章单独拆出来，方便审核。" : "Separates banned patterns and evidence articles for easier review."}
            >
              <div className="space-y-5">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "禁用表达" : "Banned Patterns"}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {profile.banned_patterns?.length ? profile.banned_patterns.map((pattern) => <Badge key={pattern} tone="danger">{pattern}</Badge>) : <span className="text-sm text-slate-500">{locale === "zh-CN" ? "暂无禁用表达。" : "No banned patterns."}</span>}
                  </div>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "证据文章 ID" : "Evidence Article IDs"}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {profile.evidence_article_ids?.length ? profile.evidence_article_ids.map((item) => <Badge key={String(item)} tone="info">{item}</Badge>) : <span className="text-sm text-slate-500">{locale === "zh-CN" ? "暂无证据文章。" : "No evidence articles."}</span>}
                  </div>
                </div>
              </div>
            </Card>

            <Card
              title={locale === "zh-CN" ? "JSON 视图" : "JSON View"}
              description={locale === "zh-CN" ? "第一版保留原始结构，便于对齐后端字段演进。" : "Keeps the raw structure visible so frontend and backend can evolve the schema together."}
            >
              <pre className="overflow-x-auto rounded-2xl border border-slate-200 bg-slate-50/70 p-4 text-xs leading-6 text-slate-600">
                {JSON.stringify(profileRaw ?? profile, null, 2)}
              </pre>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
