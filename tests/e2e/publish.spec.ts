import { selectors } from "./helpers/selectors";
import { assertStatusConsistency, waitForPublishTerminal } from "./helpers/waiters";
import { generateDraftFromWorkspace, expect, test } from "./fixtures/golden-path";

test("publish success writes back publish record and final published state", async ({ page, api }) => {
  await api.setE2EModes({
    generationMode: "fake_success",
    publishMode: "fake_success",
  });

  const { draft } = await generateDraftFromWorkspace(page, api, { withWechat: true });

  await page.locator(selectors.taskRelatedDraftLink).click();
  await page.waitForURL(new RegExp(`/drafts/${draft.id}$`));

  await page.locator(selectors.draftConfirmButton).click();
  await expect(page.locator(selectors.draftStatusBadge)).toHaveAttribute("data-status", "approved");

  await page.locator(selectors.draftPublishButton).click();

  const publishResult = await waitForPublishTerminal(api, { draftId: draft.id });
  expect(publishResult.record.id).toBeGreaterThan(0);
  expect(publishResult.record.publish_id).toBeTruthy();
  expect(publishResult.record.url).toContain(`/publish/${publishResult.record.id}`);

  await assertStatusConsistency(page, api, {
    draftId: draft.id,
    publishRecordId: publishResult.record.id,
    expectedDraftStatus: "published",
    expectedPublishStatus: "published",
    expectedPublishRecordStatus: "published",
  });

  await expect(page.locator(selectors.draftPublishStatusRegion)).toHaveAttribute(
    "data-latest-record-id",
    String(publishResult.record.id),
  );
  await expect(page.locator(selectors.publishRecordRow(publishResult.record.id))).toBeVisible();
});
