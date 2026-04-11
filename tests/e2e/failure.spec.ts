import { selectors } from "./helpers/selectors";
import { assertStatusConsistency, waitForPublishTerminal, waitForTaskTerminal } from "./helpers/waiters";
import { expect, generateDraftFromWorkspace, test, triggerWorkspaceRun } from "./fixtures/golden-path";

test("generation failure surfaces terminal error details and does not hang", async ({ page, api }) => {
  const errorMessage = "E2E generation boom";
  await api.setE2EModes({
    generationMode: "fake_failure",
    generationFailureMessage: errorMessage,
  });

  const { taskId } = await triggerWorkspaceRun(page, api);
  const task = await waitForTaskTerminal(api, taskId);

  expect(task.status).toBe("failed");
  expect(task.error_message).toContain(errorMessage);

  await expect(page.locator(selectors.taskStatusBadge)).toHaveAttribute("data-status", "failed");
  await expect(page.locator(selectors.taskErrorMessage)).toContainText(errorMessage);
  await expect(page.locator(selectors.taskRerunButton)).toBeVisible();
  await expect(page.locator(selectors.taskRelatedDraftLink)).toHaveCount(0);
});

test("publish failure writes back error and keeps draft retryable", async ({ page, api }) => {
  const errorMessage = "E2E publish boom";
  await api.setE2EModes({
    generationMode: "fake_success",
    publishMode: "fake_failure",
    publishFailureMessage: errorMessage,
  });

  const { draft } = await generateDraftFromWorkspace(page, api, { withWechat: true });

  await page.locator(selectors.taskRelatedDraftLink).click();
  await page.waitForURL(new RegExp(`/drafts/${draft.id}$`));

  await page.locator(selectors.draftConfirmButton).click();
  await expect(page.locator(selectors.draftStatusBadge)).toHaveAttribute("data-status", "approved");

  await page.locator(selectors.draftPublishButton).click();

  const publishResult = await waitForPublishTerminal(api, { draftId: draft.id });
  expect(publishResult.record.publish_status).toBe("failed");
  expect(publishResult.record.error_message).toContain(errorMessage);

  await assertStatusConsistency(page, api, {
    draftId: draft.id,
    publishRecordId: publishResult.record.id,
    expectedDraftStatus: "approved",
    expectedPublishStatus: "failed",
    expectedPublishRecordStatus: "failed",
  });

  await expect(page.locator(selectors.draftPublishError)).toContainText(errorMessage);
  await expect(page.locator(selectors.draftRetryButton)).toBeVisible();
  await expect(page.locator(selectors.publishStatusBadge)).not.toHaveAttribute("data-status", "published");
});
