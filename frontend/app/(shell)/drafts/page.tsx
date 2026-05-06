import { DraftsCenterPage } from "@/components/console/drafts-list";

export default async function DraftsRoute({
  searchParams,
}: {
  searchParams: Promise<{ account_id?: string }>;
}) {
  const params = await searchParams;
  return <DraftsCenterPage initialAccountId={params.account_id} />;
}
