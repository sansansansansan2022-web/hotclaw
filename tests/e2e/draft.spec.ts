import { selectors } from "./helpers/selectors";
import { generateDraftFromWorkspace, expect, test } from "./fixtures/golden-path";

test("draft confirm success advances state and prevents duplicate submit", async ({ page, api }) => {
  await api.setE2EModes({ generationMode: "fake_success" });

  const { draft } = await generateDraftFromWorkspace(page, api);

  await expect(page.locator(selectors.taskRelatedDraftLink)).toHaveAttribute("data-draft-id", String(draft.id));
  await page.locator(selectors.taskRelatedDraftLink).click();
  await page.waitForURL(new RegExp(`/drafts/${draft.id}$`));

  await page.locator(selectors.draftConfirmButton).click();

  const confirmedDraft = await api.getDraft(draft.id);
  expect(confirmedDraft.draft_status).toBe("approved");
  expect(confirmedDraft.publish_status).toBe("not_published");
  expect(confirmedDraft.confirmed_at).toBeTruthy();

  await expect(page.locator(selectors.draftStatusBadge)).toHaveAttribute("data-status", "approved");
  await expect(page.locator(selectors.publishStatusBadge)).toHaveAttribute("data-status", "not_published");
  await expect(page.locator(selectors.draftConfirmButton)).toBeDisabled();
});
