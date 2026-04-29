import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = process.cwd();
const settingsOverview = readFileSync(resolve(root, "components/console/settings-overview.tsx"), "utf8");
const apiIndex = readFileSync(resolve(root, "lib/api/index.ts"), "utf8");

assert.match(settingsOverview, /Image Asset Configuration/);
assert.match(settingsOverview, /image_generation_provider/);
assert.match(settingsOverview, /image_generation_model/);
assert.match(settingsOverview, /image_generation_api_key/);
assert.match(settingsOverview, /image_generation_base_url/);
assert.match(settingsOverview, /image_generation_enabled/);
assert.match(settingsOverview, /Enable AI image generation during post-process/);
assert.match(settingsOverview, /Image Generation API Key/);
assert.match(settingsOverview, /Image Generation Base URL/);
assert.match(settingsOverview, /Image search APIs are not wired yet/);
assert.match(settingsOverview, /Unsplash\/Pexels\/Bing\/SerpAPI-like/);
assert.match(apiIndex, /interface SystemConfigUpsertOptions/);
assert.match(apiIndex, /IMAGE_GENERATION_PROVIDER_PRESETS/);
assert.match(apiIndex, /default_base_url/);
for (const provider of ["dashscope", "openai", "google_vertex", "stability", "volcengine", "custom"]) {
  assert.match(apiIndex, new RegExp(`provider_id: "${provider}"`));
}

const providersCardIndex = settingsOverview.indexOf('Card title="Providers, Agents & Skills"');
const imageConfigIndex = settingsOverview.indexOf('title="Image Asset Configuration"');
const coverageCardIndex = settingsOverview.indexOf('Card title={t("settings.coverage")}');
assert.ok(providersCardIndex >= 0, "Providers, Agents & Skills card should exist");
assert.ok(imageConfigIndex > providersCardIndex, "Image Asset Configuration should be inside Providers, Agents & Skills");
assert.ok(imageConfigIndex < coverageCardIndex, "Image Asset Configuration should remain in the provider inventory column");

console.log("settings image config static checks passed");
