import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = process.cwd();
const settingsOverview = readFileSync(resolve(root, "components/console/settings-overview.tsx"), "utf8");
const llmProvidersPage = readFileSync(resolve(root, "app/settings/llm-providers/page.tsx"), "utf8");
const apiIndex = readFileSync(resolve(root, "lib/api/index.ts"), "utf8");

assert.match(settingsOverview, /Test Connection/, "Image config should expose a connection test button");
assert.match(settingsOverview, /testImageGenerationConnection/, "Settings page should call the image connection test API");
assert.match(settingsOverview, /Connection test succeeded|Connection test failed|imageTestResult/, "Image config should render connection feedback");

const llmTestButtonCount = (llmProvidersPage.match(/Test Connection/g) ?? []).length;
assert.ok(llmTestButtonCount >= 2, "LLM Providers page should expose Test Connection in edit and view modes");

assert.match(apiIndex, /export async function testImageGenerationConnection/, "Frontend API should expose image connection test helper");

console.log("model connection static checks passed");
