import { PublishLogsPage } from "@/components/console/publish-logs";

export default async function PublishLogsRoute({
  searchParams,
}: {
  searchParams: Promise<{ account_id?: string }>;
}) {
  const params = await searchParams;
  return <PublishLogsPage initialAccountId={params.account_id} />;
}
