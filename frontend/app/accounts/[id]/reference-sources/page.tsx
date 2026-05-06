import { AppShell } from "@/components/console/layout";
import { ReferenceSourcesPage } from "@/components/console/reference-sources";

export default async function AccountReferenceSourcesRoute({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <AppShell>
      <ReferenceSourcesPage accountId={id} />
    </AppShell>
  );
}
