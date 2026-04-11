import fs from "node:fs/promises";
import path from "node:path";

import { generateDraftFromWorkspace, expect, test } from "./fixtures/golden-path";
import { selectors } from "./helpers/selectors";

type PageCheckResult = {
  name: string;
  route: string;
  finalUrl: string;
  httpStatus: number | null;
  checks: string[];
};

const auditRoot = path.resolve(process.cwd(), "audit");
const screenshotRoot = path.join(auditRoot, "screenshots");
const artifactRoot = path.join(auditRoot, "artifacts");
const apiBaseURL = process.env.E2E_API_BASE_URL ?? "http://127.0.0.1:8107";

async function capturePage(
  page: import("@playwright/test").Page,
  results: PageCheckResult[],
  options: {
    name: string;
    route: string;
    checks: string[];
    verify: () => Promise<void>;
  },
): Promise<void> {
  const response = await page.goto(options.route);
  await page.waitForLoadState("networkidle");

  await expect(page.locator("body")).toBeVisible();
  await expect(page.getByText("Internal Server Error")).toHaveCount(0);
  await options.verify();

  const status = response?.status() ?? null;
  if (status !== null) {
    expect(status).toBeLessThan(400);
  }

  const screenshotPath = path.join(screenshotRoot, `${options.name}.png`);
  await page.screenshot({ path: screenshotPath, fullPage: true });

  results.push({
    name: options.name,
    route: options.route,
    finalUrl: page.url(),
    httpStatus: status,
    checks: options.checks,
  });
}

test("page smoke covers core console surfaces", async ({ page, api }) => {
  await fs.mkdir(screenshotRoot, { recursive: true });
  await fs.mkdir(artifactRoot, { recursive: true });

  await api.setE2EModes({
    generationMode: "fake_success",
    publishMode: "fake_success",
  });

  const { account, taskId, draft } = await generateDraftFromWorkspace(page, api, {
    withWechat: true,
  });

  const pageResults: PageCheckResult[] = [];

  await capturePage(page, pageResults, {
    name: "page-smoke-dashboard",
    route: "/dashboard",
    checks: ['a[href="/accounts/new"] visible', 'a[href="/workspace"] visible'],
    verify: async () => {
      await expect(page.locator('a[href="/accounts/new"]').first()).toBeVisible();
      await expect(page.locator('a[href="/workspace"]').first()).toBeVisible();
    },
  });

  await capturePage(page, pageResults, {
    name: "page-smoke-accounts",
    route: "/accounts",
    checks: ["created account name visible"],
    verify: async () => {
      await expect(page.getByText(account.name).first()).toBeVisible();
    },
  });

  await capturePage(page, pageResults, {
    name: "page-smoke-account-detail",
    route: `/accounts/${account.account_id}`,
    checks: ['[data-testid="account-detail-run-button"] visible'],
    verify: async () => {
      await expect(page.locator('[data-testid="account-detail-run-button"]')).toBeVisible();
    },
  });

  await capturePage(page, pageResults, {
    name: "page-smoke-account-workspace",
    route: `/accounts/${account.account_id}/workspace`,
    checks: [
      selectors.accountWorkspaceRunButton,
      `[data-testid="task-row-${taskId}"] visible`,
      `[data-testid="draft-row-${draft.id}"] visible`,
    ],
    verify: async () => {
      await expect(page.locator(selectors.accountWorkspaceRunButton)).toBeVisible();
      await expect(page.locator(`[data-testid="task-row-${taskId}"]`)).toBeVisible();
      await expect(page.locator(`[data-testid="draft-row-${draft.id}"]`)).toBeVisible();
    },
  });

  await capturePage(page, pageResults, {
    name: "page-smoke-task-history",
    route: "/tasks/history",
    checks: [`task id ${taskId} visible`, `a[href="/task/${taskId}"] visible`],
    verify: async () => {
      await expect(page.getByText(taskId).first()).toBeVisible();
      await expect(page.locator(`a[href="/task/${taskId}"]`).first()).toBeVisible();
    },
  });

  await capturePage(page, pageResults, {
    name: "page-smoke-task-detail",
    route: `/task/${taskId}`,
    checks: [
      selectors.taskStatusBadge,
      selectors.taskGeneratedDraftRegion,
      selectors.taskRelatedDraftLink,
    ],
    verify: async () => {
      await expect(page.locator(selectors.taskStatusBadge)).toBeVisible();
      await expect(page.locator(selectors.taskGeneratedDraftRegion)).toBeVisible();
      await expect(page.locator(selectors.taskRelatedDraftLink)).toHaveAttribute("data-draft-id", String(draft.id));
    },
  });

  await capturePage(page, pageResults, {
    name: "page-smoke-drafts-list",
    route: "/drafts",
    checks: [
      `[data-testid="draft-row-${draft.id}"] visible`,
      `[data-testid="draft-open-${draft.id}"] visible`,
    ],
    verify: async () => {
      await expect(page.locator(`[data-testid="draft-row-${draft.id}"]`)).toBeVisible();
      await expect(page.locator(`[data-testid="draft-open-${draft.id}"]`)).toBeVisible();
    },
  });

  await capturePage(page, pageResults, {
    name: "page-smoke-draft-detail",
    route: `/drafts/${draft.id}`,
    checks: [
      selectors.draftStatusBadge,
      selectors.publishStatusBadge,
      selectors.draftConfirmButton,
    ],
    verify: async () => {
      await expect(page.locator(selectors.draftStatusBadge)).toBeVisible();
      await expect(page.locator(selectors.publishStatusBadge)).toBeVisible();
      await expect(page.locator(selectors.draftConfirmButton)).toBeVisible();
    },
  });

  const confirmResponse = await page.request.post(`${apiBaseURL}/api/v1/drafts/${draft.id}/confirm-publish`);
  expect(confirmResponse.ok()).toBeTruthy();

  const publishResponse = await page.request.post(`${apiBaseURL}/api/v1/drafts/${draft.id}/publish-to-wechat`);
  expect(publishResponse.ok()).toBeTruthy();

  await capturePage(page, pageResults, {
    name: "page-smoke-publish-logs",
    route: "/publish-logs",
    checks: [`a[href="/drafts/${draft.id}"] visible`],
    verify: async () => {
      await expect(page.locator(`a[href="/drafts/${draft.id}"]`).first()).toBeVisible();
    },
  });

  await capturePage(page, pageResults, {
    name: "page-smoke-publish-records-redirect",
    route: "/publish-records",
    checks: ["legacy route redirects to /publish-logs"],
    verify: async () => {
      await expect(page).toHaveURL(/\/publish-logs$/);
    },
  });

  await capturePage(page, pageResults, {
    name: "page-smoke-settings",
    route: "/settings",
    checks: [
      'a[href="/settings/wechat"] visible',
      `a[href="/settings/wechat/${account.account_id}"] visible`,
    ],
    verify: async () => {
      await expect(page.locator('a[href="/settings/wechat"]').first()).toBeVisible();
      await expect(page.locator(`a[href="/settings/wechat/${account.account_id}"]`).first()).toBeVisible();
    },
  });

  const publishPayload = await publishResponse.json();

  await fs.writeFile(
    path.join(artifactRoot, "page-smoke-summary.json"),
    JSON.stringify(
      {
        generated_at: new Date().toISOString(),
        mode: "playwright-e2e-test-mode",
        account_id: account.account_id,
        task_id: taskId,
        draft_id: draft.id,
        publish_response: publishPayload,
        pages: pageResults,
      },
      null,
      2,
    ),
    "utf8",
  );
});
