import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import assert from "node:assert/strict";

const source = readFileSync(resolve("components/console/account-compose-flow.tsx"), "utf8");

assert.match(
  source,
  /data-testid="recommendation-published-at"/,
  "recommendation cards should expose a published-at row",
);

assert.match(
  source,
  /whitespace-nowrap/,
  "recommendation action buttons should not wrap or collapse Chinese labels",
);

assert.match(
  source,
  /formatRecommendationPublishedAt/,
  "published-at display should be formatted through a shared helper",
);

assert.match(
  source,
  /data-testid="recommendation-page-size"/,
  "recommendation lists should expose a page-size selector",
);

assert.match(
  source,
  /data-testid="recommendation-pagination"/,
  "recommendation lists should render pagination controls",
);

assert.match(
  source,
  /data-testid="recommendation-refresh-button"/,
  "refresh recommendations button should live inside the recommendation card action",
);

assert.match(
  source,
  /data-testid="recommendation-source-link"/,
  "recommendation cards should expose a source article link when source_url exists",
);

assert.match(
  source,
  /rel="noreferrer noopener"/,
  "source article links should use safe external-link attributes",
);
