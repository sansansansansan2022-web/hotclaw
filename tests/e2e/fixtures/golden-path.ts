import type { Page } from "@playwright/test";
import { expect, test as base } from "@playwright/test";

import { HotClawApi, type AccountData, type DraftSummaryData, type TaskDetailData } from "../helpers/api";
import { selectors } from "../helpers/selectors";
import { waitForDraftCreated, waitForTaskTerminal } from "../helpers/waiters";

export const test = base.extend<{ api: HotClawApi }>({
  api: async ({ request }, use) => {
    const api = new HotClawApi(request);
    await api.resetE2EModes();
    await use(api);
    await api.resetE2EModes();
  },
});

export { expect };

export async function triggerWorkspaceRun(
  page: Page,
  api: HotClawApi,
  options: {
    withWechat?: boolean;
    accountOverrides?: Record<string, unknown>;
  } = {},
): Promise<{ account: AccountData; taskId: string }> {
  const account = await api.createAccount(options.accountOverrides);
  if (options.withWechat) {
    await api.createWeChatConfig(account.account_id);
  }

  await page.goto(`/accounts/${account.account_id}/workspace`);
  await page.locator(selectors.accountWorkspaceRunButton).click();
  await page.waitForURL(/\/task\/[^/?#]+/);

  const match = /\/task\/([^/?#]+)/.exec(page.url());
  if (!match?.[1]) {
    throw new Error(`Could not extract task id from URL: ${page.url()}`);
  }

  return { account, taskId: match[1] };
}

export async function generateDraftFromWorkspace(
  page: Page,
  api: HotClawApi,
  options: {
    withWechat?: boolean;
    accountOverrides?: Record<string, unknown>;
  } = {},
): Promise<{ account: AccountData; taskId: string; task: TaskDetailData; draft: DraftSummaryData }> {
  const { account, taskId } = await triggerWorkspaceRun(page, api, options);
  const task = await waitForTaskTerminal(api, taskId);
  if (task.status !== "completed") {
    throw new Error(`Expected completed task, got ${task.status} for ${taskId}`);
  }
  const draft = await waitForDraftCreated(api, account.account_id, { taskId });
  return { account, taskId, task, draft };
}
