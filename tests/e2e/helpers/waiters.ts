import { expect, type Page } from "@playwright/test";

import type { DraftDetailData, DraftSummaryData, HotClawApi, PublishRecordData, TaskDetailData } from "./api";
import { selectors } from "./selectors";

type PollOptions = {
  timeoutMs?: number;
  intervalMs?: number;
};

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function poll<T>(
  callback: () => Promise<T>,
  done: (value: T) => boolean,
  options: PollOptions = {},
): Promise<T> {
  const timeoutMs = options.timeoutMs ?? 20_000;
  const intervalMs = options.intervalMs ?? 500;
  const deadline = Date.now() + timeoutMs;

  let lastValue: T | undefined;
  while (Date.now() < deadline) {
    lastValue = await callback();
    if (done(lastValue)) {
      return lastValue;
    }
    await delay(intervalMs);
  }

  if (lastValue !== undefined) {
    return lastValue;
  }
  throw new Error("Polling timed out before the first value was returned.");
}

export async function waitForTaskTerminal(
  api: HotClawApi,
  taskId: string,
  options: PollOptions = {},
): Promise<TaskDetailData> {
  return poll(
    () => api.getTask(taskId),
    (task) => ["completed", "failed"].includes(task.status),
    options,
  );
}

export async function waitForDraftCreated(
  api: HotClawApi,
  accountId: string,
  options: PollOptions & { taskId?: string } = {},
): Promise<DraftSummaryData> {
  return poll(
    async () => {
      const list = await api.listDrafts({ accountId });
      return (
        list.drafts.find((draft) => !options.taskId || draft.task_id === options.taskId) ??
        null
      );
    },
    (draft): draft is DraftSummaryData => Boolean(draft),
    options,
  );
}

export async function waitForPublishTerminal(
  api: HotClawApi,
  target: { draftId?: number; publishRecordId?: number },
  options: PollOptions = {},
): Promise<{ draft: DraftDetailData; record: PublishRecordData }> {
  const result = await poll(
    async () => {
      const record =
        target.publishRecordId !== undefined
          ? await api.getPublishRecord(target.publishRecordId)
          : await api.getLatestPublishRecordForDraft(target.draftId!);

      if (!record) {
        return null;
      }

      const draft = await api.getDraft(record.draft_id);
      return { draft, record };
    },
    (result): result is { draft: DraftDetailData; record: PublishRecordData } =>
      Boolean(result) && ["published", "failed", "unknown"].includes(result.record.publish_status),
    options,
  );

  if (!result) {
    const targetLabel =
      target.publishRecordId !== undefined ? `publish record ${target.publishRecordId}` : `draft ${target.draftId}`;
    throw new Error(`Timed out waiting for terminal publish status for ${targetLabel}.`);
  }

  return result;
}

function normalizeRecordStatusToDraftPublishStatus(status: string): string {
  if (status === "published") return "published";
  if (status === "failed" || status === "unknown") return "failed";
  return "pending";
}

export async function assertStatusConsistency(
  page: Page,
  api: HotClawApi,
  options: {
    draftId: number;
    publishRecordId?: number;
    expectedDraftStatus?: string;
    expectedPublishStatus?: string;
    expectedPublishRecordStatus?: string;
  },
): Promise<{ draft: DraftDetailData; record: PublishRecordData | null }> {
  const draft = await api.getDraft(options.draftId);
  const record =
    options.publishRecordId !== undefined
      ? await api.getPublishRecord(options.publishRecordId)
      : await api.getLatestPublishRecordForDraft(options.draftId);

  if (options.expectedDraftStatus) {
    expect(draft.draft_status).toBe(options.expectedDraftStatus);
    await expect(page.locator(selectors.draftStatusBadge)).toHaveAttribute("data-status", options.expectedDraftStatus);
  } else {
    await expect(page.locator(selectors.draftStatusBadge)).toHaveAttribute("data-status", draft.draft_status);
  }

  if (options.expectedPublishStatus) {
    expect(draft.publish_status).toBe(options.expectedPublishStatus);
    await expect(page.locator(selectors.publishStatusBadge)).toHaveAttribute("data-status", options.expectedPublishStatus);
  } else {
    await expect(page.locator(selectors.publishStatusBadge)).toHaveAttribute("data-status", draft.publish_status);
  }

  if (record) {
    if (options.expectedPublishRecordStatus) {
      expect(record.publish_status).toBe(options.expectedPublishRecordStatus);
    }
    expect(draft.publish_status).toBe(normalizeRecordStatusToDraftPublishStatus(record.publish_status));
  }

  return { draft, record };
}
