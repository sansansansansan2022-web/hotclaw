"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { getAccount, listAccountMemories, rebuildAccountMemories, syncAccountMemories } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { formatDateTime, truncate } from "@/lib/utils";
import type { AccountDetail, ContentMemory } from "@/types";
import { Badge, Button, Card, EmptyState, ErrorState, Input, PageHeader, SkeletonRows, Table } from "@/components/console/ui";
import { useAppStore } from "@/store/appStore";

export function AccountMemoryPage({ accountId }: { accountId: string }) {
  const { locale } = useI18n();
  const pushToast = useAppStore((state) => state.pushToast);
  const [account, setAccount] = useState<AccountDetail | null>(null);
  const [memories, setMemories] = useState<ContentMemory[]>([]);
  const [queryInput, setQueryInput] = useState("");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | number | null>(null);
  const [loading, setLoading] = useState(true);
  const [featureUnavailable, setFeatureUnavailable] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async (nextQuery = query) => {
    try {
      setLoading(true);
      setError(null);
      setFeatureUnavailable(false);

      const accountRes = await getAccount(accountId);
      setAccount(accountRes);

      try {
        const memoryRes = await listAccountMemories(accountId, { query: nextQuery || undefined });
        setMemories(memoryRes.memories);
        setSelectedId((current) => current ?? memoryRes.memories[0]?.id ?? null);
      } catch (memoryError) {
        if (memoryError instanceof Error && /404|not found/i.test(memoryError.message)) {
          setFeatureUnavailable(true);
          setMemories([]);
          setSelectedId(null);
        } else {
          throw memoryError;
        }
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : locale === "zh-CN" ? "无法加载账号内容记忆。" : "Unable to load account memories.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [accountId]);

  const selectedMemory = useMemo(
    () => memories.find((memory) => String(memory.id) === String(selectedId)) ?? memories[0] ?? null,
    [memories, selectedId],
  );

  const runAction = async (action: () => Promise<{ message?: string | null }>, successTitle: string, fallbackMessage: string) => {
    try {
      const result = await action();
      pushToast({
        tone: "success",
        title: successTitle,
        message: result.message || fallbackMessage,
      });
      await load();
    } catch (actionError) {
      pushToast({
        tone: "danger",
        title: locale === "zh-CN" ? "操作失败" : "Action failed",
        message: actionError instanceof Error ? actionError.message : locale === "zh-CN" ? "发生了意外错误。" : "Unexpected error.",
      });
    }
  };

  const onSearch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setQuery(queryInput.trim());
    await load(queryInput.trim());
  };

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={locale === "zh-CN" ? "账号资产" : "Account Asset"}
        title={account?.name ? `${account.name} · ${locale === "zh-CN" ? "内容记忆" : "Content Memory"}` : locale === "zh-CN" ? "账号内容记忆" : "Account Content Memory"}
        description={
          locale === "zh-CN"
            ? "查看账号积累的历史文章记忆，支持搜索、重建和同步，便于检查风格检索资产。"
            : "Inspect stored article memories for an account, with search, rebuild and sync actions for retrieval assets."
        }
        actions={
          <>
            <Link href={`/accounts/${accountId}`}>
              <Button variant="secondary">{locale === "zh-CN" ? "返回账号" : "Back to Account"}</Button>
            </Link>
            <Button variant="secondary" onClick={() => void runAction(() => syncAccountMemories(accountId), locale === "zh-CN" ? "同步已触发" : "Sync started", locale === "zh-CN" ? "记忆同步任务已触发。" : "Memory sync was triggered.")}>
              {locale === "zh-CN" ? "同步记忆" : "Sync Memories"}
            </Button>
            <Button onClick={() => void runAction(() => rebuildAccountMemories(accountId), locale === "zh-CN" ? "重建已触发" : "Rebuild started", locale === "zh-CN" ? "记忆重建任务已触发。" : "Memory rebuild was triggered.")}>
              {locale === "zh-CN" ? "重建记忆" : "Rebuild Memory"}
            </Button>
          </>
        }
      />

      {loading ? (
        <SkeletonRows rows={5} />
      ) : error ? (
        <ErrorState title={locale === "zh-CN" ? "内容记忆加载失败" : "Content memory failed to load"} description={error} retry={() => void load()} />
      ) : (
        <>
          <Card
            title={locale === "zh-CN" ? "搜索与筛选" : "Search & Filter"}
            description={locale === "zh-CN" ? "按标题、摘要或标签检索账号记忆。" : "Search account memories by title, summary or tags."}
          >
            <form className="flex flex-col gap-3 md:flex-row" onSubmit={(event) => void onSearch(event)}>
              <Input
                value={queryInput}
                onChange={(event) => setQueryInput(event.target.value)}
                placeholder={locale === "zh-CN" ? "搜索标题、摘要、标签..." : "Search titles, summaries, tags..."}
              />
              <Button type="submit">{locale === "zh-CN" ? "搜索" : "Search"}</Button>
            </form>
            {query ? <p className="mt-3 text-xs text-slate-500">{locale === "zh-CN" ? `当前搜索：${query}` : `Current search: ${query}`}</p> : null}
          </Card>

          {featureUnavailable ? (
            <Card title={locale === "zh-CN" ? "功能尚未接通" : "Feature Not Connected Yet"} description={locale === "zh-CN" ? "当前后端还没有暴露账号内容记忆接口。" : "The backend is not exposing account memory endpoints yet."}>
              <EmptyState
                title={locale === "zh-CN" ? "暂无内容记忆接口" : "No memory API available"}
                description={
                  locale === "zh-CN"
                    ? "页面结构已准备好。后端一旦返回 account article memories，这里会直接展示真实列表和详情。"
                    : "The page structure is ready. Once the backend returns account article memories, this view will render the live list and detail panel."
                }
              />
            </Card>
          ) : (
            <div className="grid gap-6 xl:grid-cols-[1.2fr_0.9fr]">
              <Card
                title={locale === "zh-CN" ? "Memory 列表" : "Memory List"}
                description={locale === "zh-CN" ? "按账号沉淀的文章记忆资产。" : "Article memory assets accumulated for this account."}
              >
                {memories.length ? (
                  <Table columns={[locale === "zh-CN" ? "标题" : "Title", locale === "zh-CN" ? "摘要" : "Summary", locale === "zh-CN" ? "标签" : "Tags", locale === "zh-CN" ? "来源草稿" : "Source Draft", locale === "zh-CN" ? "时间" : "Time", locale === "zh-CN" ? "操作" : "Action"]}>
                    {memories.map((memory) => (
                      <tr key={String(memory.id)}>
                        <td className="px-5 py-4 text-sm font-semibold text-slate-900">{memory.title}</td>
                        <td className="px-5 py-4 text-sm text-slate-600">{truncate(memory.summary || memory.content_excerpt, 88) || (locale === "zh-CN" ? "暂无摘要" : "No summary")}</td>
                        <td className="px-5 py-4">
                          <div className="flex max-w-52 flex-wrap gap-2">
                            {memory.tags?.length ? memory.tags.slice(0, 3).map((tag) => <Badge key={tag} tone="muted">{tag}</Badge>) : <span className="text-sm text-slate-500">{locale === "zh-CN" ? "无标签" : "No tags"}</span>}
                          </div>
                        </td>
                        <td className="px-5 py-4 text-sm text-slate-600">{memory.source_draft_id ? `#${memory.source_draft_id}` : "--"}</td>
                        <td className="px-5 py-4 text-sm text-slate-600">{formatDateTime(memory.updated_at || memory.created_at)}</td>
                        <td className="px-5 py-4">
                          <Button variant="secondary" size="sm" onClick={() => setSelectedId(memory.id)}>
                            {locale === "zh-CN" ? "查看" : "Inspect"}
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </Table>
                ) : (
                  <EmptyState
                    title={locale === "zh-CN" ? "还没有内容记忆" : "No memories yet"}
                    description={
                      locale === "zh-CN"
                        ? "当前账号还没有积累 article memories，或者搜索条件没有命中结果。"
                        : "This account has not accumulated article memories yet, or the current search returned no matches."
                    }
                  />
                )}
              </Card>

              <Card
                title={locale === "zh-CN" ? "Memory 详情" : "Memory Detail"}
                description={locale === "zh-CN" ? "点击列表项后在这里查看详细内容。" : "Inspect a selected memory entry here."}
              >
                {selectedMemory ? (
                  <div className="space-y-5">
                    <div>
                      <h2 className="text-lg font-semibold text-slate-900">{selectedMemory.title}</h2>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {selectedMemory.tags?.map((tag) => (
                          <Badge key={tag} tone="brand">
                            {tag}
                          </Badge>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "摘要" : "Summary"}</p>
                      <p className="mt-2 text-sm leading-6 text-slate-600">{selectedMemory.summary || selectedMemory.content_excerpt || (locale === "zh-CN" ? "暂无摘要。" : "No summary available.")}</p>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                      <div>
                        <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "来源草稿" : "Source Draft"}</p>
                        <p className="mt-2 text-sm text-slate-600">{selectedMemory.source_draft_id ? `#${selectedMemory.source_draft_id}` : "--"}</p>
                      </div>
                      <div>
                        <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "来源任务" : "Source Task"}</p>
                        <p className="mt-2 text-sm text-slate-600">{selectedMemory.source_task_id || "--"}</p>
                      </div>
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{locale === "zh-CN" ? "元信息" : "Metadata"}</p>
                      <pre className="mt-2 overflow-x-auto rounded-2xl border border-slate-200 bg-slate-50/70 p-4 text-xs leading-6 text-slate-600">
                        {JSON.stringify(selectedMemory.metadata ?? selectedMemory, null, 2)}
                      </pre>
                    </div>
                  </div>
                ) : (
                  <EmptyState
                    title={locale === "zh-CN" ? "没有选中的 memory" : "No memory selected"}
                    description={locale === "zh-CN" ? "从左侧列表选择一条 memory 查看详情。" : "Choose a memory entry from the list to inspect details."}
                  />
                )}
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  );
}
