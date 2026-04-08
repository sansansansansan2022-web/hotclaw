import { AppShell } from "@/components/console/layout";
import { AccountWorkspacePage } from "@/components/console/account-workspace";

export default async function AccountWorkspaceRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <AppShell>
      <AccountWorkspacePage accountId={id} />
    </AppShell>
  );
}
