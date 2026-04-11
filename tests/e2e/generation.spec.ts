import { selectors } from "./helpers/selectors";
import { waitForDraftCreated, waitForTaskTerminal } from "./helpers/waiters";
import { expect, test, triggerWorkspaceRun } from "./fixtures/golden-path";

test("generation success creates a completed task and visible draft", async ({ page, api }) => {
  await api.setE2EModes({ generationMode: "fake_success" });

  const { account, taskId } = await triggerWorkspaceRun(page, api);

  const task = await waitForTaskTerminal(api, taskId);
  expect(task.status).toBe("completed");

  const draft = await waitForDraftCreated(api, account.account_id, { taskId });
  expect(draft.draft_status).toBe("pending_review");
  expect(draft.publish_status).toBe("not_published");

  await expect(page.locator(selectors.taskStatusBadge)).toHaveAttribute("data-status", "completed");
  await expect(page.locator(selectors.taskGeneratedDraftRegion)).toContainText(draft.title);
  await expect(page.locator(selectors.taskRelatedDraftLink)).toHaveAttribute("data-draft-id", String(draft.id));
});
